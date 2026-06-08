"""Small helpers for IRC text styling."""

from __future__ import annotations

import re
from enum import IntEnum

BOLD = "\x02"
COLOR = "\x03"
RESET = "\x0f"
ITALIC = "\x1d"


class IRCColor(IntEnum):
    WHITE = 0
    BLACK = 1
    NAVY = 2
    GREEN = 3
    RED = 4
    MAROON = 5
    PURPLE = 6
    ORANGE = 7
    YELLOW = 8
    LIGHT_GREEN = 9
    TEAL = 10
    LIGHT_CYAN = 11
    LIGHT_BLUE = 12
    PINK = 13
    GRAY = 14
    LIGHT_GRAY = 15


_COLOR_CODE_RE = re.compile(r"\x03(?:\d{1,2}(?:,\d{1,2})?)?")
_STYLE_CODE_RE = re.compile(r"[\x02\x0f\x16\x1d\x1f]")


def style(
    text: object,
    *,
    fg: IRCColor | int | None = None,
    bold: bool = False,
    italic: bool = False,
) -> str:
    value = str(text)
    if not value:
        return ""
    prefix = ""
    if bold:
        prefix += BOLD
    if italic:
        prefix += ITALIC
    if fg is not None:
        prefix += f"{COLOR}{int(fg):02d}"
    if not prefix:
        return value
    return f"{prefix}{value}{RESET}"


def color(text: object, fg: IRCColor | int) -> str:
    return style(text, fg=fg)


def bold(text: object) -> str:
    return style(text, bold=True)


def italic(text: object) -> str:
    return style(text, italic=True)


def title(text: object) -> str:
    return style(text, fg=IRCColor.LIGHT_BLUE, bold=True)


def team(text: object, *, home: bool = False) -> str:
    return style(text, bold=True)


def section(text: object) -> str:
    return style(text, italic=True)


def stat_label(text: object) -> str:
    return style(text, italic=True)


def value(text: object) -> str:
    return style(text, bold=True)


def stat_value(text: object) -> str:
    return str(text)


def live(text: object) -> str:
    return style(text, fg=IRCColor.RED, bold=True)


def warning(text: object) -> str:
    return style(text, fg=IRCColor.ORANGE, bold=True)


def muted(text: object) -> str:
    return style(text, fg=IRCColor.GRAY, italic=True)


def error(text: object) -> str:
    return style(text, fg=IRCColor.RED, bold=True)


def strip_irc_formatting(text: str) -> str:
    return _STYLE_CODE_RE.sub("", _COLOR_CODE_RE.sub("", text))


def truncate_irc(text: str, limit: int) -> str:
    if len(strip_irc_formatting(text)) <= limit:
        return text
    suffix = RESET + "..."
    if limit <= len(suffix):
        return "..."[:limit]
    visible_limit = limit - 3
    return _take_visible(text, visible_limit).rstrip() + suffix


def _take_visible(text: str, limit: int) -> str:
    pieces: list[str] = []
    index = 0
    visible = 0
    while index < len(text) and visible < limit:
        if text[index] == COLOR:
            next_index = _color_code_end(text, index)
            pieces.append(text[index:next_index])
            index = next_index
            continue
        if text[index] in {BOLD, RESET, ITALIC, "\x16", "\x1f"}:
            pieces.append(text[index])
            index += 1
            continue
        pieces.append(text[index])
        index += 1
        visible += 1
    return "".join(pieces)


def _color_code_end(text: str, index: int) -> int:
    cursor = index + 1
    for _ in range(2):
        if cursor < len(text) and text[cursor].isdigit():
            cursor += 1
        else:
            break
    if cursor < len(text) and text[cursor] == ",":
        next_cursor = cursor + 1
        for _ in range(2):
            if next_cursor < len(text) and text[next_cursor].isdigit():
                next_cursor += 1
            else:
                break
        if next_cursor > cursor + 1:
            cursor = next_cursor
    return cursor
