#!/usr/bin/env python3
"""Generate a complete, labeled 3D GitHub contribution timeline as an SVG."""
import datetime as dt
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ["USERNAME"]
API = "https://api.github.com/graphql"
QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    createdAt
    contributionsCollection(from:$from,to:$to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

def request(year):
    payload = json.dumps({"query":QUERY,"variables":{
        "login":USERNAME,
        "from":f"{year}-01-01T00:00:00Z",
        "to":f"{year}-12-31T23:59:59Z"}}).encode()
    req = Request(API, payload, {"Authorization":f"Bearer {TOKEN}",
                                "Content-Type":"application/json",
                                "User-Agent":"profile-3d-timeline"})
    with urlopen(req, timeout=45) as response:
        data = json.load(response)
    if data.get("errors"):
        raise RuntimeError(str(data["errors"]))
    return data["data"]["user"]

today = dt.date.today()
current = request(today.year)
created = dt.date.fromisoformat(current["createdAt"][:10])
by_year = {today.year:current}
for year in range(created.year, today.year):
    by_year[year] = request(year)

days = {}
for year, user in by_year.items():
    for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
        for day in week["contributionDays"]:
            d = dt.date.fromisoformat(day["date"])
            if created <= d <= today:
                days[d] = int(day["contributionCount"])

# An architectural contribution city: seven daily rows per week, 2024 onward.
start_date = max(created, dt.date(2024, 1, 1))
first_sunday = start_date - dt.timedelta(days=(start_date.weekday()+1) % 7)
last_week = (today-first_sunday).days // 7
ns = "http://www.w3.org/2000/svg"
ET.register_namespace("", ns)
def date_label(d):
    return f"{d.strftime('%B')} {d.day}, {d.year}"
def add(parent, tag, attrs=None, text=None):
    node = ET.SubElement(parent, f"{{{ns}}}{tag}", attrs or {})
    if text is not None:
        node.text = str(text)
    return node

# A wide, shallow city strip; GitHub scales it to the README width.
step = 25
width = 180 + (last_week + 1)*step
height = 420
root = ET.Element(f"{{{ns}}}svg", {
    "viewBox": f"0 0 {width} {height}", "width": str(width),
    "height": str(height), "role": "img",
    "aria-label": f"3D contribution city from {date_label(start_date)} to {date_label(today)}"
})
add(root, "title", text=f"Contribution History: {date_label(start_date)} – {date_label(today)}")
add(root, "style", text="""
.label {font:600 24px system-ui,sans-serif;fill:#475569}
.range {font:500 22px system-ui,sans-serif;fill:#64748b}
.year {font:600 23px system-ui,sans-serif;fill:#475569}
""")
add(root, "rect", {"width":str(width),"height":str(height),"fill":"#f8fafc"})
add(root, "text", {"x":"75","y":"44","class":"label"}, "CONTRIBUTION HISTORY")
add(root, "text", {"x":str(width-65),"y":"44","class":"range","text-anchor":"end"},
    f"{date_label(start_date)} – {date_label(today)}")
# Pale isometric ground plane.
add(root,"polygon",{"points":f"62,289 {width-72},289 {width-30},365 104,365",
                    "fill":"#e2e8f0"})
for week in range(last_week+1):
    for day in range(7):
        date = first_sunday + dt.timedelta(days=week*7+day)
        if date < start_date or date > today:
            continue
        count = days.get(date,0)
        x = 72 + week*step + day*4.2
        y = 285 + day*9.5
        # Tall skyscrapers for high-activity days; low-rise for ordinary days.
        h = 3 if count == 0 else min(160, 10 + 12*(count**0.68))
        w = 12
        depth = 5
        if count == 0:
            front, side, roof = "#cbd5e1","#b6c3d1","#e2e8f0"
        elif count < 3:
            front, side, roof = "#54718e","#334e6c","#7996b4"
        elif count < 8:
            front, side, roof = "#355575","#233e60","#6084a9"
        else:
            front, side, roof = "#213b60","#172d4c","#426b9c"
        def poly(points,fill):
            add(root,"polygon",{"points":" ".join(f"{px:.1f},{py:.1f}" for px,py in points),
                                "fill":fill})
        # Left/front face, right side and roof are separate architectural planes.
        poly([(x,y-h),(x+w,y-h),(x+w,y),(x,y)],front)
        poly([(x+w,y-h),(x+w+depth,y-h-depth*0.65),
              (x+w+depth,y-depth*0.65),(x+w,y)],side)
        poly([(x,y-h),(x+depth,y-h-depth*0.65),
              (x+w+depth,y-h-depth*0.65),(x+w,y-h)],roof)
        # Illuminated windows, aligned into recognizable building facades.
        if count:
            floors = int(max(0,h-9)//9)
            for floor in range(floors):
                wy = y-h+7+floor*9
                for column in range(2):
                    if (week*11+day*7+floor*3+column)%5 != 0:
                        add(root,"rect",{"x":f"{x+2+column*5:.1f}","y":f"{wy:.1f}",
                            "width":"2.5","height":"3.4","fill":"#8ed9f3",
                            "opacity":"0.88"})
# Date ticks on the street edge, unobstructed by buildings.
for year in range(start_date.year,today.year+1):
    date = max(start_date,dt.date(year,1,1))
    week = (date-first_sunday).days//7
    x = 80 + week*step
    add(root,"line",{"x1":str(x),"y1":"370","x2":str(x),"y2":"390",
                     "stroke":"#94a3b8","stroke-width":"1.5"})
    add(root,"text",{"x":str(x+5),"y":"412","class":"year"},date_label(date))
Path("profile-3d-contrib").mkdir(exist_ok=True)
ET.ElementTree(root).write("profile-3d-contrib/skyline-clean.svg",
                           encoding="unicode",xml_declaration=True)
print(f"Generated architectural city {date_label(start_date)} to {date_label(today)}")
