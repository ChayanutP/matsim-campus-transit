# -*- coding: utf-8 -*-
"""สูตร score สำหรับเลือกว่าจะเพิ่มรถไปสายไหน

เปลี่ยนสูตรที่ใช้ได้โดยแก้ ACTIVE_FORMULA บรรทัดเดียว
"""

W_MAX = 10.0  # เวลารอสูงสุดที่ยอมรับได้ (นาที)
K_BUS = 22    # ความจุรถเล็ก


def ku_score(stop, w1=0.4, w2=0.4, w3=0.2):
    """
    สูตรหลัก: Score_i = w1*(N_i/K_bus) + w2*(W_i/W_max) + w3*(A_i)

    ป้ายที่ score สูงสุด = มีคนรอเยอะ + รอนาน + คนกำลังมาเพิ่ม
    สูตรนี้จะถูกเรียกทุกรอบหลัง MATSim รันเสร็จ
    ผลลัพธ์ใช้ตัดสินใจว่าจะเพิ่มรถไปสายไหน

    ปรับน้ำหนัก:
        w1 = 0.4  → ให้ความสำคัญกับจำนวนคนรอ 40%
        w2 = 0.4  → ให้ความสำคัญกับเวลารอ 40%
        w3 = 0.2  → ให้ความสำคัญกับอัตราการมาถึง 20%
        (w1 + w2 + w3 ควรรวมได้ 1.0)
    """

    # ---- ดึงข้อมูลจาก wait_by_stop.csv ----
    n = stop["n"]        # N_i: จำนวนนิสิตที่รออยู่ที่ป้ายนี้ (คน)
    w = stop["p90_min"]  # W_i: เวลารอ p90 ของป้ายนี้ (นาที)

    # ---- คำนวณ arrival rate ----
    # A_i: อัตราการมาถึงโดยประมาณ (คน/นาที)
    # = คนรอ ÷ เวลารอ → ถ้ารอไม่นานแต่คนเยอะ แปลว่าคนเพิ่งมา
    # max(w, 0.1) ป้องกันหารด้วยศูนย์เมื่อ w = 0
    a = n / max(w, 0.1)

    # ---- คำนวณ score แต่ละองค์ประกอบ ----
    crowd_term   = n / K_BUS   # สัดส่วนคนเทียบความจุรถ (0–1+)
    wait_term    = w / W_MAX   # สัดส่วนเวลารอเทียบขีดจำกัด (0–1+)
    arrival_term = a           # อัตราการมาถึง (คน/นาที)

    # ---- รวม score ----
    return w1 * crowd_term + w2 * wait_term + w3 * arrival_term


def crowd_only(stop, **kwargs):
    """ใช้แค่จำนวนคนรอ"""
    return stop["n"] / K_BUS


def wait_only(stop, **kwargs):
    """ใช้แค่เวลารอ"""
    return stop["p90_min"] / W_MAX


def equal_weight(stop, **kwargs):
    """น้ำหนักเท่ากันทั้งสาม"""
    return ku_score(stop, w1=1/3, w2=1/3, w3=1/3)


FORMULAS = {
    "ku_score":     ku_score,
    "crowd_only":   crowd_only,
    "wait_only":    wait_only,
    "equal_weight": equal_weight,
}