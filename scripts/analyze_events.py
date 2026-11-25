# -*- coding: utf-8 -*-
"""วิเคราะห์ output_events → เวลารอรายป้าย + load factor รายชั่วโมง

    python3 analyze_events.py ../output/base
"""
import gzip, sys, csv, statistics as st
import xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import DATA, hms  # noqa
sys.path.insert(0, str(DATA))
import params as P  # noqa


def find_file(outdir, stem):
    for ext in [".xml.gz", ".xml.zst"]:
        f = outdir / (stem + ext)
        if f.exists():
            return f
    return None


def open_file(path):
    p = str(path)
    if p.endswith(".zst"):
        try:
            import zstandard as zstd
            return zstd.ZstdDecompressor().stream_reader(open(p, "rb"))
        except ImportError:
            sys.exit(
                "ต้องการ zstandard เพื่ออ่านไฟล์ .zst\n"
                "แต่ถ้าใช้ config.xml ล่าสุดที่มี compressionType=gzip\n"
                "ให้รัน MATSim ใหม่แล้วจะได้ไฟล์ .gz แทน")
    return gzip.open(p, "rb")


def pct(vals, q):
    if not vals:
        return 0.0
    s = sorted(vals)
    k = min(len(s) - 1, int(round(q * (len(s) - 1))))
    return s[k]


def analyze(outdir):
    outdir = Path(outdir)
    ev = find_file(outdir, "output_events")
    veh_path = find_file(outdir, "output_transitVehicles")
    if not ev:
        sys.exit(f"ไม่พบ output_events ใน {outdir}")

    cap = {}
    if veh_path:
        types = {}
        root = ET.parse(open_file(veh_path)).getroot()
        ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
        for vt in root.findall(f"{ns}vehicleType"):
            c = vt.find(f"{ns}capacity")
            types[vt.get("id")] = (int(c.get("seats", 0)) +
                                   int(c.get("standingRoomInPersons", 0)))
        for v in root.findall(f"{ns}vehicle"):
            cap[v.get("id")] = types.get(v.get("type"), 0)

    drivers, wait_start, occ = set(), {}, {}
    waits = []
    load = {}

    for _, e in ET.iterparse(open_file(ev), events=("end",)):
        if e.tag != "event":
            e.clear(); continue
        t = float(e.get("time")); typ = e.get("type"); h = int(t // 3600)

        if typ == "TransitDriverStarts":
            drivers.add(e.get("driverId"))
        elif typ == "waitingForPt":
            wait_start[e.get("agent")] = (t, e.get("atStop"))
        elif typ in ("PersonEntersPtVehicle", "PersonEntersVehicle"):
            p, v = e.get("person"), e.get("vehicle")
            if p in drivers:
                e.clear(); continue
            occ[v] = occ.get(v, 0) + 1
            load[(v, h)] = max(load.get((v, h), 0), occ[v])
            if p in wait_start:
                t0, stop = wait_start.pop(p)
                waits.append((stop, int(t0 // 3600), t - t0))
        elif typ in ("PersonLeavesPtVehicle", "PersonLeavesVehicle"):
            p, v = e.get("person"), e.get("vehicle")
            if p not in drivers:
                occ[v] = max(0, occ.get(v, 0) - 1)
        e.clear()

    by_stop = {}
    for stop, h, w in waits:
        by_stop.setdefault(stop, []).append(w)
    rows = []
    for stop, ws in sorted(by_stop.items(), key=lambda kv: -pct(kv[1], 0.9)):
        rows.append(dict(stop=stop, n=len(ws),
                         mean_min=round(st.mean(ws)/60, 1),
                         p90_min=round(pct(ws, 0.9)/60, 1),
                         max_min=round(max(ws)/60, 1)))
    with open(outdir / "wait_by_stop.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["stop","n","mean_min","p90_min","max_min"])
        w.writeheader(); w.writerows(rows)

    by_hour = {}
    for stop, h, s in waits:
        by_hour.setdefault(h, []).append(s)
    hrows = [dict(hour=f"{h:02d}:00", n=len(v),
                  mean_min=round(st.mean(v)/60, 1),
                  p90_min=round(pct(v, 0.9)/60, 1))
             for h, v in sorted(by_hour.items())]
    with open(outdir / "wait_by_hour.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["hour","n","mean_min","p90_min"])
        w.writeheader(); w.writerows(hrows)

    lf_hour = {}
    for (v, h), m in load.items():
        c = cap.get(v, 0)
        if c:
            lf_hour.setdefault(h, []).append(m / c)
    lrows = [dict(hour=f"{h:02d}:00", vehicles=len(v),
                  max_load_factor=round(max(v), 2),
                  mean_load_factor=round(st.mean(v), 2))
             for h, v in sorted(lf_hour.items())]
    with open(outdir / "load_by_hour.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["hour","vehicles","max_load_factor","mean_load_factor"])
        w.writeheader(); w.writerows(lrows)

    allw = [s for _, _, s in waits]
    peak = [lf for h, v in lf_hour.items() if 7 <= h <= 9 for lf in v]
    summary = dict(
        boardings=len(waits),
        wait_mean_min=round(st.mean(allw)/60, 2) if allw else 0,
        wait_p90_min=round(pct(allw, 0.9)/60, 2),
        wait_max_min=round(max(allw)/60, 2) if allw else 0,
        peak_load_factor=round(max(peak), 2) if peak else 0,
        pass_wait=pct(allw, 0.9)/60 <= P.TARGET_WAIT_P90_MIN,
        pass_load=(max(peak) if peak else 0) <= P.TARGET_LOAD_FACTOR,
    )
    return summary, hrows, rows


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "../output/base"
    s, hrows, rows = analyze(d)
    print("\n=== สรุป ===")
    for k, v in s.items():
        print(f"  {k:20s} {v}")
    print("\n=== เวลารอรายชั่วโมง ===")
    for r in hrows:
        bar = "█" * int(r["p90_min"])
        print(f"  {r['hour']}  n={r['n']:6d}  mean={r['mean_min']:5.1f}  p90={r['p90_min']:5.1f} {bar}")
    print("\n=== 8 ป้ายที่รอนานที่สุด (p90) ===")
    for r in rows[:8]:
        print(f"  {r['stop']:8s} n={r['n']:6d}  p90={r['p90_min']:5.1f} นาที")