# -*- coding: utf-8 -*-
"""สร้าง transitSchedule.xml.gz + transitVehicles.xml.gz

หลักการ: ไม่ได้กรอกตารางเดินรถทีละเที่ยว แต่คำนวณจาก
    headway = cycle_time / จำนวนรถที่วิ่งอยู่ในสายนั้น ณ ขณะนั้น
ทำให้เปลี่ยนจำนวนรถใน fleet.csv แล้วตารางเดินรถปรับตามอัตโนมัติ
— ซึ่งเป็นหัวใจของการทดลอง "ต้องใช้รถกี่คัน"
"""
from common import *
import xml.sax.saxutils as sx

stops, routes, fleet = load_stops(), load_routes(), load_fleet()
LUNCH = (secs(P.LUNCH_BREAK[0]), secs(P.LUNCH_BREAK[1]))
LAYOVER_FRAC = 0.10          # เวลาพักปลายทาง 10% ของรอบ


# ---------- 1. cycle time ของแต่ละสาย ----------
def profile(route_id):
    """คืน [(stop_id, arrival_offset, departure_offset)] และ cycle time"""
    seq = routes[route_id]
    out, t = [], 0.0
    for i, sid in enumerate(seq):
        if i == 0:
            out.append((sid, None, 0.0))
        else:
            t += travel_seconds(stops[seq[i - 1]], stops[sid])
            arr = t
            if i < len(seq) - 1:
                t += P.DWELL_SECONDS
                out.append((sid, arr, t))
            else:
                out.append((sid, arr, None))
    return out, t * (1 + LAYOVER_FRAC)


PROFILES = {r: profile(r) for r in routes}
for r, (_, cyc) in PROFILES.items():
    print(f"  {r:8s} cycle = {cyc/60:5.1f} min, {len(routes[r])} stops")


# ---------- 2. ช่วงเวลาที่ชุดรถคงที่ ----------
bounds = {secs(P.SERVICE_START), secs(P.SERVICE_END), *LUNCH}
for v in fleet:
    bounds |= {v["frm"], v["to"]}
bounds = sorted(bounds)
periods = [(a, b) for a, b in zip(bounds, bounds[1:]) if b > a]


# ---------- 3. สร้างเที่ยวรถ ----------
departures = {r: [] for r in routes}
last_dep = {}
headway_log = []

for p0, p1 in periods:
    if p0 >= LUNCH[0] and p1 <= LUNCH[1]:
        continue                                   # พักกลางวัน ไม่มีรถออก
    for rid in routes:
        active = [v for v in fleet
                  if v["route_id"] == rid and v["frm"] <= p0 and v["to"] >= p1]
        if not active:
            continue
        _, cyc = PROFILES[rid]
        headway = cyc / len(active)
        headway_log.append((rid, p0, p1, len(active), headway))
        t, i = float(p0), 0
        while t < p1:
            for _ in range(len(active)):          # หาคันที่ว่างจริง
                v = active[i % len(active)]
                i += 1
                if last_dep.get(v["vehicle_id"], -1e9) + cyc <= t + 1:
                    departures[rid].append((t, v["vehicle_id"]))
                    last_dep[v["vehicle_id"]] = t
                    break
            t += headway

for rid in routes:
    departures[rid].sort()


# ---------- 4. เขียน transitVehicles.xml ----------
used = {}
for v in fleet:
    used[v["vehicle_id"]] = v["vtype"]

vt = ['<?xml version="1.0" encoding="UTF-8"?>',
      '<vehicleDefinitions xmlns="http://www.matsim.org/files/dtd"',
      '    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
      '    xsi:schemaLocation="http://www.matsim.org/files/dtd '
      'http://www.matsim.org/files/dtd/vehicleDefinitions_v2.0.xsd">']
for name, spec in P.VEHICLE_TYPES.items():
    vt += [f'  <vehicleType id="{name}">',
           f'    <capacity seats="{spec["seats"]}" '
           f'standingRoomInPersons="{spec["standing"]}"/>',
           f'    <length meter="{spec["length"]}"/>',
           '    <width meter="2.5"/>',
           f'    <passengerCarEquivalents pce="{spec["pce"]}"/>',
           '    <networkMode networkMode="car"/>',
           '    <flowEfficiencyFactor factor="1.0"/>',
           '  </vehicleType>']
for vid, vtype in sorted(used.items()):
    vt.append(f'  <vehicle id="{vid}" type="{vtype}"/>')
vt.append('</vehicleDefinitions>')
gz_write(OUT / f"transitVehicles{SUF}.xml.gz", "\n".join(vt) + "\n")


# ---------- 5. เขียน transitSchedule.xml ----------
ts = ['<?xml version="1.0" encoding="UTF-8"?>',
      '<!DOCTYPE transitSchedule SYSTEM '
      '"http://www.matsim.org/files/dtd/transitSchedule_v2.dtd">',
      '<transitSchedule>', '  <transitStops>']
for s in stops.values():
    ts.append(f'    <stopFacility id="{s["id"]}" x="{s["x"]}" y="{s["y"]}" '
              f'linkRefId="loop_{s["id"]}" name="{sx.escape(s["name"])}" '
              f'isBlocking="false"/>')
ts.append('  </transitStops>')

for rid, seq in routes.items():
    prof, _ = PROFILES[rid]
    ts += [f'  <transitLine id="{rid}">',
           f'    <transitRoute id="{rid}_loop">',
           '      <transportMode>pt</transportMode>',
           '      <routeProfile>']
    for sid, arr, dep in prof:
        a = f' arrivalOffset="{hms(arr)}"' if arr is not None else ''
        d = f' departureOffset="{hms(dep)}"' if dep is not None else ''
        ts.append(f'        <stop refId="{sid}"{a}{d} awaitDeparture="true"/>')
    ts += ['      </routeProfile>', '      <route>']
    ts.append(f'        <link refId="loop_{seq[0]}"/>')
    for a, b in zip(seq, seq[1:]):
        ts.append(f'        <link refId="{link_id(a, b)}"/>')
        ts.append(f'        <link refId="loop_{b}"/>')
    ts += ['      </route>', '      <departures>']
    for k, (t, vid) in enumerate(departures[rid]):
        ts.append(f'        <departure id="{rid}_{k:04d}" '
                  f'departureTime="{hms(t)}" vehicleRefId="{vid}"/>')
    ts += ['      </departures>', '    </transitRoute>', '  </transitLine>']
ts.append('</transitSchedule>')
gz_write(OUT / f"transitSchedule{SUF}.xml.gz", "\n".join(ts) + "\n")


# ---------- 6. สรุป headway ----------
print("\n  ตาราง headway ที่คำนวณได้ (นาที):")
print("  สาย      ช่วงเวลา             รถ  headway")
seen = set()
for rid, p0, p1, n, hw in headway_log:
    key = (rid, n)
    tag = "  ← ช่วงพีคโดนดึงรถไปสายพิเศษ" if rid in ("line1", "line3") and \
          LUNCH[0] > p0 >= secs("07:30:00") and p1 <= secs("09:30:00") else ""
    print(f"  {rid:8s} {hms(p0)}-{hms(p1)}  {n}   {hw/60:5.1f}{tag}")
total = sum(len(d) for d in departures.values())
print(f"\n  รวม {total} เที่ยว/วัน")
