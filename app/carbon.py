"""ประมาณการก๊าซเรือนกระจกที่หลีกเลี่ยงได้จากการรีไซเคิล

เป็นการประมาณเบื้องต้นสำหรับรายงานภายในและงาน ESG ไม่ใช่คาร์บอนเครดิตที่ซื้อขายได้
การขอคาร์บอนเครดิต (เช่น T-VER ของ อบก.) ต้องขึ้นทะเบียนโครงการ ใช้ระเบียบวิธีที่รับรอง และผ่านการทวนสอบ

ค่าปัจจัยตั้งต้นมาจาก US EPA WARM แทนที่ได้ด้วยค่าจากแหล่งอื่น เช่น อบก. ผ่าน API (ดู update)
"""
import json
import time

from . import db
from .config import (CARBON_DEFAULT_META, HUB_RECYCLED_MTCO2E_PER_SHORT_TON, INVENTORY_META, SHORT_TON_KG,
                     WARM_RECYCLING_MTCO2E_PER_SHORT_TON)

# kgCO2e ที่หลีกเลี่ยงได้ต่อวัสดุ 1 กก. (แปลงจาก MTCO2E ต่อ short ton และกลับเครื่องหมายให้เป็นค่าบวก)
DEFAULT_FACTORS = {k: round(-v * 1000 / SHORT_TON_KG, 3) for k, v in WARM_RECYCLING_MTCO2E_PER_SHORT_TON.items()}

# kgCO2e ที่ "ปล่อย" จากกระบวนการรีไซเคิลต่อวัสดุ 1 กก. ใช้กับบัญชี Scope 3 หมวด 5 ของผู้ก่อของเสีย
# เป็นตัวเลขคนละชุดกับค่าที่หลีกเลี่ยงได้ รายงานทุกแบบแสดงสองตัวเลขนี้แยกกัน และไม่นำมาหักกัน
INVENTORY_FACTORS = {k: round(v * 1000 / SHORT_TON_KG, 4) for k, v in HUB_RECYCLED_MTCO2E_PER_SHORT_TON.items()}


def inventory() -> dict:
    """ค่าปัจจัยของการปล่อยจากกระบวนการรีไซเคิล พร้อมที่มา"""
    return {**INVENTORY_META, "unit": "kgCO2e ที่ปล่อยจากกระบวนการรีไซเคิลต่อวัสดุ 1 กก.", "factors": dict(INVENTORY_FACTORS)}


def emitted_kg(kg_by_material: dict[str, float]) -> float:
    return sum(kg * INVENTORY_FACTORS.get(m, 0) for m, kg in kg_by_material.items())


def current() -> dict:
    """ชุดค่าปัจจัยที่ใช้อยู่ พร้อมที่มา ถ้ายังไม่เคยมีการส่งค่าเข้ามา จะเป็นค่าตั้งต้นจาก EPA WARM"""
    stored = json.loads(db.get_kv("carbon_factors") or "{}")
    meta = {**CARBON_DEFAULT_META, "updated_at": None, "updated_by": None, **{k: v for k, v in stored.items() if k != "factors"}}
    return {**meta, "is_default": not stored, "unit": "kgCO2e ที่หลีกเลี่ยงได้ต่อวัสดุ 1 กก.",
            "factors": {**DEFAULT_FACTORS, **stored.get("factors", {})}}


def avoided_kg(kg_by_material: dict[str, float], factors: dict[str, float] | None = None) -> float:
    factors = factors or current()["factors"]
    return sum(kg * factors.get(m, 0) for m, kg in kg_by_material.items())


def update(payload: dict, by: str) -> dict:
    """รับชุดค่าปัจจัยใหม่ (เช่น ค่าที่ อบก. ประกาศ) ตรวจแล้วบันทึกทับของเดิม วัสดุที่ไม่ได้ส่งมาคงค่าเดิมไว้"""
    cur = current()
    new = dict(cur["factors"])
    for key, value in (payload.get("factors") or {}).items():
        if key not in DEFAULT_FACTORS:
            raise ValueError(f"ไม่รู้จักวัสดุ {key} วัสดุที่ใช้ได้คือ {', '.join(DEFAULT_FACTORS)}")
        v = float(value)
        if not 0 <= v <= 100:
            raise ValueError(f"ค่าของ {key} ต้องอยู่ระหว่าง 0 ถึง 100 kgCO2e ต่อกิโลกรัม")
        new[key] = round(v, 4)
    source = str(payload.get("source") or "").strip()
    if not source:
        raise ValueError("ต้องระบุ source ว่าค่าชุดนี้มาจากที่ใด")
    record = {
        "source": source[:120], "version": str(payload.get("version") or "")[:60],
        "reference_url": str(payload.get("reference_url") or "")[:300],
        "effective_date": str(payload.get("effective_date") or "")[:20],
        "note": str(payload.get("note") or "")[:300], "updated_at": time.time(), "updated_by": by, "factors": new,
    }
    db.set_kv("carbon_factors", json.dumps(record, ensure_ascii=False))
    history = json.loads(db.get_kv("carbon_factor_history") or "[]")
    history.append({k: record[k] for k in ("source", "version", "updated_at", "updated_by")})
    db.set_kv("carbon_factor_history", json.dumps(history[-20:], ensure_ascii=False))
    return current()


def reset() -> dict:
    db.execute("DELETE FROM kv WHERE key = 'carbon_factors'")
    return current()
