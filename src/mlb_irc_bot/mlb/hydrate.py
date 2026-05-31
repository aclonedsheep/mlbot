SCHEDULE_HYDRATE = "team,linescore,probablePitcher,flags"
SCHEDULE_HYDRATION_CATALOG = "hydrations"


def schedule_params(date_iso: str, team_id: int | None = None) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        "sportId": 1,
        "date": date_iso,
        "hydrate": SCHEDULE_HYDRATE,
    }
    if team_id is not None:
        params["teamId"] = team_id
    return params
