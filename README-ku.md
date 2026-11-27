# รถรับส่งนิสิต มก. บางเขน — MATSim Simulation

## ต้องมีก่อนรัน

- **JDK 25** (Eclipse Temurin) — `winget install EclipseAdoptium.Temurin.25.JDK`
- **Python 3.x** (ที่ไม่ใช่ MSYS2) — ไม่ต้องติดตั้ง library เพิ่ม

---

## ขั้นที่ 1 — แก้ไฟล์ข้อมูล

| ไฟล์ | แก้อะไร |
|---|---|
| `data/stops.csv` | พิกัด lat/lon ของป้ายแต่ละจุด (คลิกขวาใน Google Maps) |
| `data/routes.csv` | ลำดับป้ายตามที่รถวิ่งจริง เรียง seq ต่อเนื่อง ไม่มีซ้ำ |
| `data/fleet.csv` | จำนวนรถ ประเภท สายที่วิ่ง ช่วงเวลา |
| `data/params.py` | `N_PT_USERS`, `CLASS_START_TIMES`, สัดส่วนจุดเข้า-ปลายทาง |

ตรวจว่าป้ายใน `routes.csv` มีครบใน `stops.csv` ก่อนเสมอ

```powershell
python check_stops.py
```

---

## ขั้นที่ 2 — สร้าง input

```powershell
python scripts\build_network.py
python scripts\build_transit.py
python scripts\build_population.py
```

ดูตาราง headway ที่ได้จาก `build_transit.py` ว่าสมเหตุสมผลไหมก่อนไปขั้นถัดไป

---

## ขั้นที่ 3 — Build (ครั้งแรกครั้งเดียว)

```powershell
.\mvnw.cmd clean package -DskipTests
```

ไม่ต้อง build ใหม่ถ้าแก้แค่ไฟล์ใน `data/` หรือ `config.xml`

---

## ขั้นที่ 4 — รัน MATSim ครั้งเดียว

จำลองนิสิต 2,000 คนเดินทางทั้งวันด้วย fleet ที่มีอยู่ใน `fleet.csv` ตอนนี้
รถวิ่งตามตารางเดินรถตายตัว ไม่มีสูตรตัดสินใจ

```powershell
java -Xmx6g -jar "target\matsim-example-project-0.0.1-SNAPSHOT.jar" `
  "C:\<path>\matsim-example-project\config.xml" `
  "C:\<path>\matsim-example-project\output\base"
```

แทน `<path>` ด้วย path จริงในเครื่อง รอประมาณ 5–15 นาที

> **หมายเหตุ:** จำนวน iterations ตั้งไว้ที่ `config.xml` บรรทัด `lastIteration`
> ค่า 20 ให้ผลแม่นยำที่สุด ค่า 5 รันเร็วกว่า 4 เท่าแต่ผลยังไม่ลู่เข้าสมดุลเต็มที่

---

## ขั้นที่ 5 — ประเมินผล baseline

อ่านผลจากขั้นที่ 4 แล้วสรุปเป็นตัวชี้วัดหลัก

```powershell
python scripts\analyze_events.py output\base
```

ผลที่ได้

| ตัวชี้วัด | ความหมาย | เป้าหมาย |
|---|---|---|
| `wait_p90_min` | เวลารอที่ป้ายของนิสิต 90% ไม่เกินกี่นาที (ยิ่งน้อยยิ่งดี) | ≤ 10 นาที |
| `peak_load_factor` | สัดส่วนที่นั่งที่ถูกใช้ในช่วงพีค (1.0 = รถเต็ม) | ≤ 0.85 |

ไฟล์ CSV รายละเอียดอยู่ใน `output\base\wait_by_stop.csv` และ `load_by_hour.csv`

---

## ขั้นที่ 6 — เทียบหลายซีนาริโอ fleet คงที่

รัน MATSim หลายครั้งด้วย fleet ที่กำหนดไว้ล่วงหน้าแต่ละแบบ
ใช้เปรียบเทียบว่าถ้าเพิ่มรถหรือเปลี่ยนขนาดรถจะดีขึ้นแค่ไหน
รถยังวิ่งตามตารางตายตัว ไม่มีสูตรตัดสินใจ

```powershell
python scripts\run_sweep.py           # รันทุกซีนาริโอ
python scripts\run_sweep.py base plus2  # รันเฉพาะที่ระบุ
```

ผลอยู่ที่ `output\comparison.csv`

ชื่อ scenario ที่ใช้ได้

| ชื่อ | ความหมาย |
|---|---|
| `base` | สภาพปัจจุบัน ใช้เปรียบเทียบเป็น baseline |
| `no_special` | ยกเลิกสายพิเศษ คืนรถใหญ่ให้สาย 1 และ 3 ตลอดวัน |
| `special_extra` | คงสายพิเศษแต่เพิ่มรถ 2 คันแทนการดึงจากสายหลัก |
| `plus1_line3` | เพิ่มรถเล็ก 1 คันในสาย 3 |
| `plus2` | เพิ่มรถเล็กสาย 1 และ 3 อย่างละคัน |
| `all_large` | เปลี่ยนรถเล็กเป็นรถใหญ่ทั้งหมด จำนวนเท่าเดิม |

เพิ่ม scenario ใหม่ได้โดยเพิ่ม entry ใน `SCENARIOS` dict ใน `run_sweep.py`

---

## ขั้นที่ 7 — ทดสอบสูตร dispatching (score-based sweep)

ให้สูตรคำนวณ score แต่ละป้ายแล้วตัดสินใจปรับ fleet อัตโนมัติทุกรอบ
แต่ละรอบ: รัน MATSim → อ่านผลเวลารอ → คำนวณ score → เพิ่มรถในสายที่ผ่านป้าย score สูง → รันใหม่

**รันสูตรหลักสูตรเดียว (w1*(N/K) + w2*(W/Wmax) + w3*(A)) (แนะนำ)**

```powershell
python -c "
import sys; sys.path.insert(0,'scripts')
from run_sweep import run_score_based
run_score_based('ku_score', max_rounds=5)
"
```

**รันและเทียบทุกสูตรพร้อมกัน (ใช้เวลานานกว่า)**

```powershell
python scripts\run_sweep.py score_based
```


ผลเปรียบเทียบทุกสูตรอยู่ที่ `output\score_comparison.csv`

**สูตรที่มีใน `scripts\scoring_formulas.py`**

| ชื่อสูตร | สูตร | ใช้เมื่อ |
|---|---|---|
| `ku_score` | w1*(N/K) + w2*(W/Wmax) + w3*(A) | สูตรหลัก รวมทุกปัจจัย |
| `crowd_only` | N/K | ทดสอบแค่จำนวนคนรอ |
| `wait_only` | W/Wmax | ทดสอบแค่เวลารอ |
| `equal_weight` | (N/K + W/Wmax + A) / 3 | น้ำหนักเท่ากันทั้งสาม |

ตัวแปรในสูตร: N = คนรอที่ป้าย, K = ความจุรถ, W = เวลารอสะสม, Wmax = เวลารอสูงสุดที่ยอมรับ, A = อัตราการมาถึง

ปรับจำนวนรอบได้โดยเปลี่ยน `max_rounds` และเพิ่มสูตรใหม่ได้ใน `scoring_formulas.py`

**เวลาโดยประมาณ (lastIteration = 5)**

| วิธีรัน | เวลา |
|---|---|
| ขั้นที่ 4 ครั้งเดียว | ~3 นาที |
| ขั้นที่ 6 ทุก scenario | ~18 นาที |
| ขั้นที่ 7 สูตรเดียว 5 รอบ | ~15 นาที |
| ขั้นที่ 7 ทุกสูตร 5 รอบ | ~60 นาที |

---

## Visualization

| Tool | ดูอะไร | วิธีเปิด |
|---|---|---|
| **SimWrapper** | แดชบอร์ดวิเคราะห์ ฟรี | simwrapper.github.io → เปิดโฟลเดอร์ `output\base` |
| **Via** | รถวิ่งบนแผนที่จริง ฟรี ≤ 500 agents | simunto.com/via → drag `output_events.xml.gz` + `output_network.xml.gz` |

---

## ถ้า MATSim crash

| Error | วิธีแก้ |
|---|---|
| `KeyError` ใน Python | ป้ายใน `routes.csv` ไม่มีใน `stops.csv` — รัน `check_stops.py` |
| `release version 25 not supported` | JDK ไม่ใช่ 25 — ตรวจด้วย `java -version` |
| `netsim link lookup failed` | มีป้ายใน `stops.csv` ที่ไม่อยู่ในสายไหน และมี `is_entry=1` — แก้เป็น `0` หรือลบออก |
| ผล `boardings = 0` | event type เปลี่ยนตาม MATSim version — รันสคริปต์ตรวจ event types |