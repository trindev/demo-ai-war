"""ส่งน้ำหนักที่รับจริงของสมาชิกประเภทบริษัท เข้าระบบบัญชีคาร์บอน GrowGreen เป็นเอกสารร่าง

ส่งเฉพาะ "กิโลกรัมต่อชนิดวัสดุ" ไม่ส่งตัวเลข CO2e ไปด้วย GrowGreen คำนวณการปล่อยด้วยค่าปัจจัยของตัวเอง
(หมวด 3-5-3 การรีไซเคิลของเสีย ใน Scope 3) และเอกสารที่ได้เป็นร่าง ต้องมีคนของบริษัทตรวจและกดส่งอนุมัติเอง

ที่อยู่ของ API ตั้งที่เซิร์ฟเวอร์ด้วยตัวแปร GROWGREEN_API_URL เท่านั้น สมาชิกใส่ได้เฉพาะ API key กับรหัสสถานที่
เพื่อไม่ให้ใครสั่งให้เซิร์ฟเวอร์นี้เรียกไปยังที่อยู่อื่นได้ ถ้าไม่ได้ตั้งค่าไว้ ระบบทำงานในโหมดดูตัวอย่าง: แสดงข้อมูลที่จะส่ง แต่ไม่ส่งจริง
"""
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from . import db, settings
from .config import GROWGREEN_ACTIVITY, GROWGREEN_HOLD_FLAGS, GROWGREEN_VENDOR
from .estimate import estimate

BKK = timezone(timedelta(hours=7))
TIMEOUT_S = 12
LOCAL_HOSTS = ("localhost", "127.0.0.1", "host.docker.internal")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """ไม่ตามการเปลี่ยนเส้นทาง: urllib จะเปลี่ยน POST เป็น GET และส่ง API key ต่อไปยังปลายทางใหม่"""

    def redirect_request(self, *_args, **_kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect)
# ส่งทีละรายการ: การส่งอัตโนมัติหลังปิดรอบกับการกดส่งเองอาจมาพร้อมกัน คนที่มาทีหลังจะเห็นว่าส่งแล้วและไม่ส่งซ้ำ
_push_lock = threading.Lock()


class GrowGreenError(Exception):
    """เรียก GrowGreen ไม่สำเร็จ ข้อความใช้แสดงให้ผู้ใช้เห็นได้ records คือผลตรวจรายบรรทัด (ถ้ามี)"""

    def __init__(self, message: str, records: list | None = None, status: int | None = None):
        super().__init__(message)
        self.records = records or []
        self.status = status   # รหัส HTTP ที่ GrowGreen ตอบ ว่าง = ไม่ได้คำตอบ จึงไม่รู้ว่าฝั่งโน้นบันทึกไปแล้วหรือยัง


def api_url() -> str:
    """ที่อยู่ของ GrowGreen ต้องเป็น https ยกเว้นเครื่องเดียวกัน (ใช้ทดสอบ) เพราะ API key ถูกส่งไปในส่วนหัวทุกครั้ง"""
    url = (os.environ.get("GROWGREEN_API_URL") or "").strip().rstrip("/")
    host = urllib.parse.urlsplit(url).hostname or ""
    if url.startswith("https://") or (url.startswith("http://") and host in LOCAL_HOSTS):
        return url
    return ""


def configured() -> bool:
    return bool(api_url())


def server_key() -> str:
    """API key ที่ตั้งไว้ที่เซิร์ฟเวอร์ (GROWGREEN_API_KEY) ใช้เมื่อบริษัทกดเชื่อมต่อโดยไม่ใส่ key ของตัวเอง เหมาะกับเดโมที่มีองค์กรเดียว"""
    return (os.environ.get("GROWGREEN_API_KEY") or "").strip()


def config_problem() -> str:
    """ข้อความเมื่อค่าที่เซิร์ฟเวอร์ตั้งไว้ใช้ไม่ได้ เพื่อให้หน้าเว็บบอกสาเหตุ แทนที่จะเงียบและอยู่ในโหมดดูตัวอย่าง"""
    raw = (os.environ.get("GROWGREEN_API_URL") or "").strip()
    if raw.startswith("gg_"):
        return "GROWGREEN_API_URL มีค่าเป็น API key ให้ย้าย key ไปที่ GROWGREEN_API_KEY และใส่ที่อยู่ของ GrowGreen (ลงท้ายด้วย /api/v1) แทน"
    if raw and not api_url():
        return "GROWGREEN_API_URL ต้องขึ้นต้นด้วย https://"
    if not raw and server_key():
        return "ตั้ง GROWGREEN_API_KEY ไว้แล้ว แต่ยังไม่ได้ตั้ง GROWGREEN_API_URL"
    return ""


# ---------- การเชื่อมต่อของสมาชิก ----------

def _public(link: dict) -> dict:
    """ข้อมูลการเชื่อมต่อที่ส่งให้หน้าเว็บ ไม่มีตัว API key"""
    return {k: link[k] for k in ("member_id", "key_hint", "site_code", "auto_push", "org_name", "org_code", "updated_at", "checked_at")}


def get_link(member_id: int, with_key: bool = False) -> dict | None:
    rows = db.query("SELECT * FROM growgreen_links WHERE member_id = ?", (member_id,))
    if not rows:
        return None
    rows[0]["auto_push"] = bool(rows[0]["auto_push"])
    return rows[0] if with_key else _public(rows[0])


def save_link(member_id: int, api_key: str, site_code: str, auto_push: bool) -> dict:
    """บันทึกการเชื่อมต่อ ถ้าตั้งที่อยู่ของ GrowGreen ไว้ จะตรวจ key กับ GrowGreen ก่อนบันทึก

    api_key ว่าง = ใช้ key เดิม (แก้เฉพาะรหัสสถานที่หรือการส่งอัตโนมัติ)
    """
    old = get_link(member_id, with_key=True)
    api_key = api_key.strip() or (old["api_key"] if old else "") or server_key()
    site_code = site_code.strip()[:40]
    if not 20 <= len(api_key) <= 200 or any(c.isspace() for c in api_key):
        raise ValueError("API key ไม่ถูกต้อง คัดลอกจากหน้า API keys ของ GrowGreen")
    org_name, org_code, checked_at = "", "", None
    if configured():
        info = _call("GET", "", api_key)
        if not isinstance(info, dict):
            raise GrowGreenError("GrowGreen ตอบกลับมาในรูปแบบที่อ่านไม่ได้", status=200)
        scopes = (info.get("key") or {}).get("scopes") or []
        if "activity:write" not in scopes:
            raise ValueError("API key นี้ไม่มีสิทธิ์ activity:write จึงส่งข้อมูลกิจกรรมไม่ได้")
        # รหัสสถานที่: ตรวจกับรายการของ GrowGreen ถ้าองค์กรมีสถานที่เดียวก็เติมให้เอง
        sites = [str(s.get("code") or "") for s in _call_list("/sites", api_key)]
        allowed = (info.get("key") or {}).get("siteCodes") or []
        sites = [s for s in sites if s and (not allowed or s in allowed)]
        if not site_code and len(sites) == 1:
            site_code = sites[0]
        elif sites and site_code not in sites:
            raise ValueError(("ไม่พบรหัสสถานที่นี้ใน GrowGreen " if site_code else "องค์กรนี้มีหลายสถานที่ ต้องระบุรหัสสถานที่ ")
                             + f"รหัสที่ใช้ได้: {', '.join(sites) or 'ไม่มี'}")
        org = info.get("organization") or {}
        org_name, org_code, checked_at = str(org.get("name") or "")[:120], str(org.get("code") or "")[:40], time.time()
    db.execute(
        "INSERT INTO growgreen_links(member_id, api_key, key_hint, site_code, auto_push, org_name, org_code, updated_at, checked_at)"
        " VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(member_id) DO UPDATE SET api_key=excluded.api_key, key_hint=excluded.key_hint,"
        " site_code=excluded.site_code, auto_push=excluded.auto_push, org_name=excluded.org_name, org_code=excluded.org_code,"
        " updated_at=excluded.updated_at, checked_at=excluded.checked_at",
        (member_id, api_key, api_key[:12] + "…", site_code, int(auto_push), org_name, org_code, time.time(), checked_at),
    )
    return get_link(member_id)


def delete_link(member_id: int) -> None:
    db.execute("DELETE FROM growgreen_links WHERE member_id = ?", (member_id,))


# ---------- ข้อมูลที่ส่ง ----------

def reference_no(req: dict) -> str:
    """เลขอ้างอิงของการรับหนึ่งครั้ง GrowGreen ใช้เลขนี้คู่กับชื่อผู้ให้บริการ เพื่อปฏิเสธการส่งซ้ำ"""
    return f"YT-{req['id']}-{req['code']}"


def kg_by_material(req: dict, mats: dict | None = None) -> dict[str, float]:
    """น้ำหนักจริงของถุงที่พบ แบ่งตามชนิดวัสดุ ด้วยสัดส่วนของของในถุงนั้น (วิธีเดียวกับรายงานคาร์บอน)"""
    mats = mats or settings.materials()
    out: dict[str, float] = {}
    for b in req["bags"]:
        if not b.get("found"):
            continue
        for part in estimate(b["items"], mats)["materials"]:
            out[part["material"]] = out.get(part["material"], 0.0) + part["share"] * (b.get("actual_kg") or 0)
    return out


def build_records(req: dict, site_code: str = "") -> list[dict]:
    """บรรทัดข้อมูลกิจกรรมของการรับหนึ่งครั้ง: หนึ่งบรรทัดต่อกิจกรรมรีไซเคิลของ GrowGreen หน่วยกิโลกรัม"""
    mats = settings.materials()
    by_activity: dict[str, dict] = {}
    for material, kg in kg_by_material(req, mats).items():
        code = GROWGREEN_ACTIVITY.get(material)
        if not code or kg <= 0:
            continue
        row = by_activity.setdefault(code, {"kg": 0.0, "labels": []})
        row["kg"] += kg
        row["labels"].append(mats[material]["label"])
    day = datetime.fromtimestamp(req["collected_at"] or req["created_at"], BKK).date().isoformat()
    found = sum(1 for b in req["bags"] if b.get("found"))
    ref = reference_no(req)
    records = []
    for code, row in sorted(by_activity.items()):
        if round(row["kg"], 3) <= 0:
            continue
        rec = {
            "externalId": f"{ref}:{code}", "activityCode": code, "quantity": round(row["kg"], 3), "unitCode": "KG",
            "startDate": day, "itemName": ("รีไซเคิล: " + ", ".join(row["labels"]))[:200],
            "referenceNo": ref, "vendorName": GROWGREEN_VENDOR,
            "remark": f"รับถึงที่ ยืนยันจุดด้วย QR และคนขับชั่งน้ำหนักจริง {found} ถุง (คำขอ #{req['id']})"[:500],
        }
        if site_code:
            rec["siteCode"] = site_code
        records.append(rec)
    return records


# ---------- เรียก GrowGreen ----------

def _call(method: str, path: str, api_key: str, body: dict | None = None, query: dict | None = None,
          headers: dict | None = None) -> dict:
    url = f"{api_url()}/ext{path}" + (f"?{urllib.parse.urlencode(query)}" if query else "")
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {api_key}", "Accept": "application/json", "User-Agent": "recycling-pickup-demo",
        **({"Content-Type": "application/json"} if data is not None else {}), **(headers or {}),
    })
    try:
        with _opener.open(req, timeout=TIMEOUT_S) as res:
            out = json.loads(res.read().decode() or "{}")
        # คำตอบที่สำเร็จของ GrowGreen ห่ออยู่ใน {"data": ...} ส่วนคำตอบที่ผิดพลาดเป็น {"error": ..., "records": ...}
        if isinstance(out, dict) and "data" in out:
            out = out["data"]
        if not isinstance(out, (dict, list)):
            raise GrowGreenError("GrowGreen ตอบกลับมาในรูปแบบที่อ่านไม่ได้", status=200)
        return out
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode() or "{}")
        except ValueError:
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        err = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        message = err.get("message") or {401: "API key ไม่ถูกต้องหรือถูกยกเลิกแล้ว", 403: "API key นี้ไม่มีสิทธิ์ทำรายการนี้",
                                         429: "เรียก GrowGreen ถี่เกินโควตา ลองใหม่ภายหลัง"}.get(e.code, "GrowGreen ตอบผิดพลาด")
        if 300 <= e.code < 400:
            message = "ที่อยู่ของ GrowGreen ถูกเปลี่ยนเส้นทาง ตรวจค่า GROWGREEN_API_URL"
        raise GrowGreenError(f"GrowGreen ตอบ {e.code}: {message}", payload.get("records"), e.code) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise GrowGreenError("เชื่อมต่อ GrowGreen ไม่ได้ ลองใหม่อีกครั้ง") from e
    except ValueError as e:
        raise GrowGreenError("GrowGreen ตอบกลับมาในรูปแบบที่อ่านไม่ได้") from e


def _call_list(path: str, api_key: str) -> list[dict]:
    out = _call("GET", path, api_key)
    return [x for x in out if isinstance(x, dict)] if isinstance(out, list) else []


def _problems(records: list) -> list[str]:
    """ข้อความปัญหารายบรรทัดจากคำตอบของ GrowGreen"""
    out = []
    for r in records or []:
        for issue in (r.get("errors") or []) if isinstance(r, dict) else []:
            out.append(f"บรรทัด {int(r.get('index', 0)) + 1} {issue.get('field', '')}: {issue.get('message', '')}".strip())
    return out[:20]


def _load(request_id: int) -> dict:
    rows = db.query("SELECT r.*, m.kind AS member_kind FROM requests r JOIN members m ON m.id = r.member_id WHERE r.id = ?", (request_id,))
    if not rows:
        raise LookupError("ไม่พบคำขอ")
    req = rows[0]
    for key in ("bags", "flags"):
        req[key] = json.loads(req[key])
    return req


def hold_reasons(req: dict) -> list[str]:
    """ธงที่ทำให้ไม่ส่งอัตโนมัติ: น้ำหนักหรือของในถุงยังมีข้อสงสัย ต้องมีคนตัดสินใจส่งเอง"""
    return [f for f in req["flags"] if f in GROWGREEN_HOLD_FLAGS]


def preview(request_id: int) -> dict:
    """ข้อมูลที่จะส่งของการรับหนึ่งครั้ง ถ้าเชื่อมต่อไว้ ให้ GrowGreen ตรวจและคำนวณให้ดูโดยไม่บันทึก (dryRun)"""
    req = _load(request_id)
    link = get_link(req["member_id"], with_key=True)
    records = build_records(req, link["site_code"] if link else "")
    out = {"request_id": request_id, "reference_no": reference_no(req), "records": records, "hold": hold_reasons(req),
           "checked": False, "emission_kgco2e": None, "problems": [], "error": "", "filed": False, "documents": []}
    done = push_status(request_id)
    if done and done["status"] == "filed":   # ส่งแล้ว: แสดงผลของครั้งที่ส่ง ไม่ตรวจซ้ำ เพราะ GrowGreen จะปฏิเสธเลขอ้างอิงที่มีอยู่แล้ว
        out.update(filed=True, documents=done["documents"], emission_kgco2e=done["emission_kgco2e"])
    elif not records:
        out["error"] = "ไม่มีน้ำหนักของวัสดุที่ส่งเข้า GrowGreen ได้"
    elif link and configured():
        try:
            res = _call("POST", "/activity-data", link["api_key"], {"records": records}, {"dryRun": "true"})
            res = res if isinstance(res, dict) else {}
            by_code = {r.get("activityCode"): r.get("emissionKgco2e") for r in res.get("records") or [] if isinstance(r, dict)}
            for rec in records:   # การปล่อยของแต่ละบรรทัดตามที่ GrowGreen คำนวณ ใช้แสดงในตัวอย่างเท่านั้น
                rec["emissionKgco2e"] = by_code.get(rec["activityCode"])
            out.update(checked=True, emission_kgco2e=res.get("totalKgco2e"))
        except GrowGreenError as e:
            out.update(error=str(e), problems=_problems(e.records))
    return out


def _record_push(req: dict, status: str, **fields) -> dict:
    row = {"documents": "[]", "emission_kgco2e": None, "kg": None, "error": "", "resend": "", **fields}
    db.execute(
        "INSERT INTO growgreen_pushes(request_id, member_id, status, reference_no, documents, emission_kgco2e, kg, error, resend, attempts, at)"
        " VALUES(?,?,?,?,?,?,?,?,?,1,?) ON CONFLICT(request_id) DO UPDATE SET status=excluded.status, documents=excluded.documents,"
        " reference_no=excluded.reference_no, resend=excluded.resend,"
        " emission_kgco2e=excluded.emission_kgco2e, kg=excluded.kg, error=excluded.error, attempts=growgreen_pushes.attempts+1, at=excluded.at"
        # รายการที่ส่งสำเร็จแล้วไม่ถูกเขียนทับด้วยผลของการส่งซ้ำ เว้นแต่แถวนั้นเป็นของคำขอเก่าที่เลขซ้ำกันหลังรีเซ็ตข้อมูล
        " WHERE growgreen_pushes.status != 'filed' OR growgreen_pushes.reference_no != excluded.reference_no",
        (req["id"], req["member_id"], status, reference_no(req), row["documents"], row["emission_kgco2e"], row["kg"], row["error"][:600],
         row["resend"], time.time()),
    )
    return push_status(req["id"])


def push_status(request_id: int) -> dict | None:
    """สถานะการส่งของคำขอนี้ จับคู่ด้วยเลขอ้างอิง (เลขคำขอ + รหัสรับของ) เพราะเลขคำขอถูกใช้ซ้ำได้หลังรีเซ็ตข้อมูลตัวอย่าง"""
    rows = db.query("SELECT p.* FROM growgreen_pushes p JOIN requests r ON r.id = p.request_id"
                    " WHERE p.request_id = ? AND p.reference_no = 'YT-' || r.id || '-' || r.code", (request_id,))
    if not rows:
        return None
    rows[0]["documents"] = json.loads(rows[0]["documents"])
    rows[0].pop("resend", None)
    return rows[0]


def push(request_id: int, auto: bool = False) -> dict:
    """ส่งการรับหนึ่งครั้งเข้า GrowGreen เป็นเอกสารร่าง คืนสถานะล่าสุดของการส่ง

    auto=True คือการส่งอัตโนมัติหลังรถส่งของที่ศูนย์: คำขอที่ติดธงจะถูกพักไว้ (held) ให้คนตัดสินใจกดส่งเอง
    """
    with _push_lock:
        return _push(request_id, auto)


def _push(request_id: int, auto: bool) -> dict:
    req = _load(request_id)
    if req["status"] != "delivered":
        raise ValueError("ส่งได้เฉพาะการรับที่ส่งถึงศูนย์คัดแยกแล้ว")
    done = push_status(request_id)
    if done and done["status"] == "filed":
        return done
    link = get_link(req["member_id"], with_key=True)
    if not link:
        raise ValueError("สมาชิกรายนี้ยังไม่ได้เชื่อมต่อ GrowGreen")
    if not configured():
        raise ValueError("เซิร์ฟเวอร์นี้ยังไม่ได้ตั้งที่อยู่ของ GrowGreen (GROWGREEN_API_URL) จึงดูตัวอย่างได้อย่างเดียว")
    if auto and hold_reasons(req):
        return _record_push(req, "held", error="ติดธงให้ตรวจ จึงยังไม่ส่งอัตโนมัติ")
    # ถ้าครั้งก่อนไม่ได้คำตอบ (ไม่รู้ว่า GrowGreen บันทึกไปแล้วหรือยัง) ให้ส่งข้อมูลชุดเดิมทุกตัวอักษร
    # เพื่อให้ Idempotency-Key ของ GrowGreen ตอบผลของครั้งแรกกลับมา แทนที่จะปฏิเสธเพราะเนื้อหาเปลี่ยน
    kept = db.query("SELECT resend FROM growgreen_pushes WHERE request_id = ? AND reference_no = ?", (request_id, reference_no(req)))
    records = json.loads(kept[0]["resend"]) if kept and kept[0]["resend"] else build_records(req, link["site_code"])
    if not records:
        return _record_push(req, "failed", error="ไม่มีน้ำหนักของวัสดุที่ส่งเข้า GrowGreen ได้")
    kg = round(sum(r["quantity"] for r in records), 3)
    try:
        res = _call("POST", "/activity-data", link["api_key"], {"reference": reference_no(req), "records": records},
                    headers={"Idempotency-Key": reference_no(req)})
    except GrowGreenError as e:
        unknown = e.status is None or e.status >= 500
        return _record_push(req, "failed", kg=kg, error="; ".join([str(e)] + _problems(e.records)),
                            resend=json.dumps(records, ensure_ascii=False) if unknown else "")
    res = res if isinstance(res, dict) else {}
    docs = [{"no": str(d.get("documentNo") or ""), "status": str(d.get("approvalStatus") or ""), "category": str(d.get("categoryCode") or "")}
            for d in (res.get("documents") if isinstance(res.get("documents"), list) else []) if isinstance(d, dict)]
    if res.get("dryRun") or not any(d["no"] for d in docs):
        # คำตอบ 2xx ที่ไม่มีเลขเอกสาร ไม่นับว่าส่งสำเร็จ (เช่น มีตัวกลางตอบแทน GrowGreen)
        return _record_push(req, "failed", kg=kg, error="GrowGreen ตอบโดยไม่มีเลขเอกสาร จึงยังไม่นับว่าส่งแล้ว ตรวจค่า GROWGREEN_API_URL")
    return _record_push(req, "filed", kg=kg, documents=json.dumps(docs, ensure_ascii=False), emission_kgco2e=res.get("totalKgco2e"))


def push_delivered(request_ids: list[int]) -> None:
    """งานเบื้องหลังหลังรถส่งของที่ศูนย์: ส่งการรับของสมาชิกที่เปิดส่งอัตโนมัติไว้ ความผิดพลาดถูกบันทึกไว้ให้กดส่งใหม่ได้"""
    if not configured():
        return
    for rid in request_ids:
        try:
            req = _load(rid)
            link = get_link(req["member_id"])
            if link and link["auto_push"]:
                push(rid, auto=True)
        except (ValueError, LookupError):
            continue   # ยังไม่เชื่อมต่อ หรือคำขอหายไปแล้ว: ไม่มีอะไรต้องส่ง
        except Exception as e:   # ความผิดพลาดที่ไม่คาดคิดของรายการหนึ่ง ต้องไม่หยุดรายการที่เหลือ และต้องเห็นได้ในหน้าเว็บ
            try:
                _record_push(_load(rid), "failed", error=f"ส่งอัตโนมัติไม่สำเร็จ: {type(e).__name__}")
            except Exception:
                pass


def overview(member_id: int | None = None) -> dict:
    """สถานะการเชื่อมต่อและการส่ง สำหรับหน้าคาร์บอน member_id ว่าง = ทุกบริษัท (ผู้ดูแล)"""
    where, params = ("WHERE r.member_id = ?", (member_id,)) if member_id else ("WHERE m.kind = 'company'", ())
    rows = db.query(
        "SELECT r.id, r.member_id, m.name AS member_name, r.code, r.collected_at, r.created_at, r.actual_kg, r.flags,"
        " p.status AS push_status, p.documents, p.emission_kgco2e, p.error, p.at AS pushed_at"
        f" FROM requests r JOIN members m ON m.id = r.member_id LEFT JOIN growgreen_pushes p ON p.request_id = r.id"
        f" AND p.reference_no = 'YT-' || r.id || '-' || r.code"
        f" {where} AND r.status = 'delivered' ORDER BY r.collected_at DESC LIMIT 60", params)
    for r in rows:
        r["flags"] = json.loads(r["flags"])
        r["hold"] = [f for f in r["flags"] if f in GROWGREEN_HOLD_FLAGS]
        r["documents"] = json.loads(r["documents"]) if r["documents"] else []
        r["reference_no"] = reference_no(r)
    links = db.query("SELECT l.*, m.name AS member_name FROM growgreen_links l JOIN members m ON m.id = l.member_id"
                     + (" WHERE l.member_id = ?" if member_id else "") + " ORDER BY l.member_id", (member_id,) if member_id else ())
    return {
        "configured": configured(), "config_problem": config_problem(), "vendor": GROWGREEN_VENDOR, "activities": GROWGREEN_ACTIVITY,
        "server_key_hint": (server_key()[:12] + "…") if server_key() else "",
        "links": [{**_public({**l, "auto_push": bool(l["auto_push"])}), "member_name": l["member_name"]} for l in links],
        "pickups": rows,
    }
