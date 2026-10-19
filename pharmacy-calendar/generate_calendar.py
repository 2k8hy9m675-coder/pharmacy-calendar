#!/usr/bin/env python3
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SUPABASE_URL = "https://elmxwpwhyewgjlvoadtb.supabase.co"
SUPABASE_KEY = "sb_publishable_yUCov2V1dKGEc-rBwt6v2A_dBkHEiYd"
PROGRAM = "Магистер по фармација 2021"

# Personal timetable:
# subject search text -> required group
WANTED = {
    "фармакогнозија": 3,
    "фармацевтска технологија": 4,  # advanced-level subject; see subject_match()
    "биофармација": 3,
    "храна и исхрана": 1,
}

ACADEMIC_START = "2026-10-01"
ACADEMIC_END = "2027-09-30"
DEFAULT_DURATION_HOURS = 2

def api_get(path, params):
    url = f"{SUPABASE_URL}/rest/v1/{path}?{urllib.parse.urlencode(params, safe='(),.*')}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def group_matches(groups_text, group_no):
    """Include exact/multi-group matches and events explicitly applying to everyone."""
    s = norm(str(groups_text or ""))
    if not s:
        # Empty group is usually a common lecture/event, so include it.
        return True
    if any(x in s for x in ("сите", "all", "сите групи")):
        return True
    nums = {int(x) for x in re.findall(r"\d+", s)}
    return group_no in nums

def subject_match(name):
    n = norm(name)
    if "фармакогнозија" in n:
        return ("фармакогнозија", 3)
    if "биофармација" in n:
        return ("биофармација", 3)
    if "храна и исхрана" in n:
        return ("храна и исхрана", 1)
    # Deliberately require the advanced-level wording and never include Pharmaceutical Chemistry 3.
    if "фармацевтска технологија" in n and ("напред" in n or "advanced" in n):
        return ("фармацевтска технологија", 4)
    return None

def esc(s):
    s = str(s or "")
    return s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")

def fold(line):
    # RFC 5545 recommends max 75 octets; conservative Unicode-aware folding.
    out, cur = [], ""
    for ch in line:
        candidate = cur + ch
        if len(candidate.encode("utf-8")) > 70:
            out.append(cur)
            cur = " " + ch
        else:
            cur = candidate
    out.append(cur)
    return "\r\n".join(out)

params = {
    "select": "id,event_date,event_time,type,groups_text,subjects(name,semester,programs(name)),professors(name),rooms(name)",
    "event_date": f"gte.{ACADEMIC_START}",
    "order": "event_date.asc,event_time.asc",
    "limit": "10000",
}
events = api_get("events", params)

selected = []
for e in events:
    date = str(e.get("event_date") or "")[:10]
    if not (ACADEMIC_START <= date <= ACADEMIC_END):
        continue
    subject = e.get("subjects") or {}
    program = subject.get("programs") or {}
    if norm(program.get("name")) != norm(PROGRAM):
        continue

    match = subject_match(subject.get("name"))
    if not match:
        continue
    _, group_no = match
    if not group_matches(e.get("groups_text"), group_no):
        continue
    selected.append((e, group_no))

now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
lines = [
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

for e, group_no in selected:
    subject = e.get("subjects") or {}
    professor = e.get("professors") or {}
    room = e.get("rooms") or {}
    date = str(e["event_date"])[:10].replace("-", "")
    t = str(e.get("event_time") or "08:00")[:5].replace(":", "")
    start = datetime.strptime(date + t, "%Y%m%d%H%M")
    end = start + timedelta(hours=DEFAULT_DURATION_HOURS)
    uid = f"ukim-{e.get('id')}@2k8hy9m675-coder.github.io"
    desc_parts = [
        f"Тип: {e.get('type') or ''}",
        f"Проф/асистент: {professor.get('name') or ''}",
        f"Група: {group_no}",
        f"Семестар: {subject.get('semester') or ''}",
    ]
    lines += [
        "BEGIN:VEVENT",
        f"UID:{esc(uid)}",
        f"DTSTAMP:{now}",
        f"DTSTART;TZID=Europe/Skopje:{start.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND;TZID=Europe/Skopje:{end.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:{esc(subject.get('name'))}",
        f"LOCATION:{esc(room.get('name'))}",
        f"DESCRIPTION:{esc(chr(10).join(desc_parts))}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
    ]

lines.append("END:VCALENDAR")
Path("schedule.ics").write_bytes(("\r\n".join(fold(x) for x in lines) + "\r\n").encode("utf-8"))
print(f"Generated schedule.ics with {len(selected)} events.")
