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

## ขั้นที่ 4 — รัน MATSim

```powershell
java -Xmx6g -jar "target\matsim-example-project-0.0.1-SNAPSHOT.jar" `
  "C:\<path>\matsim-example-project\config.xml" `
  "C:\<path>\matsim-example-project\output\base"
```

แทน `<path>` ด้วย path จริงในเครื่อง รอประมาณ 5–15 นาที

---

## ขั้นที่ 5 — ดูผลลัพธ์

```powershell
python scripts\analyze_events.py output\base
```

ผลที่ได้

| ตัวชี้วัด | เป้าหมาย |
|---|---|
| `wait_p90_min` | ≤ 10 นาที |
| `peak_load_factor` | ≤ 0.85 |

ไฟล์ CSV รายละเอียดอยู่ใน `output\base\wait_by_stop.csv` และ `load_by_hour.csv`

---

## ขั้นที่ 6 — เทียบหลายซีนาริโอ

แก้ `fleet.csv` แล้วรัน sweep เพื่อเทียบกองรถหลายแบบพร้อมกัน

```powershell
$env:KU_JAR = "target\matsim-example-project-0.0.1-SNAPSHOT.jar"
python scripts\run_sweep.py
```

ผลอยู่ที่ `output\comparison.csv`

---

## Visualization

| Tool | ดูอะไร | วิธีเปิด |
|---|---|---|
| **SimWrapper** | แดชบอร์ดวิเคราะห์ ฟรี | simwrapper.github.io → เปิดโฟลเดอร์ `output\base` |
| **Via** | รถวิ่งบนแผนที่จริง ฟรี ≤ 500 agents | simunto.com/via → drag `output_events.xml.gz` + `output_network.xml.gz` |

