import base64
import datetime
import json
import math
import os
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

USERNAME = os.environ["GITHUB_USERNAME"]
DISPLAY_NAME = os.environ.get("DISPLAY_NAME", USERNAME)
TOKEN = os.environ["GITHUB_TOKEN"]
WAKATIME_API_KEY = os.environ.get("WAKATIME_API_KEY", "").strip()

API_URL = "https://api.github.com/graphql"

os.makedirs("profile", exist_ok=True)

now = datetime.datetime.utcnow()
year_ago = now - datetime.timedelta(days=365)

GITHUB_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }

    pullRequests(states: [OPEN, CLOSED, MERGED]) {
      totalCount
    }

    mergedPullRequests: pullRequests(states: [MERGED]) {
      totalCount
    }

    issues(states: [OPEN, CLOSED]) {
      totalCount
    }

    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions

      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }

      commitContributionsByRepository(maxRepositories: 100) {
        repository {
          nameWithOwner
        }
      }

      issueContributionsByRepository(maxRepositories: 100) {
        repository {
          nameWithOwner
        }
      }

      pullRequestContributionsByRepository(maxRepositories: 100) {
        repository {
          nameWithOwner
        }
      }

      pullRequestReviewContributionsByRepository(maxRepositories: 100) {
        repository {
          nameWithOwner
        }
      }
    }
  }
}
"""


def fetch_github_data():
    payload = {
        "query": GITHUB_QUERY,
        "variables": {
            "login": USERNAME,
            "from": year_ago.isoformat() + "Z",
            "to": now.isoformat() + "Z",
        },
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-cards-generator",
        },
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))

    if "errors" in result:
        raise RuntimeError(result["errors"])

    return result["data"]["user"]


def arc_path(cx, cy, r, start_angle, end_angle):
    start = math.radians(start_angle)
    end = math.radians(end_angle)

    x1 = cx + r * math.cos(start)
    y1 = cy + r * math.sin(start)
    x2 = cx + r * math.cos(end)
    y2 = cy + r * math.sin(end)

    large_arc = 1 if end_angle - start_angle > 180 else 0

    return f"M {x1:.2f} {y1:.2f} A {r} {r} 0 {large_arc} 1 {x2:.2f} {y2:.2f}"


def seconds_to_text(seconds):
    seconds = int(seconds or 0)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours > 0 and minutes > 0:
        return f"{hours} hrs {minutes} mins"

    if hours > 0:
        return f"{hours} hrs"

    return f"{minutes} mins"


def calculate_current_streak(days):
    if not days:
        return 0

    today = datetime.datetime.utcnow().date()
    days_by_date = {item["date"]: item["count"] for item in days}

    current_date = today

    if days_by_date.get(current_date, 0) == 0:
        current_date = current_date - datetime.timedelta(days=1)

    streak = 0

    while days_by_date.get(current_date, 0) > 0:
        streak += 1
        current_date = current_date - datetime.timedelta(days=1)

    return streak


def calculate_longest_streak(days):
    longest = 0
    current = 0

    for item in days:
        if item["count"] > 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return longest


def get_language_color(name, fallback="#8B949E"):
    colors = {
        "Java": "#b07219",
        "Go": "#00ADD8",
        "Python": "#3572A5",
        "JavaScript": "#f1e05a",
        "TypeScript": "#3178c6",
        "HTML": "#e34c26",
        "CSS": "#563d7c",
        "Shell": "#89e051",
        "Dockerfile": "#384d54",
        "Kotlin": "#A97BFF",
        "Lua": "#000080",
        "Rust": "#dea584",
        "Vue.js": "#41b883",
        "XML": "#0060ac",
        "YAML": "#cb171e",
        "SQL": "#336791",
    }

    return colors.get(name, fallback)


user = fetch_github_data()

repos = user["repositories"]["nodes"]
repo_count = user["repositories"]["totalCount"]

contributions = user["contributionsCollection"]
calendar = contributions["contributionCalendar"]

total_stars = sum(repo["stargazerCount"] for repo in repos)
total_commits_last_year = contributions["totalCommitContributions"]
total_prs = user["pullRequests"]["totalCount"]
merged_prs = user["mergedPullRequests"]["totalCount"]
merged_prs_percentage = (merged_prs / total_prs * 100) if total_prs else 0
total_issues = user["issues"]["totalCount"]

contributed_repos = set()

for block_name in [
    "commitContributionsByRepository",
    "issueContributionsByRepository",
    "pullRequestContributionsByRepository",
    "pullRequestReviewContributionsByRepository",
]:
    for item in contributions.get(block_name, []):
        repo = item.get("repository")
        if repo and repo.get("nameWithOwner"):
            contributed_repos.add(repo["nameWithOwner"])

contributed_to_last_year = len(contributed_repos)
total_contributions_last_year = calendar["totalContributions"]

contribution_days = []

for week in calendar["weeks"]:
    for day in week["contributionDays"]:
        contribution_days.append(
            {
                "date": datetime.date.fromisoformat(day["date"]),
                "count": day["contributionCount"],
            }
        )

contribution_days.sort(key=lambda item: item["date"])

current_streak = calculate_current_streak(contribution_days)
longest_streak = calculate_longest_streak(contribution_days)

if total_contributions_last_year >= 1000:
    grade = "S"
elif total_contributions_last_year >= 500:
    grade = "A+"
elif total_contributions_last_year >= 300:
    grade = "A"
elif total_contributions_last_year >= 200:
    grade = "A-"
elif total_contributions_last_year >= 100:
    grade = "B+"
elif total_contributions_last_year >= 50:
    grade = "B"
elif total_contributions_last_year >= 25:
    grade = "B-"
else:
    grade = "C"

rank_progress_map = {
    "S": 92,
    "A+": 84,
    "A": 76,
    "A-": 68,
    "B+": 60,
    "B": 52,
    "B-": 44,
    "C": 34,
}

rank_progress = rank_progress_map.get(grade, 34)

language_stats = {}

for repo in repos:
    for edge in repo["languages"]["edges"]:
        lang = edge["node"]["name"]
        color = edge["node"]["color"] or get_language_color(lang)
        size = edge["size"]

        if lang not in language_stats:
            language_stats[lang] = {
                "size": 0,
                "color": color,
            }

        language_stats[lang]["size"] += size

all_languages = sorted(
    language_stats.items(),
    key=lambda item: item[1]["size"],
    reverse=True,
)

total_language_size = sum(item[1]["size"] for item in all_languages) or 1

top_languages = []

for lang, data in all_languages:
    percent = data["size"] / total_language_size * 100

    if percent >= 1:
        top_languages.append((lang, data))

    if len(top_languages) == 5:
        break

if not top_languages:
    top_languages = all_languages[:5]


ICON_PATHS = {
    "stars": "M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25zm0 2.445L6.615 5.5a.75.75 0 01-.564.41l-3.097.45 2.24 2.184a.75.75 0 01.216.664l-.528 3.084 2.769-1.456a.75.75 0 01.698 0l2.77 1.456-.53-3.084a.75.75 0 01.216-.664l2.24-2.183-3.096-.45a.75.75 0 01-.564-.41L8 2.694v.001z",
    "commits": "M1.643 3.143L.427 1.927A.25.25 0 000 2.104V5.75c0 .138.112.25.25.25h3.646a.25.25 0 00.177-.427L2.715 4.215a6.5 6.5 0 11-1.18 4.458.75.75 0 10-1.493.154 8.001 8.001 0 101.6-5.684zM7.75 4a.75.75 0 01.75.75v2.992l2.028.812a.75.75 0 01-.557 1.392l-2.5-1A.75.75 0 017 8.25v-3.5A.75.75 0 017.75 4z",
    "prs": "M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z",
    "merge": "M13.442 2.558a.625.625 0 0 1 0 .884l-10 10a.625.625 0 1 1-.884-.884l10-10a.625.625 0 0 1 .884 0zM4.5 6a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm0 1a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zm7 6a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm0 1a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
    "issues": "M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM0 8a8 8 0 1116 0A8 8 0 010 8zm9 3a1 1 0 11-2 0 1 1 0 012 0zm-.25-6.25a.75.75 0 00-1.5 0v3.5a.75.75 0 001.5 0v-3.5z",
    "contribs": "M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM5 12.25v3.25a.25.25 0 00.4.2l1.45-1.087a.25.25 0 01.3 0L8.6 15.7a.25.25 0 00.4-.2v-3.25a.25.25 0 00-.25-.25h-3.5a.25.25 0 00-.25.25z",
}

stats_rows_data = [
    ("stars", "Total Stars Earned:", str(total_stars)),
    ("commits", "Total Commits (last year):", str(total_commits_last_year)),
]

if total_prs > 0:
    stats_rows_data.append(("prs", "Total PRs:", str(total_prs)))
    stats_rows_data.append(("merge", "Merged PRs Percentage:", f"{merged_prs_percentage:.2f} %"))

if total_issues > 0:
    stats_rows_data.append(("issues", "Total Issues:", str(total_issues)))

stats_rows_data.append(("contribs", "Contributed to (last year):", str(contributed_to_last_year)))

circumference = 2 * math.pi * 40
rank_dashoffset = circumference - (circumference * rank_progress / 100)

stats_rows_svg = []

for index, (icon_key, label, value) in enumerate(stats_rows_data[:6]):
    delay = 450 + index * 150
    row_y = index * 25
    icon_path = ICON_PATHS[icon_key]

    stats_rows_svg.append(
        f'''
        <g transform="translate(0, {row_y})">
          <g class="stagger" style="animation-delay: {delay}ms" transform="translate(25, 0)">
            <svg class="icon" viewBox="0 0 16 16" width="16" height="16">
              <path fill-rule="evenodd" d="{icon_path}"/>
            </svg>

            <text class="stat bold" x="25" y="12.5">{escape(label)}</text>
            <text class="stat bold" x="219.01" y="12.5">{escape(value)}</text>
          </g>
        </g>'''
    )

stats_title = f"{DISPLAY_NAME}'s GitHub Stats, Rank: {grade}"

stats_svg = f'''<svg
  width="467"
  height="220"
  viewBox="0 0 467 220"
  fill="none"
  xmlns="http://www.w3.org/2000/svg"
  role="img"
>
  <title>{escape(stats_title)}</title>

  <style>
    .header {{
      font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #58A6FF;
      animation: fadeInAnimation 0.8s ease-in-out forwards;
    }}

    .stat {{
      font: 600 14px 'Segoe UI', Ubuntu, "Helvetica Neue", Sans-Serif;
      fill: #C3D1D9;
    }}

    .stagger {{
      opacity: 0;
      animation: fadeInAnimation 0.3s ease-in-out forwards;
    }}

    .rank-text {{
      font: 800 24px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #C3D1D9;
      animation: scaleInAnimation 0.3s ease-in-out forwards;
    }}

    .bold {{
      font-weight: 700;
    }}

    .icon {{
      fill: #1F6FEB;
      display: block;
    }}

    .rank-circle-rim {{
      stroke: #58A6FF;
      fill: none;
      stroke-width: 6;
      opacity: 0.2;
    }}

    .rank-circle {{
      stroke: #58A6FF;
      stroke-dasharray: {circumference};
      stroke-dashoffset: {circumference};
      fill: none;
      stroke-width: 6;
      stroke-linecap: round;
      opacity: 0.8;
      transform-origin: -10px 8px;
      transform: rotate(-90deg);
      animation: rankAnimation 1s forwards ease-in-out;
    }}

    @keyframes rankAnimation {{
      from {{ stroke-dashoffset: {circumference}; }}
      to {{ stroke-dashoffset: {rank_dashoffset}; }}
    }}

    @keyframes scaleInAnimation {{
      from {{ transform: translate(-5px, 5px) scale(0); }}
      to {{ transform: translate(-5px, 5px) scale(1); }}
    }}

    @keyframes fadeInAnimation {{
      from {{ opacity: 0; }}
      to {{ opacity: 1; }}
    }}
  </style>

  <rect x="0.5" y="0.5" rx="4.5" height="99%" width="466" fill="#0D1117" stroke="#e4e2e2" stroke-opacity="0" />

  <g transform="translate(25, 35)">
    <text x="0" y="0" class="header">{escape(DISPLAY_NAME)}'s GitHub Stats</text>
  </g>

  <g transform="translate(0, 55)">
    <g transform="translate(390.5, 60)">
      <circle class="rank-circle-rim" cx="-10" cy="8" r="40" />
      <circle class="rank-circle" cx="-10" cy="8" r="40" />
      <g class="rank-text">
        <text x="-5" y="3" alignment-baseline="central" dominant-baseline="central" text-anchor="middle">{escape(grade)}</text>
      </g>
    </g>

    <svg x="0" y="0">
      {''.join(stats_rows_svg)}
    </svg>
  </g>
</svg>'''

language_rows_svg = []
donut_segments_svg = []

start_angle = -90
donut_cx = 116.66666666666667
donut_cy = 116.66666666666667
donut_r = 56.66666666666667

for index, (lang, data) in enumerate(top_languages):
    percent = data["size"] / total_language_size * 100
    color = data["color"]
    row_delay = 450 + index * 150
    donut_delay = 600 + index * 100
    row_y = index * 32

    language_rows_svg.append(
        f'''
        <g transform="translate(0, {row_y})">
          <g class="stagger" style="animation-delay: {row_delay}ms">
            <circle cx="5" cy="6" r="5" fill="{escape(color)}" />
            <text x="15" y="10" class="lang-name">{escape(lang)} {percent:.2f}%</text>
          </g>
        </g>'''
    )

    end_angle = start_angle + percent / 100 * 360
    path_d = arc_path(donut_cx, donut_cy, donut_r, start_angle, end_angle)

    donut_segments_svg.append(
        f'''
        <g class="stagger" style="animation-delay: {donut_delay}ms">
          <path d="{path_d}" stroke="{escape(color)}" fill="none" stroke-width="12"></path>
        </g>'''
    )

    start_angle = end_angle

top_langs_svg = f'''<svg
  width="350"
  height="215"
  viewBox="0 0 350 215"
  fill="none"
  xmlns="http://www.w3.org/2000/svg"
  role="img"
>
  <title>Most Used Languages</title>

  <style>
    .header {{
      font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #58A6FF;
      animation: fadeInAnimation 0.8s ease-in-out forwards;
    }}

    .lang-name {{
      font: 400 11px "Segoe UI", Ubuntu, Sans-Serif;
      fill: #C3D1D9;
    }}

    .stagger {{
      opacity: 0;
      animation: fadeInAnimation 0.3s ease-in-out forwards;
    }}

    @keyframes fadeInAnimation {{
      from {{ opacity: 0; }}
      to {{ opacity: 1; }}
    }}
  </style>

  <rect x="0.5" y="0.5" rx="4.5" height="99%" width="349" fill="#0D1117" stroke="#e4e2e2" stroke-opacity="0" />

  <g transform="translate(25, 35)">
    <text x="0" y="0" class="header">Most Used Languages</text>
  </g>

  <g transform="translate(0, 55)">
    <svg x="25">
      <g transform="translate(0, 0)">
        {''.join(language_rows_svg)}

        <g transform="translate(125, -45)">
          <svg width="350" height="350">
            {''.join(donut_segments_svg)}
          </svg>
        </g>
      </g>
    </svg>
  </g>
</svg>'''


def fetch_wakatime_languages():
    if not WAKATIME_API_KEY:
        return None

    encoded_key = base64.b64encode(WAKATIME_API_KEY.encode("utf-8")).decode("utf-8")

    request = urllib.request.Request(
        "https://wakatime.com/api/v1/users/current/stats/all_time",
        headers={
            "Authorization": f"Basic {encoded_key}",
            "Accept": "application/json",
            "User-Agent": "profile-cards-generator",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None

    data = result.get("data", {})
    languages = data.get("languages", [])

    parsed = []

    for item in languages:
        name = item.get("name")
        seconds = item.get("total_seconds", 0)
        text = item.get("text") or seconds_to_text(seconds)

        if not name or seconds <= 0:
            continue

        parsed.append(
            {
                "name": name,
                "seconds": seconds,
                "text": text,
                "color": get_language_color(name),
            }
        )

    return parsed[:6]


def build_wakatime_svg():
    languages = fetch_wakatime_languages()

    if not languages:
        return '''<svg width="495" height="165" viewBox="0 0 495 165" fill="none" xmlns="http://www.w3.org/2000/svg" role="img">
  <style>
    .header { font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: #58A6FF; }
    .text { font: 500 13px 'Segoe UI', Ubuntu, Sans-Serif; fill: #C3D1D9; }
    .muted { font: 400 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: #8B949E; }
  </style>

  <rect x="0.5" y="0.5" rx="4.5" height="99%" width="494" fill="#0D1117" stroke="#e4e2e2" stroke-opacity="0" />

  <text x="25" y="35" class="header">WakaTime Stats</text>
  <text x="25" y="75" class="text">WakaTime is not connected yet.</text>
  <text x="25" y="100" class="muted">Add WAKATIME_API_KEY to GitHub Actions secrets.</text>
  <text x="25" y="122" class="muted">After that, this card will show real coding time.</text>
</svg>'''

    total_seconds = sum(item["seconds"] for item in languages) or 1

    progress_segments = []
    current_x = 25

    for item in languages:
        width = 440 * item["seconds"] / total_seconds
        progress_segments.append(
            f'''
          <rect
            mask="url(#rect-mask)"
            x="{current_x:.2f}"
            y="0"
            width="{width:.2f}"
            height="8"
            fill="{escape(item["color"])}"
          />'''
        )
        current_x += width

    rows = []

    positions = [
        (25, 25),
        (230, 25),
        (25, 50),
        (230, 50),
        (25, 75),
        (230, 75),
    ]

    for item, (x, y) in zip(languages, positions):
        rows.append(
            f'''
    <g transform="translate({x}, {y})">
      <circle cx="5" cy="6" r="5" fill="{escape(item["color"])}" />
      <text x="15" y="10" class="lang-name">{escape(item["name"])} - {escape(item["text"])}</text>
    </g>'''
        )

    return f'''<svg
  width="495"
  height="165"
  viewBox="0 0 495 165"
  fill="none"
  xmlns="http://www.w3.org/2000/svg"
  role="img"
>
  <style>
    .header {{
      font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #58A6FF;
      animation: fadeInAnimation 0.8s ease-in-out forwards;
    }}

    .lang-name {{
      font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #C3D1D9;
    }}

    #rect-mask rect {{
      animation: slideInAnimation 1s ease-in-out forwards;
    }}

    @keyframes slideInAnimation {{
      from {{ width: 0; }}
      to {{ width: 440px; }}
    }}

    @keyframes fadeInAnimation {{
      from {{ opacity: 0; }}
      to {{ opacity: 1; }}
    }}
  </style>

  <rect x="0.5" y="0.5" rx="4.5" height="99%" width="494" fill="#0D1117" stroke="#e4e2e2" stroke-opacity="0" />

  <g transform="translate(25, 35)">
    <text x="0" y="0" class="header">WakaTime Stats</text>
  </g>

  <g transform="translate(0, 55)">
    <svg x="0" y="0" width="100%">
      <mask id="rect-mask">
        <rect x="25" y="0" width="440" height="8" fill="white" rx="5" />
      </mask>

      {''.join(progress_segments)}
      {''.join(rows)}
    </svg>
  </g>
</svg>'''


def build_streak_svg():
    return f'''<svg
  width="350"
  height="165"
  viewBox="0 0 350 165"
  fill="none"
  xmlns="http://www.w3.org/2000/svg"
  role="img"
>
  <style>
    .header {{
      font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #58A6FF;
      animation: fadeInAnimation 0.8s ease-in-out forwards;
    }}

    .big {{
      font: 800 28px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #F0F6FC;
      text-anchor: middle;
      dominant-baseline: middle;
    }}

    .label {{
      font: 600 11px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #C3D1D9;
      text-anchor: middle;
    }}

    .muted {{
      font: 400 10px 'Segoe UI', Ubuntu, Sans-Serif;
      fill: #8B949E;
      text-anchor: middle;
    }}

    .ring {{
      stroke: #58A6FF;
      fill: none;
      stroke-width: 6;
      stroke-linecap: round;
      opacity: 0.85;
      animation: fadeInAnimation 0.8s ease-in-out forwards;
    }}

    @keyframes fadeInAnimation {{
      from {{ opacity: 0; }}
      to {{ opacity: 1; }}
    }}
  </style>

  <rect x="0.5" y="0.5" rx="4.5" height="99%" width="349" fill="#0D1117" stroke="#e4e2e2" stroke-opacity="0" />

  <g transform="translate(25, 35)">
    <text x="0" y="0" class="header">GitHub Streak</text>
  </g>

  <g transform="translate(70, 95)">
    <text x="0" y="0" class="big">{total_contributions_last_year}</text>
    <text x="0" y="28" class="label">Total Contributions</text>
    <text x="0" y="47" class="muted">last year</text>
  </g>

  <g transform="translate(175, 95)">
    <circle cx="0" cy="-5" r="33" class="ring" />
    <text x="0" y="-5" class="big">{current_streak}</text>
    <text x="0" y="45" class="label">Current Streak</text>
  </g>

  <g transform="translate(285, 95)">
    <text x="0" y="0" class="big">{longest_streak}</text>
    <text x="0" y="28" class="label">Longest Streak</text>
    <text x="0" y="47" class="muted">last year</text>
  </g>
</svg>'''


with open("profile/stats.svg", "w", encoding="utf-8") as file:
    file.write(stats_svg)

with open("profile/top-langs.svg", "w", encoding="utf-8") as file:
    file.write(top_langs_svg)

with open("profile/wakatime.svg", "w", encoding="utf-8") as file:
    file.write(build_wakatime_svg())

with open("profile/streak.svg", "w", encoding="utf-8") as file:
    file.write(build_streak_svg())
