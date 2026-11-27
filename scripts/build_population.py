# -*- coding: utf-8 -*-
"""สร้าง population.xml.gz — นิสิตสังเคราะห์ที่ใช้รถรับส่ง

ไม่ใช้ข้อมูลรายบุคคลใด ๆ สร้างจากตัวเลขรวมใน params.py เท่านั้น:
  จำนวนผู้ใช้ x สัดส่วนประตูเข้า x สัดส่วนปลายทาง x เวลาคาบเรียน
"""
from common import *
import random

random.seed(P.RANDOM_SEED)
stops = load_stops()

entries = list(P.ENTRY_WEIGHTS)
entry_w = [P.ENTRY_WEIGHTS[k] for k in entries]
dests = list(P.DEST_WEIGHTS)
dest_w = [P.DEST_WEIGHTS[k] for k in dests]


def jitter(minutes):
    return random.uniform(-minutes * 60, minutes * 60)


def act(kind, sid, end=None):
    s = stops[sid]
    e = f' end_time="{hms(end)}"' if end is not None else ''
    return (f'      <activity type="{kind}" x="{s["x"]}" y="{s["y"]}" '
            f'link="loop_{sid}"{e}/>')


lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<!DOCTYPE population SYSTEM '
         '"http://www.matsim.org/files/dtd/population_v6.dtd">',
         '<population>']

leg_count = 0
for i in range(P.N_PT_USERS):
    home = random.choices(entries, entry_w)[0]
    n_class = random.choices([1, 2, 3], [0.30, 0.45, 0.25])[0]

    first_start = secs(random.choices(P.CLASS_START_TIMES,
                                      P.CLASS_START_WEIGHTS)[0])
    # ออกจากบ้าน/ประตู เผื่อเวลามาถึงก่อนคาบเริ่ม
    leave_home = first_start - P.ACCESS_BUFFER_MIN * 60 + jitter(P.DEPART_JITTER_MIN)

    body = [f'  <person id="s{i:06d}">', '    <plan selected="yes">',
            act("home", home, leave_home)]

    t = first_start
    prev = None
    for c in range(n_class):
        d = random.choices(dests, dest_w)[0]
        while d == prev:                       # ไม่ให้คาบติดกันอยู่ที่เดิม
            d = random.choices(dests, dest_w)[0]
        prev = d
        body.append('      <leg mode="drt"/>') # ex drt / pt
        leg_count += 1
        t = t + P.CLASS_DURATION_MIN * 60 + jitter(P.DEPART_JITTER_MIN)
        last = (c == n_class - 1)
        if last:
            body.append(act("class", d, t))
        else:
            gap = random.choice([0, 0, 30, 60, 90]) * 60   # ช่องว่างระหว่างคาบ
            body.append(act("class", d, t + gap))
            t += gap
    body.append('      <leg mode="pt"/>')
    leg_count += 1
    body.append(act("home", home))
    body += ['    </plan>', '  </person>']
    lines += body

lines.append('</population>')
gz_write(OUT / "population.xml.gz", "\n".join(lines) + "\n")
print(f"  {P.N_PT_USERS} คน, {leg_count} เที่ยว pt "
      f"(เฉลี่ย {leg_count/P.N_PT_USERS:.1f} เที่ยว/คน/วัน)")
