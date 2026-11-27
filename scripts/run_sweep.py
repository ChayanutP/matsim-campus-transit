# -*- coding: utf-8 -*-
"""รันหลายซีนาริโอกองรถแล้วสรุปเป็นตารางเดียว

    python scripts\run_sweep.py                    # รันทุกซีนาริโอ
    python scripts\run_sweep.py base plus2         # รันเฉพาะที่ระบุ
    python scripts\run_sweep.py score_based        # รัน loop สูตรของคุณ
"""
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, DATA
import analyze_events
from scoring_formulas import FORMULAS

JAR = os.environ.get(
    "KU_JAR", str(ROOT / "target" / "matsim-example-project-0.0.1-SNAPSHOT.jar"))
JAVA_XMX = os.environ.get("KU_XMX", "6g")

L, S, E = "large_diesel", "small", "large_electric"

SCENARIOS = {
    "base": dict(
        desc="ปัจจุบัน (สาย1=4, สาย3=3, สาย5=3, สายพิเศษดึงรถใหญ่)",
        lines={"line1": [L, S, S, S], "line3": [E, S, S], "line5": [S, S, S]},
        special_from=[("line1", 0), ("line3", 0)]),
    "no_special": dict(
        desc="ยกเลิกสายพิเศษ คืนรถใหญ่ให้สาย 1 และ 3",
        lines={"line1": [L, S, S, S], "line3": [E, S, S], "line5": [S, S, S]},
        special_from=[]),
    "special_extra": dict(
        desc="คงสายพิเศษ แต่ใช้รถเพิ่ม 2 คัน",
        lines={"line1": [L, S, S, S], "line3": [E, S, S], "line5": [S, S, S]},
        special_from=[], special_extra=[S, S]),
    "plus1_line3": dict(
        desc="เพิ่มรถเล็ก 1 คันในสาย 3",
        lines={"line1": [L, S, S, S], "line3": [E, S, S, S], "line5": [S, S, S]},
        special_from=[("line1", 0), ("line3", 0)]),
    "plus2": dict(
        desc="เพิ่มรถเล็กสาย 1 และ 3 อย่างละคัน",
        lines={"line1": [L, S, S, S, S], "line3": [E, S, S, S], "line5": [S, S, S]},
        special_from=[("line1", 0), ("line3", 0)]),
    "all_large": dict(
        desc="เปลี่ยนรถเล็กเป็นรถใหญ่ทั้งหมด จำนวนเท่าเดิม",
        lines={"line1": [L, L, L, L], "line3": [E, E, E], "line5": [L, L, L]},
        special_from=[("line1", 0), ("line3", 0)]),
}

PEAK = ("07:30:00", "09:30:00")
DAY  = ("07:00:00", "20:00:00")


# ---------- helpers ----------

def make_fleet(spec, path):
    rows = []
    for rid, vtypes in spec["lines"].items():
        for i, vt in enumerate(vtypes):
            vid = f"{rid}_{i+1}"
            if (rid, i) in spec.get("special_from", []):
                rows += [(vid, vt, rid,       DAY[0],  PEAK[0]),
                         (vid, vt, "special", PEAK[0], PEAK[1]),
                         (vid, vt, rid,       PEAK[1], DAY[1])]
            else:
                rows.append((vid, vt, rid, DAY[0], DAY[1]))
    for i, vt in enumerate(spec.get("special_extra", [])):
        rows.append((f"special_{i+1}", vt, "special", PEAK[0], PEAK[1]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["vehicle_id", "vtype", "route_id", "from_time", "to_time"])
        w.writerows(rows)
    return len({r[0] for r in rows})


def run_matsim(outdir, fleet_file, scenario_tag):
    env = {**os.environ, "FLEET_FILE": fleet_file, "SCENARIO": scenario_tag}
    subprocess.run([sys.executable, "build_transit.py"], env=env,
                   cwd=Path(__file__).parent, check=True)
    cmd = ["java", f"-Xmx{JAVA_XMX}", "-jar", JAR,
           str(ROOT / "config.xml"), str(outdir)]
    r = subprocess.run(cmd, cwd=ROOT)
    return r.returncode == 0


def stop_to_routes():
    """อ่าน routes.csv → {stop_id: {route_id, ...}}"""
    mapping = {}
    with open(DATA / "routes.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sid = r["stop_id"].strip()
            rid = r["route_id"].strip()
            mapping.setdefault(sid, set()).add(rid)
    return mapping


# ---------- scenario sweep (ของเดิม) ----------

def run(name, spec):
    print(f"\n{'='*70}\n  {name}: {spec['desc']}\n{'='*70}")
    fleet_file = f"fleet_{name}.csv"
    n_veh = make_fleet(spec, DATA / fleet_file)
    outdir = ROOT / "output" / name
    ok = run_matsim(outdir, fleet_file, name)
    if not ok:
        print(f"  MATSim ล้มเหลว")
        return None
    s, _, _ = analyze_events.analyze(outdir)
    s.update(scenario=name, vehicles=n_veh, desc=spec["desc"])
    return s


# ---------- score-based sweep (ใหม่ — ใช้สูตรของคุณ) ----------

def run_score_based(formula_name="ku_score", max_rounds=3):
    """
    loop: รัน MATSim → คำนวณ score แต่ละป้าย → เพิ่มรถในสายที่ผ่านป้าย score สูง
    หยุดเมื่อผ่านเกณฑ์หรือครบ max_rounds
    """
    formula = FORMULAS[formula_name]
    stop_routes = stop_to_routes()
    fleet_file = "fleet_score.csv"

    # เริ่มจาก fleet ปัจจุบัน
    shutil.copy(DATA / "fleet.csv", DATA / fleet_file)

    all_results = []
    round_actions = []   # เก็บ action ของแต่ละรอบสำหรับ summary

    for rnd in range(max_rounds):
        tag = f"score_{formula_name}_{rnd}"

        outdir = ROOT / "output" / tag
        ok = run_matsim(outdir, fleet_file, tag)
        if not ok:
            print("  MATSim ล้มเหลว หยุด")
            break

        summary, _, stop_rows = analyze_events.analyze(outdir)
        with open(DATA / fleet_file, encoding="utf-8") as f:
            n_veh = len({r["vehicle_id"] for r in csv.DictReader(f)})
        summary.update(scenario=tag, formula=formula_name,
                       round=rnd+1, vehicles=n_veh)
        all_results.append(summary)

        if summary["pass_wait"] and summary["pass_load"]:
            round_actions.append({"top_stops": [], "routes_added": []})
            break

        # คำนวณ score แต่ละป้าย
        scores = {r["stop"]: formula(r) for r in stop_rows if r["n"] > 0}
        if not scores:
            break

        top_stops = sorted(scores, key=scores.get, reverse=True)[:3]

        routes_to_add = set()
        for stop in top_stops:
            routes_to_add.update(stop_routes.get(stop, set()))
        routes_to_add.discard("special")

        with open(DATA / fleet_file, encoding="utf-8") as f:
            fleet_rows = list(csv.DictReader(f))

        added_routes = []
        for rid in routes_to_add:
            existing = [r for r in fleet_rows if r["route_id"] == rid]
            n = len(existing) + 1
            fleet_rows.append({
                "vehicle_id": f"{rid}_extra_{n}",
                "vtype": "small",
                "route_id": rid,
                "from_time": "07:00:00",
                "to_time": "20:00:00",
            })
            added_routes.append(rid)

        round_actions.append({
            "top_stops": top_stops,
            "routes_added": added_routes,
        })

        with open(DATA / fleet_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, ["vehicle_id","vtype","route_id",
                                   "from_time","to_time"])
            w.writeheader()
            w.writerows(fleet_rows)

    # ---------- สรุปแบบละเอียดรายรอบ ----------
    SEP = "=" * 62
    print(f"\n{SEP}")
    print(f"  สรุปผล {formula_name}")
    print(SEP)

    p90_first = all_results[0].get("wait_p90_min", 0) if all_results else 0
    p90_last  = all_results[-1].get("wait_p90_min", 0) if all_results else 0

    for i, r in enumerate(all_results):
        rnd_num  = r.get("round", i+1)
        vehicles = r.get("vehicles", "?")
        p90      = r.get("wait_p90_min", 0)
        load     = r.get("peak_load_factor", 0)
        passed   = r["pass_wait"] and r["pass_load"]
        act      = round_actions[i] if i < len(round_actions) else {}
        top      = act.get("top_stops", [])
        added    = act.get("routes_added", [])

        print(f"\n  รอบที่ {rnd_num} — fleet {vehicles} คัน")

        if i == 0:
            print(f"    fleet เริ่มต้นจาก fleet.csv")
        else:
            prev_veh = all_results[i-1].get("vehicles", "?")
            print(f"    fleet เพิ่มจากรอบที่ {rnd_num-1} ({prev_veh} → {vehicles} คัน)")

        if top:
            print(f"    สูตรคำนวณ score พบว่าป้าย {', '.join(top)} มีความต้องการสูงสุด")
        if added:
            for rid in sorted(added):
                print(f"    → เพิ่มรถเล็ก 1 คัน → สาย {rid}")
            print(f"    รวมเพิ่ม {len(added)} คันในรอบนี้")

        ok_str = "✓ ผ่าน" if passed else "✗ ยังไม่ผ่าน"
        print(f"    ผล: รอ p90 = {p90:.1f} นาที  load = {load:.2f}  {ok_str}")

        if passed:
            print(f"    ผ่านเกณฑ์แล้วในรอบนี้")

    # หมายเหตุ
    print(f"\n  {'─'*58}")
    print(f"  หมายเหตุ:")
    print(f"  - รอ p90   = เวลารอที่ป้ายของนิสิต 90% ไม่เกินกี่นาที")
    print(f"               (ยิ่งน้อยยิ่งดี  เป้าหมาย ≤ 10 นาที)")
    print(f"  - load     = สัดส่วนที่นั่งที่ถูกใช้ในช่วงพีค")
    print(f"               (1.00 = รถเต็ม  เป้าหมาย ≤ 0.85)")

    # สรุปภาพรวม
    final  = all_results[-1] if all_results else {}
    passed = final.get("pass_wait") and final.get("pass_load")
    n_rnd  = len(all_results)
    v_first = all_results[0].get("vehicles", "?") if all_results else "?"
    v_last  = final.get("vehicles", "?")

    print(f"\n  {'─'*58}")
    if p90_first > 0 and p90_last > 0:
        pct = (p90_first - p90_last) / p90_first * 100
        print(f"  สรุป: สูตรทำงานได้ — p90 ลดลง {pct:.0f}%"
              f" จาก {p90_first:.1f} → {p90_last:.1f} นาที")
        print(f"        ใน {n_rnd} รอบ สูตรเพิ่มรถจาก {v_first} → {v_last} คัน")

    if not passed:
        load_ok = final.get("pass_load", False)
        wait_ok = final.get("pass_wait", False)
        if wait_ok and not load_ok:
            print(f"  คอขวด: load ยังเป็น {final.get('peak_load_factor',0):.2f}"
                  f" เพราะความจุรถไม่พอ")
            print(f"          แนะนำ: เพิ่ม standing capacity"
                  f" หรือเปลี่ยนรถเล็กเป็นรถใหญ่")
        elif not wait_ok and load_ok:
            print(f"  คอขวด: เวลารอ p90 = {final.get('wait_p90_min',0):.1f} นาที"
                  f" ยังเกินเป้า")
            print(f"          แนะนำ: เพิ่มความถี่ หรือเพิ่มรถอีก")
        else:
            print(f"  คอขวด: ทั้งเวลารอและความจุยังไม่ผ่านเกณฑ์")
    else:
        print(f"  ✓ ผ่านเกณฑ์ทั้งหมด")

    print(SEP)

    # บันทึก CSV ไว้เสมอ ไม่ว่าจะรันผ่านทางไหน
    if all_results:
        out = ROOT / "output" / "score_comparison.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if out.exists() else "w"
        with open(out, mode, newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, all_results[0].keys(), extrasaction="ignore")
            if mode == "w":
                w.writeheader()
            w.writerows(all_results)

    return all_results


# ---------- main ----------

def print_summary(formula_name="ku_score"):
    """อ่าน score_comparison.csv แล้วพิมพ์สรุปรายรอบ"""
    csv_path = ROOT / "output" / "score_comparison.csv"
    if not csv_path.exists():
        print("  ไม่พบ output\\score_comparison.csv — รัน score_based ก่อน")
        return

    with open(csv_path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if r.get("formula") == formula_name]

    if not rows:
        print(f"  ไม่พบข้อมูลของสูตร {formula_name} ใน CSV")
        return

    SEP = "=" * 62
    print(f"\n{SEP}")
    print(f"  สรุปผล {formula_name}")
    print(SEP)

    p90_first = float(rows[0]["wait_p90_min"])
    p90_last  = float(rows[-1]["wait_p90_min"])

    for r in rows:
        rnd  = r["round"]
        veh  = r["vehicles"]
        p90  = float(r["wait_p90_min"])
        load = float(r["peak_load_factor"])
        ok   = "✓ ผ่าน" if r["pass_wait"]=="True" and r["pass_load"]=="True" \
               else "✗ ยังไม่ผ่าน"
        print(f"\n  รอบที่ {rnd} — fleet {veh} คัน")
        print(f"    ผล: รอ p90 = {p90:.1f} นาที  load = {load:.2f}  {ok}")

    print(f"\n  {'─'*58}")
    print(f"  หมายเหตุ:")
    print(f"  - รอ p90 = เวลารอที่ป้ายของนิสิต 90% ไม่เกินกี่นาที")
    print(f"             (ยิ่งน้อยยิ่งดี  เป้าหมาย ≤ 10 นาที)")
    print(f"  - load   = สัดส่วนที่นั่งที่ถูกใช้ในช่วงพีค")
    print(f"             (1.00 = รถเต็ม  เป้าหมาย ≤ 0.85)")

    if p90_first > 0:
        pct = (p90_first - p90_last) / p90_first * 100
        print(f"\n  สรุป: p90 ลดลง {pct:.0f}%"
              f" จาก {p90_first:.1f} → {p90_last:.1f} นาที")
    print(SEP)


if __name__ == "__main__":
    want = sys.argv[1:] or list(SCENARIOS)

    if want[0] == "summary":
        # แสดงสรุปจาก CSV ที่มีอยู่แล้ว ไม่ต้องรันใหม่
        fname = want[1] if len(want) > 1 else "ku_score"
        print_summary(fname)

    elif want == ["score_based"]:
        # รัน loop สูตรทุกตัวแล้วเทียบ
        all_res = []
        for fname in FORMULAS:
            shutil.copy(DATA / "fleet.csv", DATA / "fleet_score.csv")
            res = run_score_based(fname, max_rounds=5)
            all_res.extend(res)
        out = ROOT / "output" / "score_comparison.csv"
        if all_res:
            with open(out, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, all_res[0].keys(), extrasaction="ignore")
                w.writeheader(); w.writerows(all_res)
            print(f"\n  ตารางเต็ม: {out}")
    elif want[0] in SCENARIOS or all(w in SCENARIOS for w in want):
        # รันซีนาริโอแบบเดิม
        results = [r for n in want
                   if n in SCENARIOS and (r := run(n, SCENARIOS[n]))]

        cols = ["scenario", "vehicles", "wait_mean_min", "wait_p90_min",
                "wait_max_min", "peak_load_factor", "pass_wait", "pass_load", "desc"]
        out = ROOT / "output" / "comparison.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, cols, extrasaction="ignore")
            w.writeheader(); w.writerows(results)

        print(f"\n{'='*78}")
        print(f"  {'ซีนาริโอ':<18}{'รถ':>4}{'รอ p90':>9}"
              f"{'load พีค':>11}  ผ่านเกณฑ์")
        for r in results:
            ok = "✓✓" if r["pass_wait"] and r["pass_load"] else "✗"
            print(f"  {r['scenario']:<18}{r['vehicles']:>4}"
                  f"{r['wait_p90_min']:>9.1f}{r['peak_load_factor']:>11.2f}  {ok}")
        print(f"\n  ตารางเต็ม: {out}")