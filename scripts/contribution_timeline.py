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

# One uninterrupted week-by-week city, spanning account creation through today.
start_date = max(created, dt.date(2024, 1, 1))
first_sunday = start_date - dt.timedelta(days=(start_date.weekday()+1)%7)
last_week = (today-first_sunday).days//7
# Each week has seven daily blocks across a visible isometric depth axis.
# Leave enough horizontal separation to prevent neighboring weeks phasing.
tile_x = 24.0
def pos(week, weekday=0):
    return 100 + week*tile_x + weekday*3.0, 240 + weekday*12.0

width = int(100 + (last_week+1)*tile_x + 180)
height = 480
ns = "http://www.w3.org/2000/svg"
ET.register_namespace("",ns)
def long_date(value):
    return f"{value.strftime('%B')} {value.day}, {value.year}"

def el(parent, name, attrs=None, text=None):
    node = ET.SubElement(parent, f"{{{ns}}}{name}", attrs or {})
    if text is not None: node.text = str(text)
    return node
root = ET.Element(f"{{{ns}}}svg", {"viewBox":f"0 0 {width} {height}",
    "width":str(width),"height":str(height),"role":"img",
    "aria-label":f"Isometric GitHub contribution timeline from {start_date} to {today}"})
el(root,"title",text=f"{USERNAME} GitHub contributions, {long_date(start_date)} to {long_date(today)}")
el(root,"style",text="""
  .label {font: 600 25px system-ui,sans-serif;fill:#57606a}
  .range {font: 500 23px system-ui,sans-serif;fill:#57606a}
  .year {font: 600 23px system-ui,sans-serif;fill:#57606a}
  @media(prefers-color-scheme:dark) {
    .label,.range,.year {fill:#8b949e}
  }
""")
el(root,"text",{"x":"64","y":"48","class":"label"},f"{USERNAME} / GitHub history")
el(root,"text",{"x":str(width-55),"y":"48","class":"range","text-anchor":"end"},f"{long_date(start_date)} – {long_date(today)}")
# Preserve daily contribution blocks and the full seven-row isometric depth.
# Render back-to-front so nearer blocks properly occlude farther ones.
for week in range(last_week+1):
    for weekday in range(7):
        date = first_sunday + dt.timedelta(days=week*7+weekday)
        if not (start_date <= date <= today):
            continue
        count = days.get(date, 0)
        x,y = pos(week, weekday)
        level = 0 if count == 0 else min(4, 1+int(math.log2(max(1,count))/2))
        height_px = 2 if count == 0 else min(175, 8 + 13 * (count ** 0.62))
        top = ["#d0d7de","#9be9a8","#40c463","#30a14e","#216e39"][level]
        left = ["#aeb6be","#74ba81","#309b4b","#257d3c","#19592f"][level]
        right = ["#929ca6","#5d9c6b","#247c3d","#1c6330","#124624"][level]
        w,h = 7,4
        def polygon(points,color):
            el(root,"polygon",{"points":" ".join(f"{a:.1f},{b:.1f}" for a,b in points),
                "fill":color,"stroke":"#ffffff","stroke-width":"0.35","stroke-opacity":"0.35"})
        polygon([(x,y-height_px),(x+w,y-height_px-h),(x+2*w,y-height_px),(x+w,y-height_px+h)],top)
        polygon([(x,y-height_px),(x+w,y-height_px+h),(x+w,y+h),(x,y)],left)
        polygon([(x+w,y-height_px+h),(x+2*w,y-height_px),(x+2*w,y),(x+w,y+h)],right)
# Year markers along the lower edge of the timeline.
marker_years = list(range(start_date.year, today.year+1))
for year in marker_years:
    marker=max(start_date,dt.date(year,1,1))
    week=(marker-first_sunday).days//7
    x,y=pos(week,6)
    el(root,"line",{"x1":f"{x+9:.1f}","y1":f"{y+16:.1f}",
                    "x2":f"{x+9:.1f}","y2":f"{y+45:.1f}",
                    "stroke":"#8b949e","stroke-width":"1.5","opacity":"0.7"})
    el(root,"text",{"x":f"{x+13:.1f}","y":f"{y+76:.1f}","class":"year"},long_date(marker))
Path("profile-3d-contrib").mkdir(exist_ok=True)
ET.ElementTree(root).write("profile-3d-contrib/skyline-clean.svg",encoding="unicode",xml_declaration=True)
print(f"Generated {start_date} through {today}; {len(days)} dated contributions; {width}x{height}")
