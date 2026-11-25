# -*- coding: utf-8 -*-
"""รันหลายซีนาริโอกองรถแล้วสรุปเป็นตารางเดียว — ตัวนี้คือคำตอบของ "ต้องใช้รถกี่คัน"

    python3 run_sweep.py            # รันทุกซีนาริโอ
    python3 run_sweep.py base plus2 # รันเฉพาะที่ระบุ
"""
import csv, os, subprocess, sys
from pathlib import Path
from common import ROOT, DATA
import analyze_events

JAR = os.environ.get(
    "KU_JAR", str(ROOT / "target" / "matsim-example-project-0.0.1-SNAPSHOT.jar"))
JAVA_XMX = os.environ.get("KU_XMX", "6g")

L, S, E = "large_diesel", "small", "large_electric"

SCENARIOS = {
    # ---- สภาพปัจจุบัน ----
    "base": dict(
        desc="ปัจจุบัน (สาย1=4, สาย3=3, สาย5=3, สายพิเศษดึงรถใหญ่จากสาย1+3)",
        lines={"line1": [L, S, S, S], "line3": [E, S, S], "line5": [S, S, S]},
        special_from=[("line1", 0), ("line3", 0)]),

    # ---- ยกเลิกสายพิเศษ คืนรถใหญ่ให้สายหลัก ----
    "no_special": dict(
        desc="ยกเลิกสายพิเศษ คืนรถใหญ่ให้สาย 1 และ 3 ตลอดวัน",
        lines={"line1": [L, S, S, S], "line3": [E, S, S], "line5": [S, S, S]},
        special_from=[]),

    # ---- คงสายพิเศษ แต่ไม่ดึงรถสายหลัก ----
    "special_extra": dict(
        desc="คงสายพิเศษ แต่ใช้รถเพิ่ม 2 คัน แทนการดึงจากสาย 1 และ 3",
        lines={"line1": [L, S, S, S], "line3": [E, S, S], "line5": [S, S, S]},
        special_from=[], special_extra=[S, S]),

    # ---- เพิ่มรถทีละคัน ----
    "plus1_line3": dict(
        desc="เพิ่มรถเล็ก 1 คันในสาย 3 (รวม 11 คัน)",
        lines={"line1": [L, S, S, S], "line3": [E, S, S, S], "line5": [S, S, S]},
        special_from=[("line1", 0), ("line3", 0)]),

    "plus2": dict(
        desc="เพิ่มรถเล็กสาย 1 และ 3 อย่างละคัน (รวม 12 คัน)",
        lines={"line1": [L, S, S, S, S], "line3": [E, S, S, S],
               "line5": [S, S, S]},
        special_from=[("line1", 0), ("line3", 0)]),

    # ---- ทดสอบว่าคอขวดคือความจุหรือความถี่ ----
    "all_large": dict(
        desc="จำนวนรถเท่าเดิม แต่เปลี่ยนรถเล็กเป็นรถใหญ่ทั้งหมด",
        lines={"line1": [L, L, L, L], "line3": [E, E, E], "line5": [L, L, L]},
        special_from=[("line1", 0), ("line3", 0)]),
}

PEAK = ("07:30:00", "09:30:00")
DAY = ("07:00:00", "20:00:00")


def make_fleet(spec, path):
    rows = []
    for rid, vtypes in spec["lines"].items():
        for i, vt in enumerate(vtypes):
            vid = f"{rid}_{i+1}"
            if (rid, i) in spec.get("special_from", []):
                rows += [(vid, vt, rid, DAY[0], PEAK[0]),
                         (vid, vt, "special", PEAK[0], PEAK[1]),
                         (vid, vt, rid, PEAK[1], DAY[1])]
            else:
                rows.append((vid, vt, rid, DAY[0], DAY[1]))
    for i, vt in enumerate(spec.get("special_extra", [])):
        rows.append((f"special_{i+1}", vt, "special", PEAK[0], PEAK[1]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["vehicle_id", "vtype", "route_id", "from_time", "to_time"])
        w.writerows(rows)
    return len({r[0] for r in rows})


def run(name, spec):
    print(f"\n{'='*70}\n  {name}: {spec['desc']}\n{'='*70}")
    fleet_file = f"fleet_{name}.csv"
    n_veh = make_fleet(spec, DATA / fleet_file)

    env = {**os.environ, "FLEET_FILE": fleet_file, "SCENARIO": name}
    subprocess.run([sys.executable, "build_transit.py"], env=env, check=True)

    outdir = ROOT / "output" / name
    cmd = ["java", f"-Xmx{JAVA_XMX}", "-cp", JAR, "org.matsim.ku.RunKuShuttle",
           str(ROOT / "config.xml"), str(outdir),
           str(ROOT / "input" / f"transitSchedule_{name}.xml.gz"),
           str(ROOT / "input" / f"transitVehicles_{name}.xml.gz")]
    print("  " + " ".join(cmd[:4]) + " ...")
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode:
        print(f"  ✗ MATSim ล้มเหลว (exit {r.returncode})")
        return None

    s, _, _ = analyze_events.analyze(outdir)
    s.update(scenario=name, vehicles=n_veh, desc=spec["desc"])
    return s


if __name__ == "__main__":
    want = sys.argv[1:] or list(SCENARIOS)
    results = [r for n in want if (r := run(n, SCENARIOS[n]))]

    cols = ["scenario", "vehicles", "wait_mean_min", "wait_p90_min",
            "wait_max_min", "peak_load_factor", "pass_wait", "pass_load", "desc"]
    with open(ROOT / "output" / "comparison.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader(); w.writerows(results)

    print(f"\n{'='*78}\n  เปรียบเทียบซีนาริโอ\n{'='*78}")
    print(f"  {'ซีนาริโอ':<16}{'รถ':>4}{'รอเฉลี่ย':>10}{'รอ p90':>9}"
          f"{'สูงสุด':>9}{'load พีค':>11}  ผ่านเกณฑ์")
    for r in results:
        ok = "✓✓" if r["pass_wait"] and r["pass_load"] else \
             ("✓ เวลารอ" if r["pass_wait"] else
              ("✓ ความจุ" if r["pass_load"] else "✗"))
        print(f"  {r['scenario']:<16}{r['vehicles']:>4}"
              f"{r['wait_mean_min']:>10.1f}{r['wait_p90_min']:>9.1f}"
              f"{r['wait_max_min']:>9.1f}{r['peak_load_factor']:>11.2f}  {ok}")
    print(f"\n  เกณฑ์: รอ p90 ≤ 10 นาที, load factor พีค ≤ 0.85 "
          f"(แก้ได้ใน data/params.py)")
    print(f"  ตารางเต็ม: output/comparison.csv")
