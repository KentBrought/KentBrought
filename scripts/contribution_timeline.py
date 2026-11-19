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

# Compact buildings on a dense, 14-row isometric grid.
# Each real contribution day is rendered as two visual lots, not two days.
step = 20
width = 170 + (last_week + 1)*step
height = 540
root = ET.Element(f"{{{ns}}}svg", {
    "viewBox": f"0 0 {width} {height}", "width": str(width),
    "height": str(height), "role": "img",
    "aria-label": f"3D contribution city from {date_label(start_date)} to {date_label(today)}"
})
add(root,"title",text=f"Contribution History: {date_label(start_date)} – {date_label(today)}")
add(root,"style",text="""
.label {font:600 24px system-ui,sans-serif;fill:#475569}
.range {font:500 22px system-ui,sans-serif;fill:#64748b}
.year {font:600 22px system-ui,sans-serif;fill:#475569}
""")
add(root,"rect",{"width":str(width),"height":str(height),"fill":"#f8fafc"})
add(root,"text",{"x":"65","y":"42","class":"label"},"CONTRIBUTION HISTORY")
add(root,"text",{"x":str(width-60),"y":"42","class":"range","text-anchor":"end"},
    f"{date_label(start_date)} – {date_label(today)}")
palettes = [
    ("#536b85","#30445d","#7891aa"),
    ("#395c79","#243f5c","#6f91af"),
    ("#4b7186","#315366","#8aabba"),
    ("#53647d","#34455e","#8b9ab0"),
    ("#466f7c","#28525e","#81a6af"),
    ("#64748b","#475569","#94a3b8"),
    ("#3e597b","#283e5d","#718bac")
]
def poly(points,fill):
    add(root,"polygon",{"points":" ".join(f"{px:.2f},{py:.2f}" for px,py in points),"fill":fill})
# Twenty-nine tightly packed visual rows (15 more than before), using the same seven daily counts.
for row in range(29):
    day = min(6, row * 7 // 29)
    variant = row % 4
    for week in range(last_week+1):
        date = first_sunday + dt.timedelta(days=week*7+day)
        if not start_date <= date <= today:
            continue
        count = days.get(date,0)
        # Each daily count drives both small buildings in its day.
        x = 70 + week*step + row*1.1
        y = 190 + row*7.2
        w,depth,slant = 18.0, 8.0, 5.2
        h = 2 if count == 0 else min(115, 8+11*(count**0.58))
        h *= 0.83 if variant else 1.0
        front,side,roof = palettes[(week*7+day*11+variant*3)%len(palettes)]
        if count == 0:
            front,side,roof="#cbd5e1","#aebfce","#e2e8f0"
        # A compact, seamless lot, not a long extrusion.
        poly([(x,y),(x+w,y),(x+w+depth,y-slant),(x+depth,y-slant)],"#e1e8ef")
        poly([(x,y-h),(x+w,y-h),(x+w,y),(x,y)],front)
        poly([(x+w,y-h),(x+w+depth,y-h-slant),
              (x+w+depth,y-slant),(x+w,y)],side)
        poly([(x,y-h),(x+depth,y-h-slant),
              (x+w+depth,y-h-slant),(x+w,y-h)],roof)
        if count:
            for floor in range(int(max(0,h-8)//9)):
                wy=y-h+6+floor*9
                for column in range(3):
                    if (week+day*3+variant+floor+column)%5 != 0:
                        add(root,"rect",{"x":f"{x+2+column*5:.1f}","y":f"{wy:.1f}",
                            "width":"2.3","height":"3.2","fill":"#a4e2f2"})
                if (week+floor+day)%4 != 0:
                    poly([(x+w+1.4,wy-0.9),(x+w+3.2,wy-2.1),
                          (x+w+3.2,wy+1.0),(x+w+1.4,wy+2.2)],"#7ac6e5")
# Full-date timeline markers.
for year in range(start_date.year,today.year+1):
    date=max(start_date,dt.date(year,1,1))
    week=(date-first_sunday).days//7
    x=78+week*step
    add(root,"line",{"x1":str(x),"y1":"416","x2":str(x),"y2":"435",
                     "stroke":"#94a3b8","stroke-width":"1.5"})
    add(root,"text",{"x":str(x+5),"y":"465","class":"year"},date_label(date))
Path("profile-3d-contrib").mkdir(exist_ok=True)
ET.ElementTree(root).write("profile-3d-contrib/skyline-clean.svg",
                           encoding="unicode",xml_declaration=True)
print(f"Generated architectural city {date_label(start_date)} to {date_label(today)}")
