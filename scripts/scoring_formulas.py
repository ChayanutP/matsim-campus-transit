# -*- coding: utf-8 -*-
"""สูตร score สำหรับเลือกว่าจะเพิ่มรถไปสายไหน

เปลี่ยนสูตรที่ใช้ได้โดยแก้ ACTIVE_FORMULA บรรทัดเดียว
"""

W_MAX = 10.0  # เวลารอสูงสุดที่ยอมรับได้ (นาที)
K_BUS = 22    # ความจุรถเล็ก


def ku_score(stop, w1=0.4, w2=0.4, w3=0.2):
    """Score_i = w1*(N_i/K_bus) + w2*(W_i/W_max) + w3*(A_i)"""
    n = stop["n"]
    w = stop["p90_min"]
    a = n / max(w, 0.1)
    return w1 * (n / K_BUS) + w2 * (w / W_MAX) + w3 * a


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