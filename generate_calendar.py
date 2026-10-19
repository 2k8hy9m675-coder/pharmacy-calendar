#!/usr/bin/env python3

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


# =========================================================
# SETTINGS
# =========================================================

SUPABASE_URL = "https://elmxwpwhyewgjlvoadtb.supabase.co"
SUPABASE_KEY = "sb_publishable_yUCov2V1dKGEc-rBwt6v2A_dBkHEiYd"

PROGRAM = "Магистер по фармација 2021"

ACADEMIC_START = "2026-10-01"
ACADEMIC_END = "2027-09-30"

# If an isolated database row exists, treat it as one academic hour.
SINGLE_ROW_DURATION_HOURS = 1


# =========================================================
# DOWNLOAD ALL EVENTS - WITH PAGINATION
# =========================================================

def api_get_all(path, params):
    all_data = []
    offset = 0
    page_size = 1000

    while True:
        page_params = dict(params)
        page_params["limit"] = str(page_size)
        page_params["offset"] = str(offset)

        query = urllib.parse.urlencode(
            page_params,
            safe="(),.*"
        )

        url = f"{SUPABASE_URL}/rest/v1/{path}?{query}"

        request = urllib.request.Request(
            url,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Accept": "application/json",
            },
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

        all_data.extend(data)

        print(
            f"Downloaded page: "
            f"{offset}–{offset + len(data)}"
        )

        if len(data) < page_size:
            break

        offset += page_size

    print(
        f"TOTAL DATABASE EVENTS DOWNLOADED: "
        f"{len(all_data)}"
    )

    return all_data


# =========================================================
# HELPERS
# =========================================================

def norm(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip().lower()
    )


def group_matches(groups_text, wanted_group):
    """
    Accept:
    - exact group
    - multiple groups containing our group
    - events for all groups
    - events without a group (usually common lectures)
    """

    text = norm(groups_text)

    if not text:
        return True

    if (
        "сите" in text
        or "all" in text
    ):
        return True

    numbers = {
        int(x)
        for x in re.findall(r"\d+", text)
    }

    return wanted_group in numbers


def subject_match(subject_name):
    """
    Returns our group number if this is one
    of the four wanted subjects.
    """

    name = norm(subject_name)

    # Never include Pharmaceutical Chemistry 3
    if (
        "фармацевтска хемија" in name
        and "3" in name
    ):
        return None

    # Pharmacognosy - semester 5
    if "фармакогнозија" in name:
        return 3

    # Biopharmacy
    if "биофармација" in name:
        return 3

    # Food and Nutrition
    if "храна и исхрана" in name:
        return 1

    # Pharmaceutical Technology - Advanced Level
    if (
        "фармацевтска технологија" in name
        and (
            "напред" in name
            or "advanced" in name
        )
    ):
        return 4

    return None


def escape_ics(value):
    value = str(value or "")

    return (
        value
        .replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\n", r"\n")
    )


def fold_line(line):
    """
    Fold long ICS lines while remaining safe
    for UTF-8 Macedonian characters.
    """

    output = []
    current = ""

    for char in line:

        candidate = current + char

        if len(candidate.encode("utf-8")) > 70:
            output.append(current)
            current = " " + char
        else:
            current = candidate

    output.append(current)

    return "\r\n".join(output)


def get_name(value):
    """
    Supabase relation can occasionally arrive
    as object or list.
    """

    if isinstance(value, list):
        if not value:
            return ""
        value = value[0]

    if isinstance(value, dict):
        return value.get("name") or ""

    return ""


# =========================================================
# QUERY DATABASE
# =========================================================

params = {
    "select": (
        "id,"
        "event_date,"
        "event_time,"
        "type,"
        "groups_text,"
        "subjects("
            "name,"
            "semester,"
            "programs(name)"
        "),"
        "professors(name),"
        "rooms(name)"
    ),

    "event_date": f"gte.{ACADEMIC_START}",

    "order": (
        "event_date.asc,"
        "event_time.asc"
    ),
}


events = api_get_all(
    "events",
    params
)


# =========================================================
# FILTER PERSONAL SCHEDULE
# =========================================================

selected = []

for event in events:

    date = str(
        event.get("event_date") or ""
    )[:10]

    if not date:
        continue

    if date < ACADEMIC_START:
        continue

    if date > ACADEMIC_END:
        continue


    subject = event.get("subjects") or {}

    if isinstance(subject, list):
        subject = subject[0] if subject else {}


    program = subject.get("programs") or {}

    if isinstance(program, list):
        program = program[0] if program else {}


    program_name = program.get("name") or ""

    if norm(program_name) != norm(PROGRAM):
        continue


    subject_name = subject.get("name") or ""

    wanted_group = subject_match(
        subject_name
    )

    if wanted_group is None:
        continue


    if not group_matches(
        event.get("groups_text"),
        wanted_group
    ):
        continue


    professor = get_name(
        event.get("professors")
    )

    room = get_name(
        event.get("rooms")
    )


    time_string = str(
        event.get("event_time")
        or "08:00"
    )[:5]


    try:

        start = datetime.strptime(
            f"{date} {time_string}",
            "%Y-%m-%d %H:%M"
        )

    except ValueError:

        print(
            "Skipping invalid date/time:",
            date,
            time_string
        )

        continue


    selected.append({

        "id":
            event.get("id"),

        "subject":
            subject_name,

        "semester":
            subject.get("semester"),

        "group":
            wanted_group,

        "type":
            event.get("type") or "",

        "professor":
            professor,

        "room":
            room,

        "groups_text":
            event.get("groups_text") or "",

        "start":
            start,
    })


selected.sort(
    key=lambda x: x["start"]
)

print(
    f"PERSONAL ROWS FOUND: "
    f"{len(selected)}"
)


# =========================================================
# MERGE CONSECUTIVE HOURLY ROWS
# =========================================================

def merge_key(event):

    return (

        event["start"].date(),

        norm(event["subject"]),

        norm(event["type"]),

        norm(event["professor"]),

        norm(event["room"]),

        event["group"],
    )


grouped = {}

for event in selected:

    key = merge_key(event)

    grouped.setdefault(
        key,
        []
    ).append(event)


merged = []


for key, rows in grouped.items():

    rows.sort(
        key=lambda x: x["start"]
    )

    current = None


    for row in rows:

        row_start = row["start"]

        row_end = (
            row_start
            + timedelta(
                hours=SINGLE_ROW_DURATION_HOURS
            )
        )


        if current is None:

            current = {
                **row,
                "end": row_end,
                "ids": [row["id"]],
            }

            continue


        # Merge if next database row starts exactly
        # when the previous academic hour ends.

        if row_start == current["end"]:

            current["end"] = row_end

            current["ids"].append(
                row["id"]
            )

        else:

            merged.append(current)

            current = {
                **row,
                "end": row_end,
                "ids": [row["id"]],
            }


    if current is not None:
        merged.append(current)


merged.sort(
    key=lambda x: x["start"]
)


print(
    f"CALENDAR BLOCKS AFTER MERGING: "
    f"{len(merged)}"
)


# =========================================================
# GENERATE ICS
# =========================================================

now = datetime.now(
    timezone.utc
).strftime(
    "%Y%m%dT%H%M%SZ"
)


calendar_lines = [

    "BEGIN:VCALENDAR",

    "VERSION:2.0",

    "PRODID:-//Personal UKIM Pharmacy Schedule//MK",

    "CALSCALE:GREGORIAN",

    "METHOD:PUBLISH",

    "X-WR-CALNAME:Фармација – мој распоред",

    "X-WR-TIMEZONE:Europe/Skopje",

    "REFRESH-INTERVAL;VALUE=DURATION:PT1H",

    "X-PUBLISHED-TTL:PT1H",
]


for event in merged:

    start = event["start"]
    end = event["end"]


    # Stable UID so Apple Calendar updates the same
    # event instead of creating duplicates.

    uid_source = (
        f"{start.strftime('%Y%m%d-%H%M')}-"
        f"{norm(event['subject'])}-"
        f"{norm(event['type'])}-"
        f"{event['group']}"
    )

    uid_safe = re.sub(
        r"[^a-zA-Z0-9_-]",
        "-",
        uid_source
    )


    description = "\n".join([

        f"Тип: {event['type']}",

        f"Проф/асистент: "
        f"{event['professor']}",

        f"Група: "
        f"{event['group']}",

        f"Семестар: "
        f"{event['semester']}",
    ])


    calendar_lines.extend([

        "BEGIN:VEVENT",

        (
            f"UID:{uid_safe}"
            "@2k8hy9m675-coder.github.io"
        ),

        f"DTSTAMP:{now}",

        (
            "DTSTART;TZID=Europe/Skopje:"
            f"{start.strftime('%Y%m%dT%H%M%S')}"
        ),

        (
            "DTEND;TZID=Europe/Skopje:"
            f"{end.strftime('%Y%m%dT%H%M%S')}"
        ),

        (
            "SUMMARY:"
            f"{escape_ics(event['subject'])}"
        ),

        (
            "LOCATION:"
            f"{escape_ics(event['room'])}"
        ),

        (
            "DESCRIPTION:"
            f"{escape_ics(description)}"
        ),

        "STATUS:CONFIRMED",

        "END:VEVENT",
    ])


calendar_lines.append(
    "END:VCALENDAR"
)


ics_text = (
    "\r\n".join(
        fold_line(line)
        for line in calendar_lines
    )
    + "\r\n"
)


Path(
    "schedule.ics"
).write_bytes(
    ics_text.encode("utf-8")
)


print(
    f"SUCCESS: schedule.ics generated "
    f"with {len(merged)} calendar events."
)

if merged:

    print(
        "First event:",
        merged[0]["start"],
        merged[0]["subject"]
    )

    print(
        "Last event:",
        merged[-1]["start"],
        merged[-1]["subject"]
    )
