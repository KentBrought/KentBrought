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
# One 3D column per week keeps the 2024-present timeline legible on mobile.
tile_x = 18.0
def pos(week):
    return 64 + week*tile_x, 162

width = int(64 + (last_week+1)*tile_x + 85)
height = 280
ns = "http://www.w3.org/2000/svg"
ET.register_namespace("",ns)
def el(parent, name, attrs=None, text=None):
    node = ET.SubElement(parent, f"{{{ns}}}{name}", attrs or {})
    if text is not None: node.text = str(text)
    return node
root = ET.Element(f"{{{ns}}}svg", {"viewBox":f"0 0 {width} {height}",
    "width":str(width),"height":str(height),"role":"img",
    "aria-label":f"Isometric GitHub contribution timeline from {start_date} to {today}"})
el(root,"title",text=f"{USERNAME} GitHub contributions, {start_date} to {today}")
el(root,"style",text="""
  .label {font: 600 25px system-ui,sans-serif;fill:#57606a}
  .range {font: 500 23px system-ui,sans-serif;fill:#57606a}
  .year {font: 600 23px system-ui,sans-serif;fill:#57606a}
  @media(prefers-color-scheme:dark) {
    .label,.range,.year {fill:#8b949e}
  }
""")
el(root,"text",{"x":"64","y":"48","class":"label"},f"{USERNAME} / GitHub history")
el(root,"text",{"x":str(width-55),"y":"48","class":"range","text-anchor":"end"},f"{start_date} – {today}")
# Aggregate daily contributions into one clearly separated 3D column per week.
for week in range(last_week+1):
    dates = [first_sunday + dt.timedelta(days=week*7+day) for day in range(7)]
    count = sum(days.get(date,0) for date in dates if start_date <= date <= today)
    x,y = pos(week)
    level = 0 if count == 0 else min(4, 1+int(math.log2(max(1,count))/2))
    height_px = 2 if count == 0 else 5+min(62,math.log2(count+1)*9)
    top = ["#d0d7de","#9be9a8","#40c463","#30a14e","#216e39"][level]
    left = ["#aeb6be","#74ba81","#309b4b","#257d3c","#19592f"][level]
    right = ["#929ca6","#5d9c6b","#247c3d","#1c6330","#124624"][level]
    w,h = 7,4
    def polygon(points,color):
        el(root,"polygon",{"points":" ".join(f"{a:.1f},{b:.1f}" for a,b in points),
                           "fill":color})
    polygon([(x,y-height_px),(x+w,y-height_px-h),(x+2*w,y-height_px),(x+w,y-height_px+h)],top)
    polygon([(x,y-height_px),(x+w,y-height_px+h),(x+w,y+h),(x,y)],left)
    polygon([(x+w,y-height_px+h),(x+2*w,y-height_px),(x+2*w,y),(x+w,y+h)],right)
# Year markers along the lower edge of the timeline.
marker_years = list(range(start_date.year, today.year+1))
for year in marker_years:
    marker=max(start_date,dt.date(year,1,1))
    week=(marker-first_sunday).days//7
    x,y=pos(week)
    el(root,"line",{"x1":f"{x+9:.1f}","y1":f"{y+16:.1f}",
                    "x2":f"{x+9:.1f}","y2":f"{y+45:.1f}",
                    "stroke":"#8b949e","stroke-width":"1.5","opacity":"0.7"})
    el(root,"text",{"x":f"{x+13:.1f}","y":f"{y+76:.1f}","class":"year"},str(year))
Path("profile-3d-contrib").mkdir(exist_ok=True)
ET.ElementTree(root).write("profile-3d-contrib/skyline-clean.svg",encoding="unicode",xml_declaration=True)
print(f"Generated {start_date} through {today}; {len(days)} dated contributions; {width}x{height}")
