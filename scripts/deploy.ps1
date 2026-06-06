<#
.SYNOPSIS
Deploy mlbot to the production VPS.

.DESCRIPTION
Pushes the selected branch, SSHes to the VPS, fast-forwards the remote checkout,
rebuilds the Docker Compose service, restarts it, and runs a dry-run health check
inside the rebuilt container.
#>

[CmdletBinding()]
param(
    [string]$DeployHost = $(if ($env:MLBOT_DEPLOY_HOST) { $env:MLBOT_DEPLOY_HOST } else { "208.109.241.169" }),
    [string]$RemotePath = $(if ($env:MLBOT_DEPLOY_PATH) { $env:MLBOT_DEPLOY_PATH } else { "/home/wolfb/mlbot" }),
    [string]$GitRemote = $(if ($env:MLBOT_DEPLOY_REMOTE) { $env:MLBOT_DEPLOY_REMOTE } else { "origin" }),
    [string]$Branch = $(if ($env:MLBOT_DEPLOY_BRANCH) { $env:MLBOT_DEPLOY_BRANCH } else { "main" }),
    [string]$Service = $(if ($env:MLBOT_DEPLOY_SERVICE) { $env:MLBOT_DEPLOY_SERVICE } else { "mlb-irc-bot" }),
    [string]$GitHubHost = $(if ($env:MLBOT_GITHUB_HOST) { $env:MLBOT_GITHUB_HOST } else { "github.com" }),
    [string]$GitHubUser = $(if ($env:MLBOT_GITHUB_USER) { $env:MLBOT_GITHUB_USER } else { "aclonedsheep" }),
    [switch]$SkipPush,
    [switch]$NoGhCredential,
    [switch]$AllowDirty,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$InputText
    )

    $display = "$FilePath $($Arguments -join ' ')"
    Write-Host ">>> $display"
    if ($DryRun) {
        return
    }

    if ($PSBoundParameters.ContainsKey("InputText")) {
        $InputText | & $FilePath @Arguments
    } else {
        & $FilePath @Arguments
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $display"
    }
}

function Get-ExternalOutput {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $output = & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
    return $output
}

function Assert-CommandExists {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH."
    }
}

function Assert-CleanCheckout {
    param(
        [Parameter(Mandatory = $true)][string]$PathLabel,
        [Parameter(Mandatory = $true)][scriptblock]$StatusCommand
    )

    if ($AllowDirty) {
        return
    }

    $status = & $StatusCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect $PathLabel git status."
    }
    if ($status) {
        $statusText = ($status -join [Environment]::NewLine)
        throw "$PathLabel has uncommitted changes. Commit/stash them or rerun with -AllowDirty.`n$statusText"
    }
}

function Get-ActiveGhUser {
    param([Parameter(Mandatory = $true)][string]$HostName)

    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        return $null
    }

    $status = & gh auth status --hostname $HostName 2>&1
    if ($LASTEXITCODE -ne 0) {
        return $null
    }

    $currentUser = $null
    foreach ($line in $status) {
        if ($line -match "account\s+(\S+)") {
            $currentUser = $Matches[1]
            continue
        }
        if ($line -match "Active account:\s+true") {
            return $currentUser
        }
    }

    return $null
}

function Quote-BashArg {
    param([Parameter(Mandatory = $true)][string]$Value)

    return "'" + $Value.Replace("'", "'\''") + "'"
}

Assert-CommandExists "git"
Assert-CommandExists "ssh"

$repoRoot = Get-ExternalOutput "git" @("rev-parse", "--show-toplevel")
if (-not $repoRoot) {
    throw "This script must be run from inside a git checkout."
}
Set-Location $repoRoot

$currentBranch = Get-ExternalOutput "git" @("branch", "--show-current")
if ($currentBranch -ne $Branch) {
    throw "Current branch is '$currentBranch', but deploy branch is '$Branch'. Check out '$Branch' or pass -Branch explicitly."
}

Assert-CleanCheckout "Local checkout" { & git status --porcelain }

if (-not $SkipPush) {
    if ($NoGhCredential -or -not $GitHubUser) {
        Invoke-External "git" @("push", $GitRemote, $Branch)
    } else {
        Assert-CommandExists "gh"
        $previousGhUser = Get-ActiveGhUser $GitHubHost
        try {
            if ($previousGhUser -ne $GitHubUser) {
                Invoke-External "gh" @("auth", "switch", "--hostname", $GitHubHost, "--user", $GitHubUser)
            }
            Invoke-External "git" @(
                "-c",
                "credential.helper=",
                "-c",
                "credential.helper=!gh auth git-credential",
                "push",
                $GitRemote,
                $Branch
            )
        } finally {
            if (-not $DryRun -and $previousGhUser -and $previousGhUser -ne $GitHubUser) {
                Invoke-External "gh" @("auth", "switch", "--hostname", $GitHubHost, "--user", $previousGhUser)
            }
        }
    }
}

$remoteScript = @'
set -euo pipefail

remote_path="$1"
git_remote="$2"
branch="$3"
service="$4"

cd "$remote_path"

if [ -n "$(git status --porcelain)" ]; then
  echo "Remote checkout has uncommitted changes:" >&2
  git status --short >&2
  exit 1
fi

git fetch "$git_remote" "$branch"
git checkout "$branch"
git pull --ff-only "$git_remote" "$branch"
docker compose up -d --build "$service"
docker compose ps "$service"
docker compose exec -T "$service" python -m mlb_irc_bot --dry-run
container_id="$(docker compose ps -q "$service")"
docker inspect "$container_id" --format 'status={{.State.Status}} running={{.State.Running}} restarts={{.RestartCount}} started={{.State.StartedAt}}'
git status --short --branch
git rev-parse --short HEAD
'@

$remoteCommand = "bash -se -- $(Quote-BashArg $RemotePath) $(Quote-BashArg $GitRemote) $(Quote-BashArg $Branch) $(Quote-BashArg $Service)"
Invoke-External "ssh" @("-o", "BatchMode=yes", $DeployHost, $remoteCommand) -InputText $remoteScript

Write-Host "Deploy complete: ${DeployHost}:${RemotePath} ($Branch / $Service)"
