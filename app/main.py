"""แยกถูก รับถึงบ้าน: API + เสิร์ฟหน้าเว็บ PWA

บทบาทมี 4 แบบ: user (สมาชิกและบริษัท), driver (คนขับรถรับของ), admin (ผู้ดูแลระบบ), partner (โรงงานและร้านรับซื้อ)
ทุกเส้นทางตรวจสิทธิ์จาก session cookie และข้อมูลที่ส่งกลับถูกกรองตามบทบาท
"""
import base64
import csv
import hmac
import io
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import segno

from . import ai, auth, carbon, db, growgreen, routing, seed, settings
from .config import (BAG_TAGS, CODE_ALPHABET, DEPOT, FLAGS, MATERIALS, PRICE_REFS, PRICE_SOURCES, QR_PREFIX, SIZES,
                     SLOT_BY_ID, SLOTS)
from .estimate import aggregate_items, estimate

BASE = Path(__file__).resolve().parent.parent
BKK = timezone(timedelta(hours=7))
TYPE_LABEL = {"plastic": "พลาสติก", "paper": "กระดาษ", "metal": "โลหะ", "glass": "แก้ว"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    # ฐานข้อมูลว่าง หรือสร้างจากโครงสร้างรุ่นเก่า: ล้างแล้วใส่ข้อมูลตัวอย่างใหม่
    if db.get_kv("schema_version") != db.SCHEMA_VERSION:
        reseed()
    yield


app = FastAPI(title="แยกถูก รับถึงบ้าน", lifespan=lifespan)


# ---------- ตัวช่วย ----------

def reseed() -> None:
    db.reset()
    seed.run()
    db.set_kv("schema_version", db.SCHEMA_VERSION)
    compute_plan()


def today() -> str:
    return datetime.now(BKK).date().isoformat()


def fmt_time(ts: float | None) -> str:
    return datetime.fromtimestamp(ts, BKK).strftime("%Y-%m-%d %H:%M") if ts else ""


def count_pieces(items: list[dict]) -> int:
    return sum(int(i.get("count") or 0) for i in items if i.get("material") != "non_recyclable")


def load_requests(where: str = "", params: tuple = ()) -> list[dict]:
    rows = db.query(
        "SELECT r.id, r.member_id, r.lat, r.lng, r.slot, r.window_start, r.window_end, r.bags, r.items, r.materials,"
        " r.volume, r.est_kg, r.est_value, r.status, r.actual_kg, r.note, r.created_at, r.flags,"
        " json_array_length(r.photos) AS n_photos,"
        " r.vehicle_id, r.verified_at, r.verify_distance_m, r.collected_at, r.delivered_at, r.actual_items,"
        " m.name AS member_name, m.address, m.kind AS member_kind, m.phone AS member_phone"
        f" FROM requests r JOIN members m ON m.id = r.member_id {where} ORDER BY r.id",
        params,
    )
    for r in rows:
        for key in ("bags", "items", "materials", "flags"):
            r[key] = json.loads(r[key])
        r["actual_items"] = json.loads(r["actual_items"]) if r["actual_items"] else None
        r["total_count"] = count_pieces(r["items"])
    return rows


def add_flags(rid: int, codes: list[str]) -> None:
    if not codes:
        return
    cur = json.loads(db.query("SELECT flags FROM requests WHERE id = ?", (rid,))[0]["flags"])
    db.execute("UPDATE requests SET flags = ? WHERE id = ?", (json.dumps(list(dict.fromkeys(cur + codes))), rid))


def load_partners() -> list[dict]:
    rows = db.query("SELECT * FROM partners ORDER BY id")
    for p in rows:
        p["accepts"] = json.loads(p["accepts"])
        p["accepts_label"] = [TYPE_LABEL[t] for t in p["accepts"]]
    return rows


def split_by_factory(kg_by_type: dict[str, float]) -> list[dict]:
    """น้ำหนักที่ต้องส่งต่อแต่ละโรงงาน ตามประเภทวัสดุที่โรงงานนั้นรับ"""
    return [
        {"partner_id": p["id"], "name": p["name"], "kg": round(sum(kg_by_type.get(t, 0) for t in p["accepts"]), 1)}
        for p in load_partners() if p["kind"] == "factory"
    ]


def compute_plan() -> dict:
    """จัดเส้นทางจากคำขอที่ยังรับไม่เสร็จ แล้วเก็บแผนล่าสุดไว้"""
    mats = settings.materials()
    vehicles = db.query("SELECT * FROM vehicles WHERE active = 1 ORDER BY id")
    reqs = load_requests("WHERE r.status IN ('pending', 'verified')")
    result = routing.solve(DEPOT, vehicles, reqs)
    by_id = {r["id"]: r for r in reqs}
    veh_by_id = {v["id"]: v for v in vehicles}

    served = [by_id[s["request_id"]] for route in result["routes"] for s in route["stops"]]
    served.sort(key=lambda r: r["id"])
    total_km = round(sum(route["km"] for route in result["routes"]), 1)
    base_km = round(routing.baseline_km(DEPOT, len(vehicles), served), 1)
    saving = round((1 - total_km / base_km) * 100) if base_km > 0 else 0

    kg_by_type: dict[str, float] = {}
    for r in served:
        for m in r["materials"]:
            ftype = mats[m["material"]]["factory"]
            if ftype:
                kg_by_type[ftype] = kg_by_type.get(ftype, 0) + m["share"] * r["est_kg"]

    for route in result["routes"]:
        v = veh_by_id[route["vehicle_id"]]
        route.update(name=v["name"], color=v["color"], capacity_units=v["capacity_units"])

    n_stops = len(served)
    summary = f"ใช้รถ {sum(1 for r in result['routes'] if r['stops'])} คัน รับ {n_stops} จุด ระยะทางรวม {total_km} กม."
    if base_km > 0 and n_stops > 1:
        summary += f" สั้นกว่าวิ่งตามลำดับที่แจ้ง ({base_km} กม.) {saving}%"
    if result["unassigned"]:
        summary += f" มี {len(result['unassigned'])} จุดที่จัดไม่ลงในวันนี้"
    if not vehicles:
        summary = "ไม่มีรถที่ใช้งานได้ จึงยังจัดเส้นทางไม่ได้"

    plan = {
        "created_at": time.time(), "routes": result["routes"], "unassigned": result["unassigned"],
        "total_km": total_km, "baseline_km": base_km, "saving_pct": saving,
        "factory_kg": split_by_factory(kg_by_type), "summary": summary,
    }
    db.set_kv("plan", json.dumps(plan, ensure_ascii=False))
    return plan


def get_plan() -> dict:
    raw = db.get_kv("plan")
    return json.loads(raw) if raw else {"routes": [], "unassigned": [], "factory_kg": [], "summary": "", "total_km": 0, "baseline_km": 0, "saving_pct": 0}


def stop_index(plan: dict) -> dict:
    """คำขอแต่ละรายการอยู่บนรถคันไหน ลำดับที่เท่าไร และจะถึงกี่โมง"""
    return {
        str(s["request_id"]): {"seq": n + 1, "eta": s["eta"], "name": r["name"], "color": r["color"], "vehicle_id": r["vehicle_id"]}
        for r in plan["routes"] for n, s in enumerate(r["stops"])
    }


# ---------- รูปแบบข้อมูลที่รับเข้า ----------

class LoginIn(BaseModel):
    username: str
    password: str


class QuickLoginIn(BaseModel):
    user_id: int


class ClassifyIn(BaseModel):
    image_b64: str
    media_type: str = "image/jpeg"


class ItemIn(BaseModel):
    name_th: str
    material: str
    count: int = 1
    ai_count: int | None = None   # จำนวนที่ AI นับได้ ก่อนสมาชิกแก้ไข
    prep_tip_th: str = ""


class BagIn(BaseModel):
    name_th: str
    position_th: str = ""
    kind: str = "bag"
    mixed: bool = False
    size: str = "S"
    count_method: str = "exact"
    partial_view: bool = False
    photo: int | None = None      # ลำดับของรูปใน photos ที่ถุงนี้อยู่
    items: list[ItemIn]


class RequestIn(BaseModel):
    lat: float
    lng: float
    slot: str
    bags: list[BagIn]
    photos: list[str] = []
    note: str = ""


class VerifyIn(BaseModel):
    scan: str                    # ข้อความจาก QR หรือรหัส 6 ตัวที่พิมพ์เอง
    lat: float | None = None     # ตำแหน่งคนขับตอนสแกน (ถ้าอุปกรณ์ให้ได้)
    lng: float | None = None


class BagCheck(BaseModel):
    tag: str
    found: bool = True
    kg: float = 0
    mismatch: bool = False        # ของในถุงไม่ตรงกับที่แจ้ง


class CollectIn(BaseModel):
    bags: list[BagCheck]          # ผลตรวจรับของทุกถุงในคำขอ


class CommandIn(BaseModel):
    text: str


class PriceIn(BaseModel):
    material: str
    price: float


class NoticeIn(BaseModel):
    partner_id: int
    text: str


class TokenIn(BaseModel):
    name: str
    scopes: list[str]
    member_id: int | None = None   # ถ้าระบุ โทเคนเห็นข้อมูลของสมาชิกรายนี้เท่านั้น


class GrowGreenLinkIn(BaseModel):
    api_key: str = ""              # ว่าง = ใช้ key เดิม
    site_code: str = ""            # รหัสสถานที่ใน GrowGreen ว่างได้เมื่อองค์กรมีสถานที่เดียว
    auto_push: bool = True         # ส่งอัตโนมัติเมื่อรถส่งของถึงศูนย์คัดแยก
    member_id: int | None = None   # ผู้ดูแลระบุสมาชิกที่จะตั้งค่าให้ สมาชิกตั้งได้เฉพาะของตัวเอง


class FactorsIn(BaseModel):
    source: str                    # ที่มาของค่า เช่น "อบก. (TGO)"
    version: str = ""
    reference_url: str = ""
    effective_date: str = ""
    note: str = ""
    factors: dict[str, float]      # วัสดุ -> kgCO2e ที่หลีกเลี่ยงได้ต่อ 1 กก.


# ---------- เข้าสู่ระบบ ----------

def _session_response(user: dict) -> JSONResponse:
    res = JSONResponse({"ok": True, "role": user["role"], "name": user["name"]})
    res.set_cookie(auth.COOKIE, auth.start_session(user["id"]), httponly=True, samesite="lax", max_age=auth.SESSION_SECONDS)
    return res


@app.get("/api/demo-accounts")
def demo_accounts():
    """บัญชีตัวอย่างสำหรับปุ่ม quick login ของหน้าเข้าสู่ระบบ"""
    if not auth.QUICK_LOGIN:
        return []
    return db.query("SELECT id, username, name, role FROM users WHERE quick = 1 ORDER BY id")


@app.post("/api/login")
def login(body: LoginIn):
    rows = db.query("SELECT * FROM users WHERE username = ?", (body.username.strip().lower(),))
    if not rows or not auth.check_password(rows[0], body.password):
        raise HTTPException(401, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    return _session_response(rows[0])


@app.post("/api/login/quick")
def login_quick(body: QuickLoginIn):
    if not auth.QUICK_LOGIN:
        raise HTTPException(403, "ปิดการเข้าสู่ระบบแบบด่วนไว้")
    rows = db.query("SELECT * FROM users WHERE id = ? AND quick = 1", (body.user_id,))
    if not rows:
        raise HTTPException(404, "ไม่พบบัญชีตัวอย่างนี้")
    return _session_response(rows[0])


@app.post("/api/logout")
def logout(yt_session: str | None = Cookie(None)):
    auth.end_session(yt_session)
    res = JSONResponse({"ok": True})
    res.delete_cookie(auth.COOKIE)
    return res


# ---------- ข้อมูลของหน้าเว็บ กรองตามบทบาท ----------

@app.get("/api/state")
def state(u: dict = Depends(auth.current)):
    cfg = settings.get()
    plan = get_plan()
    stops = stop_index(plan)
    out = {
        "me": {"id": u["id"], "name": u["name"], "role": u["role"], "username": u["username"]},
        "ai_mode": "claude" if ai.has_key() else "mock",
        "config": {
            "materials": settings.materials(), "sizes": SIZES, "slots": SLOTS, "depot": DEPOT, "flags": FLAGS,
            "min_request_kg": cfg["min_request_kg"], "below_min_policy": cfg["below_min_policy"], "mixed_policy": cfg["mixed_policy"],
            "points_per_kg": cfg["points_per_kg"], "road_routing": cfg["road_routing"], "carbon_price_thb": cfg["carbon_price_thb"],
        },
    }
    if u["role"] == "admin":
        prices = today_prices()
        partners = load_partners()
        expected = {f["partner_id"]: f["kg"] for f in plan["factory_kg"]}
        for p in partners:
            p["prices"] = prices.get(p["id"], {})
            p["expected_kg"] = expected.get(p["id"], 0)
        out.update(
            members=db.query("SELECT * FROM members ORDER BY id"), vehicles=db.query("SELECT * FROM vehicles ORDER BY id"),
            requests=load_requests(), plan=plan, stops=stops, dropoffs=json.loads(db.get_kv("dropoffs") or "[]")[-10:],
            partners=partners, notices=db.query("SELECT * FROM notices ORDER BY id DESC LIMIT 30"), settings=cfg,
            tokens=list_tokens(), weekly=weekly_collected(),
        )
    elif u["role"] == "user":
        reqs = load_requests("WHERE r.member_id = ?", (u["ref_id"],))
        out["me"]["member"] = db.query("SELECT * FROM members WHERE id = ?", (u["ref_id"],))[0]
        out.update(requests=reqs, stops={str(r["id"]): stops[str(r["id"])] for r in reqs if str(r["id"]) in stops})
    elif u["role"] == "driver":
        vid = u["ref_id"]
        route = next((r for r in plan["routes"] if r["vehicle_id"] == vid), None)
        ids = [s["request_id"] for s in route["stops"]] if route else []
        marks = ",".join("?" * len(ids)) or "NULL"
        reqs = load_requests(f"WHERE r.id IN ({marks}) OR (r.vehicle_id = ? AND r.status = 'collected')", (*ids, vid))
        out["me"]["vehicle"] = db.query("SELECT * FROM vehicles WHERE id = ?", (vid,))[0]
        out.update(requests=reqs, route=route, stops=stops,
                   dropoffs=[d for d in json.loads(db.get_kv("dropoffs") or "[]") if d["vehicle_id"] == vid][-3:])
    else:  # partner
        pid = u["ref_id"]
        partner = next(p for p in load_partners() if p["id"] == pid)
        partner["prices"] = today_prices().get(pid, {})
        out["me"]["partner"] = partner
        out.update(notices=db.query("SELECT * FROM notices WHERE partner_id = ? ORDER BY id DESC LIMIT 30", (pid,)),
                   expected_kg=next((f["kg"] for f in plan["factory_kg"] if f["partner_id"] == pid), 0))
    return out


# ---------- สมาชิก ----------

@app.post("/api/classify")
def classify(body: ClassifyIn, _: dict = Depends(auth.need("user"))):
    if body.media_type not in ai.ALLOWED_MEDIA:
        raise HTTPException(400, "รองรับเฉพาะไฟล์ภาพ JPEG, PNG, WebP หรือ GIF")
    if len(body.image_b64) > 7_000_000:
        raise HTTPException(413, "รูปใหญ่เกินไป")
    try:
        base64.b64decode(body.image_b64, validate=True)
    except Exception:
        raise HTTPException(400, "ข้อมูลรูปไม่ถูกต้อง")
    result = ai.classify(body.image_b64, body.media_type)
    mats = settings.materials()
    for c in result["containers"]:
        c["estimate"] = estimate(c["items"], mats)
    return result


@app.post("/api/requests")
def create_request(body: RequestIn, u: dict = Depends(auth.need("user"))):
    cfg = settings.get()
    mats = settings.materials()
    if body.slot not in SLOT_BY_ID:
        raise HTTPException(400, "ช่วงเวลาไม่ถูกต้อง")
    if not (-90 <= body.lat <= 90 and -180 <= body.lng <= 180):
        raise HTTPException(400, "พิกัดไม่ถูกต้อง")
    photos = [p for p in body.photos[:6] if p.startswith("data:image/jpeg;base64,") and len(p) < 300_000]

    # เก็บเฉพาะถุงที่มีของรับได้ตามเกณฑ์ล่าสุด แล้วติดป้าย A, B, C ตามลำดับ
    bags, flags = [], []
    for b in body.bags:
        if b.size not in SIZES:
            raise HTTPException(400, "ขนาดถุงไม่ถูกต้อง")
        items = [i.model_dump() for i in b.items if i.material in MATERIALS and i.count > 0]
        est = estimate(items, mats)
        if est["est_kg"] <= 0:
            continue
        if b.mixed and cfg["mixed_policy"] == "reject":
            raise HTTPException(400, f"{b.name_th} มีของปนกัน กรุณาแยกชนิดก่อนส่ง หรือลบถุงนี้ออกจากคำขอ")
        if b.mixed and cfg["mixed_policy"] == "warn":
            flags.append("mixed_bag")
        bags.append({
            "tag": "", "name_th": b.name_th[:60], "position_th": b.position_th[:40], "kind": b.kind, "mixed": b.mixed,
            "size": b.size, "count_method": b.count_method, "partial_view": b.partial_view,
            "photo": b.photo if b.photo is not None and 0 <= b.photo < len(photos) else None, "items": items,
            "est_kg": est["est_kg"], "est_value": est["est_value"], "found": None, "actual_kg": None, "mismatch": False,
        })
    if not bags:
        raise HTTPException(400, "ไม่มีถุงที่มีของรับได้ในคำขอนี้")
    if len(bags) > len(BAG_TAGS):
        raise HTTPException(400, f"รับได้ไม่เกิน {len(BAG_TAGS)} ถุงต่อคำขอ")
    for k, b in enumerate(bags):
        b["tag"] = BAG_TAGS[k]

    items = aggregate_items(bags)
    est = estimate(items, mats)
    if est["est_kg"] < cfg["min_request_kg"]:
        if cfg["below_min_policy"] == "block":
            raise HTTPException(400, f"น้ำหนักรวมประมาณ {est['est_kg']:.1f} กก. ต่ำกว่าขั้นต่ำ {cfg['min_request_kg']:g} กก. ลองรวมให้ได้มากขึ้นก่อนแจ้ง")
        flags.append("below_min")
    slot = SLOT_BY_ID[body.slot]
    rid = db.execute(
        "INSERT INTO requests(member_id, lat, lng, slot, window_start, window_end, bags, items, materials, volume,"
        " est_kg, est_value, photos, note, code, flags, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (u["ref_id"], round(body.lat, 6), round(body.lng, 6), slot["id"], slot["start"], slot["end"],
         json.dumps(bags, ensure_ascii=False), json.dumps(items, ensure_ascii=False), json.dumps(est["materials"]),
         sum(SIZES[b["size"]]["units"] for b in bags), est["est_kg"], est["est_value"], json.dumps(photos),
         body.note[:200], "".join(secrets.choice(CODE_ALPHABET) for _ in range(6)),
         json.dumps(list(dict.fromkeys(flags))), time.time()),
    )
    plan = compute_plan()  # มีงานใหม่เข้ามา จัดเส้นทางใหม่ทันที
    stop = next(
        ({"vehicle": r["name"], "eta": s["eta"], "seq": n + 1}
         for r in plan["routes"] for n, s in enumerate(r["stops"]) if s["request_id"] == rid),
        None,
    )
    return {"request": load_requests("WHERE r.id = ?", (rid,))[0], "stop": stop}


def _own_request(rid: int, u: dict, columns: str = "*") -> dict:
    """คำขอที่ผู้ใช้นี้มีสิทธิ์ดู: เจ้าของคำขอ คนขับ หรือผู้ดูแล"""
    rows = db.query(f"SELECT {columns} FROM requests WHERE id = ?", (rid,))
    if not rows:
        raise HTTPException(404, "ไม่พบคำขอ")
    owner = db.query("SELECT member_id FROM requests WHERE id = ?", (rid,))[0]["member_id"]
    if u["role"] == "partner" or (u["role"] == "user" and owner != u["ref_id"]):
        raise HTTPException(403, "ไม่มีสิทธิ์ดูคำขอนี้")
    return rows[0]


@app.get("/api/requests/{rid}/photo/{index}")
def request_photo(rid: int, index: int, u: dict = Depends(auth.current)):
    photos = json.loads(_own_request(rid, u, "photos")["photos"])
    if not 0 <= index < len(photos):
        raise HTTPException(404, "ไม่มีรูป")
    return Response(base64.b64decode(photos[index].split(",", 1)[1]), media_type="image/jpeg")


@app.get("/api/requests/{rid}/ticket")
def ticket(rid: int, u: dict = Depends(auth.need("user", "admin"))):
    """QR และรหัสที่สมาชิกแสดงให้คนขับ เปิดได้เฉพาะเจ้าของคำขอและผู้ดูแล"""
    code = _own_request(rid, u, "code")["code"]
    payload = f"{QR_PREFIX}:{rid}:{code}"
    buf = io.BytesIO()
    # make_qr บังคับเป็น QR ปกติ (ค่าเริ่มต้นอาจได้ Micro QR ซึ่งกล้องมือถือส่วนใหญ่อ่านไม่ได้)
    # omitsize ให้ SVG มี viewBox จึงย่อขยายตามขนาดที่หน้าเว็บกำหนด
    segno.make_qr(payload, error="m").save(buf, kind="svg", border=3, xmldecl=False, light="#ffffff", omitsize=True)
    return {"request_id": rid, "code": code, "payload": payload, "svg": buf.getvalue().decode("utf-8")}


# ---------- คนขับ ----------

@app.post("/api/requests/{rid}/verify")
def verify(rid: int, body: VerifyIn, u: dict = Depends(auth.need("driver"))):
    """คนขับสแกน QR ของสมาชิกเมื่อถึงจุด: ยืนยันว่ามาถูกคำขอ ก่อนจะรับของได้"""
    cfg = settings.get()
    rows = db.query("SELECT * FROM requests WHERE id = ?", (rid,))
    if not rows:
        raise HTTPException(404, "ไม่พบคำขอ")
    req = rows[0]
    if req["status"] in ("collected", "delivered"):
        raise HTTPException(409, "คำขอนี้รับไปแล้ว")

    scan = body.scan.strip().upper()
    code = scan
    if scan.startswith(QR_PREFIX + ":"):
        parts = scan.split(":")
        if len(parts) != 3 or not parts[1].isdigit():
            raise HTTPException(400, "QR นี้ไม่ใช่ของระบบ")
        if int(parts[1]) != rid:
            raise HTTPException(409, f"QR นี้เป็นของคำขอ #{int(parts[1])} ไม่ใช่จุดนี้")
        code = parts[2]
    if not hmac.compare_digest(code, req["code"]):
        raise HTTPException(400, "รหัสไม่ตรงกับคำขอนี้")

    distance, far = None, False
    if body.lat is not None and body.lng is not None:
        distance = round(routing.haversine_km((body.lat, body.lng), (req["lat"], req["lng"])) * 1000)
        far = distance > cfg["scan_max_distance_m"]
        if far and cfg["scan_far_policy"] == "block":
            raise HTTPException(409, f"คุณอยู่ห่างจากหมุด {distance:,} ม. เกินเกณฑ์ {cfg['scan_max_distance_m']:g} ม. จึงยังยืนยันจุดไม่ได้")
    now = time.time()
    if req["status"] == "pending":
        db.execute(
            "UPDATE requests SET status = 'verified', verified_at = ?, verify_distance_m = ?, vehicle_id = ? WHERE id = ?",
            (now, distance, u["ref_id"], rid),
        )
        if far:
            add_flags(rid, ["scan_far"])
    return {"ok": True, "verified_at": req["verified_at"] or now, "distance_m": distance}


@app.post("/api/requests/{rid}/collect")
def collect(rid: int, body: CollectIn, _: dict = Depends(auth.need("driver"))):
    """คนขับตรวจรับทีละถุงตามป้าย และบันทึกน้ำหนักจริง ทำได้หลังยืนยันจุดด้วย QR แล้วเท่านั้น"""
    cfg = settings.get()
    rows = db.query("SELECT * FROM requests WHERE id = ?", (rid,))
    if not rows:
        raise HTTPException(404, "ไม่พบคำขอ")
    req = rows[0]
    if req["status"] in ("collected", "delivered"):
        raise HTTPException(409, "คำขอนี้รับไปแล้ว")
    if req["status"] != "verified":
        raise HTTPException(409, "ต้องสแกน QR ของลูกค้าเพื่อยืนยันจุดก่อน")

    bags = json.loads(req["bags"])
    checks = {c.tag: c for c in body.bags}
    if set(checks) != {b["tag"] for b in bags}:
        raise HTTPException(400, "ต้องตรวจให้ครบทุกถุงตามป้ายที่แจ้งไว้")
    for b in bags:
        c = checks[b["tag"]]
        if c.found and not 0 < c.kg <= 200:
            raise HTTPException(400, f"ถุง {b['tag']}: น้ำหนักต้องมากกว่า 0 และไม่เกิน 200 กก.")
        b.update(found=c.found, actual_kg=round(c.kg, 2) if c.found else 0, mismatch=bool(c.found and c.mismatch))
    found = [b for b in bags if b["found"]]
    if not found:
        raise HTTPException(400, "ต้องพบอย่างน้อย 1 ถุง ถ้าไม่พบของเลยให้แจ้งผู้ดูแลระบบ")
    if len(found) < len(bags) and not cfg["allow_partial_pickup"]:
        raise HTTPException(400, "เกณฑ์ปัจจุบันไม่ให้รับบางส่วน ต้องพบครบทุกถุง ถ้าไม่ครบให้แจ้งผู้ดูแลระบบ")

    actual_kg = round(sum(b["actual_kg"] for b in found), 2)
    est_found = sum(b["est_kg"] for b in found)
    flags = []
    if len(found) < len(bags):
        flags.append("missing_bag")
    if any(b["mismatch"] for b in found):
        flags.append("mismatch")
    if est_found > 0 and abs(actual_kg - est_found) / est_found * 100 > cfg["weight_tolerance_pct"]:
        flags.append("weight_diff")
    points = round(actual_kg * cfg["points_per_kg"])
    db.execute(
        "UPDATE requests SET status = 'collected', bags = ?, actual_kg = ?, actual_items = ?, collected_at = ? WHERE id = ?",
        (json.dumps(bags, ensure_ascii=False), actual_kg, json.dumps(aggregate_items(found), ensure_ascii=False), time.time(), rid),
    )
    add_flags(rid, flags)
    db.execute("UPDATE members SET points = points + ? WHERE id = ?", (points, req["member_id"]))
    return {"ok": True, "points": points, "actual_kg": actual_kg, "found": len(found), "bags": len(bags), "flags": flags}


@app.post("/api/dropoff")
def dropoff(background: BackgroundTasks, u: dict = Depends(auth.need("driver"))):
    """ปิดรอบ: รถส่งของที่รับมาทั้งหมดให้ศูนย์คัดแยก และสรุปน้ำหนักที่ต้องส่งต่อแต่ละโรงงาน"""
    vid = u["ref_id"]
    veh = db.query("SELECT * FROM vehicles WHERE id = ?", (vid,))[0]
    loads = load_requests("WHERE r.status = 'collected' AND r.vehicle_id = ?", (vid,))
    if not loads:
        raise HTTPException(409, "ไม่มีของบนรถที่ต้องส่ง")
    mats = settings.materials()
    kg_by_type: dict[str, float] = {}
    found = [b for r in loads for b in r["bags"] if b["found"]]
    for b in found:  # แบ่งน้ำหนักจริงของแต่ละถุงตามสัดส่วนวัสดุในถุงนั้น
        for m in estimate(b["items"], mats)["materials"]:
            ftype = mats[m["material"]]["factory"]
            if ftype:
                kg_by_type[ftype] = kg_by_type.get(ftype, 0) + m["share"] * b["actual_kg"]
    now = time.time()
    db.execute("UPDATE requests SET status = 'delivered', delivered_at = ? WHERE status = 'collected' AND vehicle_id = ?", (now, vid))
    summary = {
        "vehicle_id": vid, "vehicle": veh["name"], "at": now, "stops": len(loads), "bags": len(found),
        "kg": round(sum(r["actual_kg"] for r in loads), 1), "pieces": sum(count_pieces(b["items"]) for b in found),
        "factories": [{"name": f["name"], "kg": f["kg"]} for f in split_by_factory(kg_by_type)],
    }
    history = json.loads(db.get_kv("dropoffs") or "[]")
    history.append(summary)
    db.set_kv("dropoffs", json.dumps(history[-50:], ensure_ascii=False))
    # ส่งน้ำหนักของบริษัทที่เชื่อมต่อ GrowGreen ไว้ หลังตอบคนขับแล้ว เพื่อไม่ให้การปิดรอบต้องรอระบบภายนอก
    background.add_task(growgreen.push_delivered, [r["id"] for r in loads])
    return summary


# ---------- ผู้ดูแลระบบ ----------

@app.post("/api/plan")
def plan(_: dict = Depends(auth.need("admin"))):
    return compute_plan()


@app.post("/api/command")
def command(body: CommandIn, _: dict = Depends(auth.need("admin"))):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "กรุณาพิมพ์คำสั่ง")
    vehicles = db.query("SELECT * FROM vehicles ORDER BY id")
    parsed = ai.parse_command(text[:500], vehicles)
    action, vid = parsed["action"], parsed["vehicle_id"]
    veh = next((v for v in vehicles if v["id"] == vid), None)

    if action in ("disable_vehicle", "enable_vehicle") and veh:
        db.execute("UPDATE vehicles SET active = ? WHERE id = ?", (0 if action == "disable_vehicle" else 1, vid))
        did = f"{'หยุดใช้' if action == 'disable_vehicle' else 'เปิดใช้'}{veh['name']} แล้ว"
    elif action == "replan":
        did = "จัดเส้นทางใหม่แล้ว"
    else:
        return {"ok": False, "source": parsed["source"],
                "reply": "ยังไม่เข้าใจคำสั่งนี้ ลองพิมพ์เช่น “รถคัน 2 เสีย” “รถคัน 2 กลับมาแล้ว” หรือ “จัดเส้นทางใหม่”"}
    new_plan = compute_plan()
    return {"ok": True, "source": parsed["source"], "reply": f"{did} {new_plan['summary']}"}


@app.post("/api/reset")
def reset(_: dict = Depends(auth.need("admin"))):
    sessions = db.query("SELECT * FROM sessions")  # บัญชีตัวอย่างมี id คงที่ จึงคงการเข้าสู่ระบบไว้ได้
    tokens = db.query("SELECT * FROM api_tokens")  # โทเคนที่ระบบภายนอกใช้อยู่ ไม่ควรหายเมื่อรีเซ็ตข้อมูลตัวอย่าง
    reseed()
    for s in sessions:
        db.execute("INSERT INTO sessions(token, user_id, created_at) VALUES(?,?,?)", (s["token"], s["user_id"], s["created_at"]))
    for t in tokens:
        db.execute("INSERT INTO api_tokens(id, name, token_hash, prefix, scopes, member_id, created_at, last_used_at, revoked_at)"
                   " VALUES(?,?,?,?,?,?,?,?,?)", tuple(t[k] for k in ("id", "name", "token_hash", "prefix", "scopes", "member_id",
                                                                    "created_at", "last_used_at", "revoked_at")))
    return {"ok": True}


@app.put("/api/admin/settings")
def save_settings(patch: dict, _: dict = Depends(auth.need("admin"))):
    """บันทึกเกณฑ์การรับของและการผ่อนปรน แล้วจัดเส้นทางใหม่เพราะน้ำหนักประมาณอาจเปลี่ยน"""
    try:
        cfg = settings.save(patch)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    compute_plan()
    return cfg


@app.post("/api/admin/notices")
def send_notice(body: NoticeIn, _: dict = Depends(auth.need("admin"))):
    if not db.query("SELECT 1 FROM partners WHERE id = ?", (body.partner_id,)):
        raise HTTPException(404, "ไม่พบคู่ค้า")
    text = body.text.strip()[:300]
    if not text:
        raise HTTPException(400, "กรุณาพิมพ์ข้อความ")
    nid = db.execute("INSERT INTO notices(partner_id, text, created_at) VALUES(?,?,?)", (body.partner_id, text, time.time()))
    return {"ok": True, "id": nid}


STATUS_LABEL = {"pending": "รอรับ", "verified": "ยืนยันจุดแล้ว", "collected": "รับแล้ว", "delivered": "ส่งถึงศูนย์แล้ว"}


@app.get("/api/records.csv")
def records_csv(_: dict = Depends(auth.need("admin"))):
    vehicles = {v["id"]: v["name"] for v in db.query("SELECT id, name FROM vehicles")}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["เลขที่", "เวลาแจ้ง", "สมาชิก", "ประเภท", "ละติจูด", "ลองจิจูด", "ช่วงเวลานัด", "จำนวนถุง", "ป้ายถุง", "รายการ (ชิ้น)",
                "จำนวนรวม (ชิ้น)", "พื้นที่บนรถ (ถุง)", "น้ำหนักประมาณ (กก.)", "มูลค่าประมาณ (บาท)", "สถานะ", "รถที่รับ",
                "เวลายืนยันจุด", "ระยะจากหมุดตอนสแกน (ม.)", "เวลารับของ", "ถุงที่พบ", "ถุงที่ของไม่ตรง", "น้ำหนักจริง (กก.)",
                "เวลาส่งถึงศูนย์", "กรณีผ่อนปรนหรือต้องตรวจ"])
    for r in load_requests():
        items = "; ".join(f'{i["name_th"]} x{i.get("count", 0)}' for i in r["items"])
        tags = " ".join(f'{r["id"]}-{b["tag"]}' for b in r["bags"])
        checked = r["status"] in ("collected", "delivered")
        w.writerow([r["id"], fmt_time(r["created_at"]), r["member_name"], "บริษัท" if r["member_kind"] == "company" else "ครัวเรือน",
                    r["lat"], r["lng"], SLOT_BY_ID[r["slot"]]["label"], len(r["bags"]), tags, items, r["total_count"], r["volume"],
                    r["est_kg"], r["est_value"], STATUS_LABEL[r["status"]], vehicles.get(r["vehicle_id"], ""), fmt_time(r["verified_at"]),
                    r["verify_distance_m"] if r["verify_distance_m"] is not None else "", fmt_time(r["collected_at"]),
                    sum(1 for b in r["bags"] if b["found"]) if checked else "",
                    " ".join(b["tag"] for b in r["bags"] if b["mismatch"]) if checked else "",
                    r["actual_kg"] or "", fmt_time(r["delivered_at"]), "; ".join(FLAGS[f] for f in r["flags"])])
    # ใส่ BOM ให้ Excel อ่านภาษาไทยได้ถูกต้อง
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="pickup-records.csv"'})


# ---------- ราคารับซื้อและคู่ค้า ----------

def today_prices() -> dict[int, dict[str, float]]:
    """ราคาล่าสุดของคู่ค้าแต่ละราย แยกตามวัสดุ"""
    rows = db.query("SELECT p.partner_id, p.material, p.price FROM prices p"
                    " JOIN (SELECT partner_id, material, MAX(day) AS day FROM prices GROUP BY partner_id, material) t"
                    " ON t.partner_id = p.partner_id AND t.material = p.material AND t.day = p.day")
    out: dict[int, dict[str, float]] = {}
    for r in rows:
        out.setdefault(r["partner_id"], {})[r["material"]] = r["price"]
    return out


@app.get("/api/prices")
def prices(days: int = 60, _: dict = Depends(auth.current)):
    """กระดานราคา: ราคารับซื้อสูงสุดของแต่ละวัสดุในแต่ละวัน ราคาล่าสุดของคู่ค้าแต่ละรายพร้อมที่มา และราคาอ้างอิงจากภายนอก"""
    days = max(7, min(days, 120))
    since = (datetime.now(BKK).date() - timedelta(days=days - 1)).isoformat()
    rows = db.query("SELECT material, day, MAX(price) AS best FROM prices WHERE day >= ? GROUP BY material, day ORDER BY day", (since,))
    latest = db.query("SELECT p.partner_id, p.material, p.price, p.day, p.entered_at FROM prices p"
                      " JOIN (SELECT partner_id, material, MAX(day) AS day FROM prices GROUP BY partner_id, material) t"
                      " ON t.partner_id = p.partner_id AND t.material = p.material AND t.day = p.day")
    mats = settings.materials()
    partners = {p["id"]: p for p in load_partners()}
    out = []
    for key, m in mats.items():
        series = [{"day": r["day"], "price": r["best"]} for r in rows if r["material"] == key]
        if not series:
            continue
        offers = sorted(({"partner_id": o["partner_id"], "name": partners[o["partner_id"]]["name"], "kind": partners[o["partner_id"]]["kind"],
                          "price": o["price"], "day": o["day"], "entered_at": o["entered_at"]}
                         for o in latest if o["material"] == key), key=lambda o: -o["price"])
        refs = [{"source": src, "item": item, "low": low, "high": high} for src, item, low, high in PRICE_REFS.get(key, [])]
        out.append({"key": key, "label": m["label"], "member_price": m["price"], "accepted": m["accepted"], "series": series,
                    "offers": offers, "refs": refs})
    return {"sample": True, "materials": out, "sources": PRICE_SOURCES}


@app.post("/api/partner/prices")
def set_price(body: PriceIn, u: dict = Depends(auth.need("partner"))):
    """คู่ค้าตั้งราคารับซื้อของวันนี้"""
    partner = next(p for p in load_partners() if p["id"] == u["ref_id"])
    if body.material not in MATERIALS or MATERIALS[body.material]["factory"] not in partner["accepts"]:
        raise HTTPException(400, "คู่ค้ารายนี้ไม่ได้รับวัสดุชนิดนี้")
    if not 0 < body.price <= 1000:
        raise HTTPException(400, "ราคาต้องมากกว่า 0 และไม่เกิน 1,000 บาทต่อกิโลกรัม")
    db.execute("INSERT INTO prices(partner_id, material, day, price, entered_at) VALUES(?,?,?,?,?)"
               " ON CONFLICT(partner_id, material, day) DO UPDATE SET price = excluded.price, entered_at = excluded.entered_at",
               (partner["id"], body.material, today(), round(body.price, 2), time.time()))
    return {"ok": True}


@app.post("/api/partner/notices/{nid}/ack")
def ack_notice(nid: int, u: dict = Depends(auth.need("partner"))):
    rows = db.query("SELECT * FROM notices WHERE id = ? AND partner_id = ?", (nid, u["ref_id"]))
    if not rows:
        raise HTTPException(404, "ไม่พบข้อความ")
    if not rows[0]["ack_at"]:
        db.execute("UPDATE notices SET ack_at = ? WHERE id = ?", (time.time(), nid))
    return {"ok": True}


# ---------- คาร์บอน ----------

def carbon_report(member_id: int | None = None) -> dict:
    """ตัวเลขคาร์บอนสองชุดจากน้ำหนักจริงของถุงที่รับแล้ว แยกตามสมาชิก วัสดุ และเดือน

    co2e_kg = ก๊าซเรือนกระจกที่หลีกเลี่ยงได้โดยประมาณ (ผลดีเทียบกับการผลิตจากวัตถุดิบใหม่)
    recycling_co2e_kg = การปล่อยจากกระบวนการรีไซเคิลเอง ที่บริษัทใช้ลงบัญชี Scope 3 หมวด 5
    สองตัวเลขนี้ตอบคนละคำถาม จึงรายงานแยกกันเสมอ และไม่มีช่องใดนำมาหักกัน
    """
    mats = settings.materials()
    price = settings.get()["carbon_price_thb"]
    fac = carbon.current()
    inv = carbon.inventory()
    where = "WHERE r.status IN ('collected', 'delivered')" + (" AND r.member_id = ?" if member_id else "")
    members: dict[int, dict] = {}
    monthly: dict[str, dict] = {}
    for r in load_requests(where, (member_id,) if member_id else ()):
        m = members.setdefault(r["member_id"], {"member_id": r["member_id"], "name": r["member_name"], "kind": r["member_kind"],
                                                "pickups": 0, "kg": 0.0, "by_material": {}})
        m["pickups"] += 1
        month = datetime.fromtimestamp(r["collected_at"] or r["created_at"], BKK).strftime("%Y-%m")
        mo = monthly.setdefault(month, {"month": month, "kg": 0.0, "by_material": {}})
        for b in r["bags"]:
            if not b["found"]:
                continue
            for part in estimate(b["items"], mats)["materials"]:
                kg = part["share"] * b["actual_kg"]
                for bucket in (m, mo):
                    bucket["kg"] += kg
                    bucket["by_material"][part["material"]] = bucket["by_material"].get(part["material"], 0) + kg

    def finish(bucket: dict) -> dict:
        co2 = carbon.avoided_kg(bucket["by_material"], fac["factors"])
        bucket.update(kg=round(bucket["kg"], 1), co2e_kg=round(co2, 1), value_thb=round(co2 / 1000 * price, 2),
                      recycling_co2e_kg=round(carbon.emitted_kg(bucket["by_material"]), 2),
                      by_material={k: round(v, 1) for k, v in sorted(bucket["by_material"].items(), key=lambda kv: -kv[1])})
        return bucket

    rows = sorted((finish(m) for m in members.values()), key=lambda m: -m["co2e_kg"])
    total = {"kg": 0.0, "by_material": {}}
    for m in rows:
        total["kg"] += m["kg"]
        for k, v in m["by_material"].items():
            total["by_material"][k] = total["by_material"].get(k, 0) + v
    return {
        "factors": {k: {"label": mats[k]["label"], "kg_co2e_per_kg": v} for k, v in fac["factors"].items()},
        "factor_source": {k: fac[k] for k in ("source", "version", "reference_url", "effective_date", "note", "updated_at", "updated_by", "is_default")},
        "inventory_factors": {k: {"label": mats[k]["label"], "kg_co2e_per_kg": v} for k, v in inv["factors"].items()},
        "inventory_source": {k: inv[k] for k in ("source", "version", "reference_url", "note")},
        "carbon_price_thb": price, "members": rows, "total": finish(total),
        "monthly": [finish(monthly[k]) for k in sorted(monthly)],
    }


@app.get("/api/carbon")
def carbon_api(u: dict = Depends(auth.need("admin", "user"))):
    return carbon_report(u["ref_id"] if u["role"] == "user" else None)


@app.get("/api/carbon.csv")
def carbon_csv(_: dict = Depends(auth.need("admin"))):
    rep = carbon_report()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["สมาชิก", "ประเภท", "จำนวนครั้งที่รับ", "น้ำหนักรวม (กก.)", "ก๊าซเรือนกระจกที่หลีกเลี่ยงได้โดยประมาณ (kgCO2e)",
                f"มูลค่าเทียบเท่าที่ {rep['carbon_price_thb']:g} บาทต่อ tCO2e (บาท)",
                "การปล่อยจากกระบวนการรีไซเคิล สำหรับ Scope 3 หมวด 5 (kgCO2e) ไม่นำไปหักกับค่าที่หลีกเลี่ยงได้", "แยกตามวัสดุ (กก.)"])
    for m in rep["members"]:
        w.writerow([m["name"], "บริษัท" if m["kind"] == "company" else "ครัวเรือน", m["pickups"], m["kg"], m["co2e_kg"], m["value_thb"],
                    m["recycling_co2e_kg"], "; ".join(f'{rep["factors"][k]["label"]} {v}' for k, v in m["by_material"].items() if k in rep["factors"])])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="carbon-estimate.csv"'})


# ---------- โทเคนของระบบ และ API สำหรับระบบภายนอก (v1) ----------

def list_tokens() -> list[dict]:
    rows = db.query("SELECT t.id, t.name, t.prefix, t.scopes, t.member_id, t.created_at, t.last_used_at, t.revoked_at, m.name AS member_name"
                    " FROM api_tokens t LEFT JOIN members m ON m.id = t.member_id ORDER BY t.id DESC")
    for r in rows:
        r["scopes"] = json.loads(r["scopes"])
    return rows


def weekly_collected(weeks: int = 9) -> list[dict]:
    """น้ำหนักจริงที่รับได้ในแต่ละสัปดาห์ (เริ่มวันจันทร์) ย้อนหลัง ใช้กับกราฟของแดชบอร์ด"""
    this_monday = datetime.now(BKK).date() - timedelta(days=datetime.now(BKK).weekday())
    out = {(this_monday - timedelta(weeks=w)).isoformat(): {"kg": 0.0, "pickups": 0} for w in range(weeks - 1, -1, -1)}
    for r in db.query("SELECT collected_at, actual_kg FROM requests WHERE collected_at IS NOT NULL"):
        d = datetime.fromtimestamp(r["collected_at"], BKK).date()
        key = (d - timedelta(days=d.weekday())).isoformat()
        if key in out:
            out[key]["kg"] += r["actual_kg"] or 0
            out[key]["pickups"] += 1
    return [{"week": k, "kg": round(v["kg"], 1), "pickups": v["pickups"]} for k, v in out.items()]


@app.post("/api/admin/tokens")
def create_token(body: TokenIn, _: dict = Depends(auth.need("admin"))):
    """สร้างโทเคนของระบบ ตัวโทเคนเต็มถูกส่งกลับครั้งเดียว ระบบเก็บเฉพาะค่า hash"""
    name = body.name.strip()[:60]
    scopes = [s for s in dict.fromkeys(body.scopes) if s in auth.TOKEN_SCOPES]
    if not name or not scopes:
        raise HTTPException(400, "ต้องตั้งชื่อ และเลือกสิทธิ์อย่างน้อย 1 อย่าง")
    if body.member_id is not None and not db.query("SELECT 1 FROM members WHERE id = ?", (body.member_id,)):
        raise HTTPException(404, "ไม่พบสมาชิกที่จะผูกกับโทเคน")
    if body.member_id is not None and "carbon:write" in scopes:
        raise HTTPException(400, "โทเคนที่ผูกกับสมาชิกรายเดียวใช้ได้เฉพาะสิทธิ์อ่าน")
    return auth.create_token(name, scopes, body.member_id)


@app.post("/api/admin/tokens/{tid}/revoke")
def revoke_token(tid: int, _: dict = Depends(auth.need("admin"))):
    if not db.query("SELECT 1 FROM api_tokens WHERE id = ?", (tid,)):
        raise HTTPException(404, "ไม่พบโทเคน")
    db.execute("UPDATE api_tokens SET revoked_at = COALESCE(revoked_at, ?) WHERE id = ?", (time.time(), tid))
    return {"ok": True}


def _public_report(rep: dict) -> dict:
    """รูปแบบข้อมูลคาร์บอนที่ส่งให้ระบบภายนอก"""
    return {
        "generated_at": datetime.now(BKK).isoformat(timespec="seconds"),
        "unit": {"weight": "kg", "avoided_emissions": "kgCO2e", "recycling_emissions": "kgCO2e"},
        "disclaimer": "ประมาณการจากน้ำหนักจริงที่รับ ยังไม่ใช่คาร์บอนเครดิตที่ผ่านการทวนสอบ",
        # co2e_kg คือค่าที่หลีกเลี่ยงได้ (ชื่อเดิม คงไว้ให้ระบบที่เรียกอยู่แล้ว) recycling_co2e_kg คือการปล่อยสำหรับ Scope 3 หมวด 5
        "fields": {"co2e_kg": "ก๊าซเรือนกระจกที่หลีกเลี่ยงได้โดยประมาณ ไม่ใช่ตัวเลขสำหรับบัญชีการปล่อยขององค์กร",
                   "recycling_co2e_kg": "การปล่อยจากกระบวนการรีไซเคิล ใช้กับ Scope 3 หมวด 5 ห้ามนำไปหักกับ co2e_kg"},
        "factor_source": rep["factor_source"], "factors": {k: v["kg_co2e_per_kg"] for k, v in rep["factors"].items()},
        "inventory_factor_source": rep["inventory_source"],
        "inventory_factors": {k: v["kg_co2e_per_kg"] for k, v in rep["inventory_factors"].items()},
        "total": {k: rep["total"][k] for k in ("kg", "co2e_kg", "recycling_co2e_kg", "by_material")},
        "monthly": [{k: m[k] for k in ("month", "kg", "co2e_kg", "recycling_co2e_kg", "by_material")} for m in rep["monthly"]],
        "members": [{k: m[k] for k in ("member_id", "name", "kind", "pickups", "kg", "co2e_kg", "recycling_co2e_kg", "by_material")}
                    for m in rep["members"]],
    }


@app.get("/api/v1/carbon/summary")
def v1_carbon_summary(client: dict = Depends(auth.api_client("carbon:read"))):
    """ให้ระบบภายนอกดึงข้อมูลคาร์บอน โทเคนที่ผูกกับสมาชิกรายเดียวจะได้เฉพาะข้อมูลของสมาชิกรายนั้น"""
    return _public_report(carbon_report(client["member_id"]))


@app.get("/api/v1/carbon/members/{member_id}")
def v1_carbon_member(member_id: int, client: dict = Depends(auth.api_client("carbon:read"))):
    if client["member_id"] is not None and client["member_id"] != member_id:
        raise HTTPException(403, "โทเคนนี้เห็นได้เฉพาะสมาชิกที่ผูกไว้")
    if not db.query("SELECT 1 FROM members WHERE id = ?", (member_id,)):
        raise HTTPException(404, "ไม่พบสมาชิก")
    return _public_report(carbon_report(member_id))


@app.get("/api/v1/carbon/factors")
def v1_carbon_factors(_: dict = Depends(auth.api_client("carbon:read"))):
    return carbon.current()


@app.put("/api/v1/carbon/factors")
def v1_set_carbon_factors(body: FactorsIn, client: dict = Depends(auth.api_client("carbon:write"))):
    """รับชุดค่าปัจจัยการปล่อยจากภายนอก เช่น ค่าที่ อบก. ประกาศ แล้วใช้กับการคำนวณทั้งระบบทันที"""
    try:
        return carbon.update(body.model_dump(), client["name"])
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))


@app.delete("/api/v1/carbon/factors")
def v1_reset_carbon_factors(_: dict = Depends(auth.api_client("carbon:write"))):
    """กลับไปใช้ค่าตั้งต้น"""
    return carbon.reset()


# ---------- เชื่อมต่อ GrowGreen: ส่งน้ำหนักที่รับจริงของบริษัทเข้าบัญชีคาร์บอนเป็นเอกสารร่าง ----------

def _gg_member(u: dict, member_id: int | None = None) -> int:
    """สมาชิกที่คำสั่งนี้ทำกับ: สมาชิกทำได้เฉพาะของตัวเองและต้องเป็นบริษัท ผู้ดูแลต้องระบุสมาชิก"""
    mid = u["ref_id"] if u["role"] == "user" else member_id
    rows = db.query("SELECT kind FROM members WHERE id = ?", (mid,)) if mid else []
    if not rows:
        raise HTTPException(404, "ไม่พบสมาชิก")
    if rows[0]["kind"] != "company":
        raise HTTPException(403, "การเชื่อมต่อ GrowGreen ใช้กับสมาชิกประเภทบริษัทเท่านั้น")
    return mid


def _gg_request(u: dict, rid: int) -> int:
    """ตรวจว่าผู้ใช้มีสิทธิ์กับคำขอนี้: สมาชิกเห็นเฉพาะคำขอของตัวเอง"""
    rows = db.query("SELECT member_id FROM requests WHERE id = ?", (rid,))
    if not rows or (u["role"] == "user" and rows[0]["member_id"] != u["ref_id"]):
        raise HTTPException(404, "ไม่พบคำขอ")
    return _gg_member(u, rows[0]["member_id"])


@app.get("/api/growgreen")
def growgreen_overview(u: dict = Depends(auth.need("admin", "user"))):
    return growgreen.overview(_gg_member(u) if u["role"] == "user" else None)


@app.put("/api/growgreen/link")
def growgreen_link(body: GrowGreenLinkIn, u: dict = Depends(auth.need("admin", "user"))):
    """บันทึก API key ของ GrowGreen ถ้าเซิร์ฟเวอร์ตั้งที่อยู่ของ GrowGreen ไว้ จะตรวจ key ก่อนบันทึก"""
    mid = _gg_member(u, body.member_id)
    try:
        return growgreen.save_link(mid, body.api_key, body.site_code, body.auto_push)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except growgreen.GrowGreenError as e:
        raise HTTPException(502, str(e))


@app.delete("/api/growgreen/link")
def growgreen_unlink(member_id: int | None = None, u: dict = Depends(auth.need("admin", "user"))):
    growgreen.delete_link(_gg_member(u, member_id))
    return {"ok": True}


@app.get("/api/growgreen/requests/{rid}/preview")
def growgreen_preview(rid: int, u: dict = Depends(auth.need("admin", "user"))):
    """ข้อมูลที่จะส่งของการรับหนึ่งครั้ง และผลตรวจจาก GrowGreen แบบไม่บันทึก (ถ้าเชื่อมต่อไว้)"""
    _gg_request(u, rid)
    return growgreen.preview(rid)


@app.post("/api/growgreen/requests/{rid}/push")
def growgreen_push(rid: int, u: dict = Depends(auth.need("admin", "user"))):
    """ส่งการรับหนึ่งครั้งเข้า GrowGreen เป็นเอกสารร่าง ใช้กดส่งเอง ส่งใหม่หลังผิดพลาด หรือส่งคำขอที่ติดธงหลังตรวจแล้ว"""
    _gg_request(u, rid)
    try:
        return growgreen.push(rid)
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/api/health")
def health():
    return {"ok": True}


app.mount("/icons", StaticFiles(directory=os.environ.get("ICON_DIR", str(BASE / "icons")), check_dir=False), name="icons")
app.mount("/", StaticFiles(directory=str(BASE / "web"), html=True), name="web")
