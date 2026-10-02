import json
import math
import os
import urllib.request
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape


USERNAME = (
    os.environ.get("PROFILE_USER")
    or os.environ.get("GITHUB_REPOSITORY_OWNER")
    or "ShengyuWang9"
)

TOKEN = os.environ["GITHUB_TOKEN"]

OUTPUT = Path("assets/contribution-animation.svg")


# -----------------------------
# Layout
# -----------------------------

CELL = 11
GAP = 3
STEP = CELL + GAP

LEFT = 35
TOP = 32
RIGHT = 12
BOTTOM = 16


# -----------------------------
# Animation
#
# sweep + cell transition
# ~= 4.8 seconds in total
# -----------------------------

SWEEP_DURATION = 4.10
CELL_DURATION = 0.62
MAX_ROW_OFFSET = 0.07


QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            weekday
            contributionCount
            contributionLevel
          }
        }
      }
    }
  }
}
"""


LEVEL_CLASS = {
    "NONE": "level-0",
    "FIRST_QUARTILE": "level-1",
    "SECOND_QUARTILE": "level-2",
    "THIRD_QUARTILE": "level-3",
    "FOURTH_QUARTILE": "level-4",
}


def get_calendar():
    payload = json.dumps(
        {
            "query": QUERY,
            "variables": {
                "login": USERNAME
            },
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "animated-github-profile",
        },
    )

    with urllib.request.urlopen(request) as response:
        result = json.load(response)

    if "errors" in result:
        raise RuntimeError(result["errors"])

    user = result["data"]["user"]

    if user is None:
        raise RuntimeError(f"GitHub user not found: {USERNAME}")

    return user["contributionsCollection"]["contributionCalendar"]


def sweep_delay(week_index: int, week_count: int) -> float:
    """
    Slow -> fast -> slow.

    Instead of giving every column the same time gap,
    this maps the horizontal position onto an ease-in-out
    time curve.
    """

    if week_count <= 1:
        return 0.0

    progress = week_index / (week_count - 1)

    eased_time = math.acos(1 - 2 * progress) / math.pi

    return eased_time * SWEEP_DURATION


def row_offset(week_index: int, weekday: int) -> float:
    """
    Tiny deterministic offset inside one week.

    Prevents the graph from looking like a perfectly
    straight scanner line.
    """

    value = (week_index * 17 + weekday * 37) % 8

    return (value / 7) * MAX_ROW_OFFSET


def month_labels(weeks):
    labels = []
    seen_months = set()

    for week_index, week in enumerate(weeks):
        days = week["contributionDays"]

        if not days:
            continue

        for day_data in days:
            current_date = date.fromisoformat(
                day_data["date"]
            )

            month_key = (
                current_date.year,
                current_date.month,
            )

            # Only label a month in the week where
            # that month actually begins.
            if (
                current_date.day <= 7
                and month_key not in seen_months
            ):
                x = LEFT + week_index * STEP

                labels.append(
                    f'<text class="month" '
                    f'x="{x}" y="14">'
                    f'{current_date.strftime("%b")}'
                    f"</text>"
                )

                seen_months.add(month_key)
                break

    return "\n".join(labels)


def weekday_labels():
    labels = []

    for weekday, text in [
        (1, "Mon"),
        (3, "Wed"),
        (5, "Fri"),
    ]:
        y = TOP + weekday * STEP + 9

        labels.append(
            f'<text class="weekday" x="0" y="{y}">{text}</text>'
        )

    return "\n".join(labels)


def generate_svg(calendar):
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    width = LEFT + len(weeks) * STEP + RIGHT
    height = TOP + 7 * STEP + BOTTOM

    cells = []

    for week_index, week in enumerate(weeks):

        x = LEFT + week_index * STEP

        base_delay = sweep_delay(
            week_index,
            len(weeks),
        )

        for day_data in week["contributionDays"]:

            weekday = day_data["weekday"]

            y = TOP + weekday * STEP

            level = LEVEL_CLASS[
                day_data["contributionLevel"]
            ]

            delay = (
                base_delay
                + row_offset(
                    week_index,
                    weekday,
                )
            )

            contribution_count = day_data[
                "contributionCount"
            ]

            contribution_date = escape(
                day_data["date"]
            )

            cells.append(
                f"""
<rect
    class="day {level}"
    x="{x}"
    y="{y}"
    width="{CELL}"
    height="{CELL}"
    rx="2"
    style="--delay:{delay:.3f}s"
>
    <title>{contribution_date}: {contribution_count} contributions</title>
</rect>
"""
            )

    svg = f"""\
<svg
    xmlns="http://www.w3.org/2000/svg"
    width="{width}"
    height="{height}"
    viewBox="0 0 {width} {height}"
    role="img"
    aria-label="{total} contributions in the last year"
>

<style>

text {{
    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Helvetica,
        Arial,
        sans-serif;
}}

.month,
.weekday {{
    fill: #57606a;
    font-size: 10px;
}}

.day {{
    opacity: 0;

    --hint-1: #dafbe1;
    --hint-2: #9be9a8;

    animation-duration: {CELL_DURATION}s;
    animation-delay: var(--delay);
    animation-timing-function:
        cubic-bezier(.65, 0, .35, 1);
    animation-fill-mode: forwards;
}}

.level-0 {{
    --target: #ebedf0;
    animation-name: reveal-empty;
}}

.level-1 {{
    --target: #9be9a8;
    animation-name: reveal-green;
}}

.level-2 {{
    --target: #40c463;
    animation-name: reveal-green;
}}

.level-3 {{
    --target: #30a14e;
    animation-name: reveal-green;
}}

.level-4 {{
    --target: #216e39;
    animation-name: reveal-green;
}}


@keyframes reveal-empty {{

    0% {{
        opacity: 0;
        fill: transparent;
    }}

    100% {{
        opacity: 1;
        fill: var(--target);
    }}

}}


@keyframes reveal-green {{

    0% {{
        opacity: 0;
        fill: transparent;
    }}

    20% {{
        opacity: 1;
        fill: var(--hint-1);
    }}

    60% {{
        opacity: 1;
        fill: var(--hint-2);
    }}

    100% {{
        opacity: 1;
        fill: var(--target);
    }}

}}


@media (prefers-color-scheme: dark) {{

    .month,
    .weekday {{
        fill: #8c959f;
    }}

    .day {{
        --hint-1: #0e4429;
        --hint-2: #006d32;
    }}

    .level-0 {{
        --target: #161b22;
    }}

    .level-1 {{
        --target: #0e4429;
    }}

    .level-2 {{
        --target: #006d32;
    }}

    .level-3 {{
        --target: #26a641;
    }}

    .level-4 {{
        --target: #39d353;
    }}

}}

</style>

{month_labels(weeks)}

{weekday_labels()}

{"".join(cells)}

</svg>
"""

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        svg,
        encoding="utf-8",
    )

    print(
        f"Generated animation for {USERNAME}: "
        f"{total} contributions"
    )


if __name__ == "__main__":
    calendar = get_calendar()

    generate_svg(calendar)