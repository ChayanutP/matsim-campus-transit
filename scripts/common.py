# -*- coding: utf-8 -*-
import csv, gzip, math, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "input"
OUT.mkdir(exist_ok=True)

sys.path.insert(0, str(DATA))
import params as P  # noqa: E402

def to_utm(lat, lon):
    """แปลง WGS84 → UTM Zone 47N (EPSG:32647) ไม่ต้องใช้ library ใด ๆ
    ความแม่นยำ < 1 เมตร สำหรับพื้นที่ประเทศไทย"""
    import math
    lat_r = math.radians(float(lat))
    lon_r = math.radians(float(lon))
    lon0_r = math.radians(99.0)          # central meridian zone 47N
    a = 6378137.0
    f = 1 / 298.257223563
    b = a * (1 - f)
    e2 = 1 - (b / a) ** 2
    N = a / math.sqrt(1 - e2 * math.sin(lat_r) ** 2)
    T = math.tan(lat_r) ** 2
    C = (e2 / (1 - e2)) * math.cos(lat_r) ** 2
    A = math.cos(lat_r) * (lon_r - lon0_r)
    M = a * (
        (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256) * lat_r
        - (3*e2/8 + 3*e2**2/32 + 45*e2**3/1024) * math.sin(2*lat_r)
        + (15*e2**2/256 + 45*e2**3/1024) * math.sin(4*lat_r)
        - (35*e2**3/3072) * math.sin(6*lat_r)
    )
    x = 500000 + 0.9996 * N * (
        A + (1-T+C)*A**3/6
        + (5-18*T+T**2+72*C-58*(e2/(1-e2)))*A**5/120
    )
    y = 0.9996 * (
        M + N * math.tan(lat_r) * (
            A**2/2
            + (5-T+9*C+4*C**2)*A**4/24
            + (61-58*T+T**2+600*C-330*(e2/(1-e2)))*A**6/720
        )
    )
    return round(x, 2), round(y, 2)


def hms(seconds):
    seconds = int(round(seconds))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def secs(t):
    h, m, s = (int(v) for v in t.split(":"))
    return h * 3600 + m * 60 + s


def load_stops():
    stops = {}
    with open(DATA / "stops.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            x, y = to_utm(r["lat"], r["lon"])
            stops[r["stop_id"]] = dict(
                id=r["stop_id"], name=r["name"], x=x, y=y,
                zone=r["zone"], is_entry=r["is_entry"] == "1",
                verified=r["verified"] == "1",
            )
    return stops


def load_routes():
    routes = {}
    with open(DATA / "routes.csv", encoding="utf-8") as f:
        rows = sorted(csv.DictReader(f), key=lambda r: (r["route_id"], int(r["seq"])))
    for r in rows:
        routes.setdefault(r["route_id"], []).append(r["stop_id"])
    return routes


FLEET_FILE = os.environ.get("FLEET_FILE", "fleet.csv")
TAG = os.environ.get("SCENARIO", "")
SUF = f"_{TAG}" if TAG else ""


def load_fleet(path=None):
    out = []
    with open(path or (DATA / FLEET_FILE), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append(dict(vehicle_id=r["vehicle_id"], vtype=r["vtype"],
                            route_id=r["route_id"],
                            frm=secs(r["from_time"]), to=secs(r["to_time"])))
    return out


def dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def travel_seconds(a, b):
    """เวลาเดินทางระหว่างสองป้าย จากระยะเส้นตรง x ตัวคูณอ้อม"""
    d = dist(a, b) * P.DETOUR_FACTOR
    return max(30.0, d / (P.AVG_SPEED_KMH / 3.6))


def link_id(a, b):
    return f"l_{a}_{b}"


def gz_write(path, text):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(text)
    print(f"  wrote {path.relative_to(ROOT)}  ({os.path.getsize(path)/1024:.0f} KB)")
