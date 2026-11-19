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
step = 22
width = 180 + (last_week + 1)*step
height = 610
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
add(root,"polygon",{"points":f"62,305 {width-72},305 {width-10},515 90,515",
                    "fill":"#e2e8f0"})
for day in range(7):
    for week in range(last_week+1):
        date = first_sunday + dt.timedelta(days=week*7+day)
        if date < start_date or date > today:
            continue
        count = days.get(date,0)
        x = 72 + week*step + day*4.0
        y = 315 + day*28
        # Contiguous isometric lots, including inactive days.
        add(root,"polygon",{"points":f"{x:.1f},{y:.1f} {x+step:.1f},{y:.1f} {x+step+15:.1f},{y-10:.1f} {x+15:.1f},{y-39:.1f}",
            "fill":"#dbe4ed","stroke":"#cbd5e1","stroke-width":"0.35"})
        # Tall skyscrapers for high-activity days; low-rise for ordinary days.
        h = 1.5 if count == 0 else min(195, 16 + 17*(count**0.68))
        w = 20
        depth = 15
        palettes = [
            ("#536b85", "#30445d", "#7891aa"),
            ("#395c79", "#243f5c", "#6f91af"),
            ("#4b7186", "#315366", "#8aabba"),
            ("#53647d", "#34455e", "#8b9ab0"),
            ("#466f7c", "#28525e", "#81a6af"),
            ("#64748b", "#475569", "#94a3b8"),
            ("#3e597b", "#283e5d", "#718bac"),
        ]
        front, side, roof = palettes[(week*7 + day*11) % len(palettes)]
        if count == 0:
            front, side, roof = "#cbd5e1", "#aebfce", "#e2e8f0"
        def poly(points,fill):
            add(root,"polygon",{"points":" ".join(f"{px:.1f},{py:.1f}" for px,py in points),
                                "fill":fill})
        # Draw rear-to-front, with disjoint footprints and roof always on top.
        poly([(x,y-h),(x+w,y-h),(x+w,y),(x,y)],front)
        poly([(x+w,y-h),(x+w+depth,y-h-depth*0.65),
              (x+w+depth,y-depth*0.65),(x+w,y)],side)
        poly([(x,y-h),(x+depth,y-h-depth*0.65),
              (x+w+depth,y-h-depth*0.65),(x+w,y-h)],roof)
        # Window strips on BOTH exposed faces, kept inside the building geometry.
        if count:
            floors = int(max(0,h-14)//12)
            for floor in range(floors):
                wy = y-h+9+floor*12
                for column in range(3):
                    if (week*11+day*7+floor*3+column)%5 != 0:
                        add(root,"rect",{"x":f"{x+3+column*5:.1f}","y":f"{wy:.1f}",
                            "width":"2.8","height":"4.2","fill":"#a4e2f2",
                            "opacity":"0.9"})
                # Side-face windows follow the slanted facade as parallelograms.
                if (week*3+day*5+floor*2)%4 != 0:
                    wx = x+w+2.2
                    wy_side = wy-2.2
                    poly([(wx,wy_side),(wx+2.3,wy_side-1.5),
                          (wx+2.3,wy_side+2.8),(wx,wy_side+4.3)],"#7ac6e5")
# Date ticks on the street edge, unobstructed by buildings.
for year in range(start_date.year,today.year+1):
    date = max(start_date,dt.date(year,1,1))
    week = (date-first_sunday).days//7
    x = 80 + week*step
    add(root,"line",{"x1":str(x),"y1":"532","x2":str(x),"y2":"552",
                     "stroke":"#94a3b8","stroke-width":"1.5"})
    add(root,"text",{"x":str(x+5),"y":"583","class":"year"},date_label(date))
Path("profile-3d-contrib").mkdir(exist_ok=True)
ET.ElementTree(root).write("profile-3d-contrib/skyline-clean.svg",
                           encoding="unicode",xml_declaration=True)
print(f"Generated architectural city {date_label(start_date)} to {date_label(today)}")
