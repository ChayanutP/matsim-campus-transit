# -*- coding: utf-8 -*-
"""สร้าง network.xml.gz แบบ schematic จากลำดับป้ายในแต่ละสาย

ข้อจำกัด: โครงข่ายนี้เป็นเส้นตรงเชื่อมป้ายต่อป้าย ไม่ใช่ถนนจริง
เพียงพอสำหรับตอบคำถาม "ต้องใช้รถกี่คัน" เพราะคอขวดคือความจุรถ ไม่ใช่ถนน
ถ้าต้องการถนนจริง ให้ใช้ OSM (ดู README หัวข้อ "อัปเกรดเป็นถนนจริง")
"""
from common import *

stops, routes = load_stops(), load_routes()

# เก็บคู่ป้ายที่ต้องเชื่อมกัน (ทิศทางเดียวตามที่รถวิ่ง)
pairs = set()
for seq in routes.values():
    for a, b in zip(seq, seq[1:]):
        if a != b:
            pairs.add((a, b))

# เพิ่มลิงก์ย้อนกลับ เพื่อให้ agent ที่เดินหรือ reroute ไม่ติดตาย
pairs |= {(b, a) for a, b in pairs}

# ลิงก์วนรอบตัวเอง (loop link) ที่ป้ายแต่ละแห่ง — ใช้เป็น linkRefId ของ stopFacility
loops = {s: f"loop_{s}" for s in stops}

lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<!DOCTYPE network SYSTEM "http://www.matsim.org/files/dtd/network_v2.dtd">',
         '<network name="KU Bangkhen schematic">', "  <nodes>"]

for s in stops.values():
    lines.append(f'    <node id="n_{s["id"]}" x="{s["x"]}" y="{s["y"]}"/>')
lines.append("  </nodes>")
lines.append("  <links capperiod=\"01:00:00\">")


def link(lid, frm, to, length):
    return (f'    <link id="{lid}" from="n_{frm}" to="n_{to}" '
            f'length="{length:.1f}" capacity="{P.LINK_CAPACITY}" '
            f'freespeed="{P.LINK_FREESPEED}" permlanes="{P.LINK_LANES}" '
            f'modes="car"/>')


for s in stops:
    lines.append(link(loops[s], s, s, 20.0))
for a, b in sorted(pairs):
    lines.append(link(link_id(a, b), a, b, max(50.0, dist(stops[a], stops[b]) * P.DETOUR_FACTOR)))

lines += ["  </links>", "</network>"]
gz_write(OUT / "network.xml.gz", "\n".join(lines) + "\n")

print(f"  nodes={len(stops)}  links={len(pairs)+len(stops)}")
unverified = [s["id"] for s in stops.values() if not s["verified"]]
if unverified:
    print(f"  ⚠ ป้ายที่ยังใช้พิกัดประมาณ ({len(unverified)}): {', '.join(unverified)}")
