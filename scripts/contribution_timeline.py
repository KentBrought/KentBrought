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
first_sunday = created - dt.timedelta(days=(created.weekday()+1)%7)
last_week = (today-first_sunday).days//7
tile_x, tile_y = 13.0, 6.0
# Isometric view: weeks run horizontally, weekdays run diagonally down-right.
def pos(week, weekday):
    return 64 + week*tile_x + weekday*tile_y, 105 + week*1.45 + weekday*tile_y*0.65

width = int(64 + last_week*tile_x + 7*tile_y + 110)
height = int(105 + last_week*1.45 + 7*tile_y + 185)
ns = "http://www.w3.org/2000/svg"
ET.register_namespace("",ns)
def el(parent, name, attrs=None, text=None):
    node = ET.SubElement(parent, f"{{{ns}}}{name}", attrs or {})
    if text is not None: node.text = str(text)
    return node
root = ET.Element(f"{{{ns}}}svg", {"viewBox":f"0 0 {width} {height}",
    "width":str(width),"height":str(height),"role":"img",
    "aria-label":f"Isometric GitHub contribution timeline from {created} to {today}"})
el(root,"title",text=f"{USERNAME} GitHub contributions, {created} to {today}")
el(root,"style",text="""
  .label {font: 600 25px system-ui,sans-serif;fill:#57606a}
  .range {font: 500 23px system-ui,sans-serif;fill:#57606a}
  .year {font: 600 23px system-ui,sans-serif;fill:#57606a}
  @media(prefers-color-scheme:dark) {
    .label,.range,.year {fill:#8b949e}
  }
""")
el(root,"text",{"x":"64","y":"48","class":"label"},f"{USERNAME} / GitHub history")
el(root,"text",{"x":str(width-55),"y":"48","class":"range","text-anchor":"end"},f"{created} – {today}")
# Draw all tiles, including zero days, in back-to-front order.
for week in range(last_week+1):
    for weekday in range(7):
        date = first_sunday + dt.timedelta(days=week*7+weekday)
        if not (created <= date <= today): continue
        count = days.get(date,0)
        x,y = pos(week,weekday)
        level = 0 if count==0 else min(4,1+int(math.log2(max(1,count))/2))
        height_px = 3 if count==0 else 8+min(54,math.log2(count+1)*11)
        top = ["#d0d7de","#9be9a8","#40c463","#30a14e","#216e39"][level]
        left = ["#aeb6be","#74ba81","#309b4b","#257d3c","#19592f"][level]
        right = ["#929ca6","#5d9c6b","#247c3d","#1c6330","#124624"][level]
        w,h=10,5
        def polygon(points,color):
            el(root,"polygon",{"points":" ".join(f"{a:.1f},{b:.1f}" for a,b in points),
                "fill":color})
        polygon([(x,y-height_px),(x+w,y-height_px-h),(x+2*w,y-height_px),(x+w,y-height_px+h)],top)
        polygon([(x,y-height_px),(x+w,y-height_px+h),(x+w,y+h),(x,y)],left)
        polygon([(x+w,y-height_px+h),(x+2*w,y-height_px),(x+2*w,y),(x+w,y+h)],right)
# Year markers along the lower edge of the timeline.
for year in range(created.year,today.year+1):
    marker=max(created,dt.date(year,1,1))
    week=(marker-first_sunday).days//7
    x,y=pos(week,6)
    el(root,"line",{"x1":f"{x+9:.1f}","y1":f"{y+22:.1f}",
                    "x2":f"{x+9:.1f}","y2":f"{y+67:.1f}",
                    "stroke":"#8b949e","stroke-width":"1.5","opacity":"0.7"})
    el(root,"text",{"x":f"{x+13:.1f}","y":f"{y+95:.1f}","class":"year"},str(year))
Path("profile-3d-contrib").mkdir(exist_ok=True)
ET.ElementTree(root).write("profile-3d-contrib/skyline-clean.svg",encoding="unicode",xml_declaration=True)
print(f"Generated {created} through {today}; {len(days)} dated contributions; {width}x{height}")
