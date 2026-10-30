"""Resolve faithful source excerpts and measured narration holds before capture."""

from __future__ import annotations

import copy
import math
from pathlib import Path

import align_narration


def line_range(value: object, total: int, label: str) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(n) is not int for n in value)
        or not 1 <= value[0] <= value[1] <= total
    ):
        raise ValueError(
            f"{label} must be an inclusive [first, last] source-line range within 1–{total}"
        )
    return value[0], value[1]


def cue_time(cue: object, timing: dict, *, end: bool = False) -> float:
    offset = float(timing.get("narration_offset_seconds", 0.15))
    options: dict = cue if isinstance(cue, dict) else {"phrase": cue}
    if "at" in options:
        return float(str(options["at"])) + offset
    match = align_narration.find_phrase(
        timing["words"], str(options["phrase"]), int(options.get("occurrence", 1))
    )
    return float(match["end" if end else "start"]) + offset


def prepare_actions(
    actions: list[dict],
    app_dir: Path,
    timing: dict | None = None,
    *,
    resolve_holds: bool = True,
) -> list[dict]:
    """Keep old text/duration actions intact; resolve new source and hold fields."""
    result = copy.deepcopy(actions)
    for index, action in enumerate(result):
        if not isinstance(action, dict) or not isinstance(action.get("code"), dict):
            continue
        code = action["code"]
        if "source_lines" in code:
            if any(key in code for key in ("text", "before", "after")):
                raise ValueError("Use source_lines or copied code text, not both")
            name = code.get("source_file") or (
                "app.py" if (app_dir / "app.py").is_file() else "app.R"
            )
            path = (app_dir / name).resolve()
            if Path(name).is_absolute() or not path.is_relative_to(app_dir.resolve()):
                raise ValueError("Code source_file must stay inside the app directory")
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError) as exc:
                raise ValueError(f"Cannot read source excerpt {name}: {exc}") from exc
            first, last = line_range(
                code.pop("source_lines"), len(lines), "source_lines"
            )
            low, high = line_range(
                code.pop("highlight_lines", [first, last]),
                len(lines),
                "highlight_lines",
            )
            if not first <= low <= high <= last:
                raise ValueError("highlight_lines must stay inside source_lines")
            code.update(
                source_file=str(name),
                start_line=first,
                before="\n".join(lines[first - 1 : low - 1]),
                text="\n".join(lines[low - 1 : high]),
                after="\n".join(lines[high:last]),
                _source_lines=lines[first - 1 : last],
                _focus_range=[low - first, high - first + 1],
            )
        if "hold_until" not in code or not resolve_holds:
            continue
        if timing is None:
            raise ValueError(
                "hold_until needs measured narration timing; use --preview-states before audio exists"
            )
        if index == 0 or "cue" not in result[index - 1]:
            raise ValueError(
                "hold_until needs a cue immediately before its code action"
            )
        if "duration" in code:
            raise ValueError("Use hold_until or duration, not both")
        pause = code.pop("reading_pause", 2.0)
        if (
            isinstance(pause, bool)
            or not isinstance(pause, (float, int))
            or not math.isfinite(pause)
            or pause < 0
        ):
            raise ValueError(
                "reading_pause must be a finite, nonnegative number of seconds"
            )
        start = cue_time(result[index - 1]["cue"], timing)
        finish = cue_time(code.pop("hold_until"), timing, end=True) + pause
        if finish <= start:
            raise ValueError("hold_until must end after the code reveal")
        following = next(
            (item["cue"] for item in result[index + 1 :] if "cue" in item), None
        )
        if following is not None:
            next_start = cue_time(following, timing)
            if finish > next_start + 1 / 30:
                raise ValueError(
                    f"Code action {index+1}: explanation and reading pause overlap the next narration cue; revise the narration or action plan"
                )
            finish = min(finish, next_start)
        code["_hold_end"] = finish
        code["duration"] = round((finish - start) * 1000)
    return result
