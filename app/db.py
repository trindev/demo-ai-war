"""SQLite แบบเรียบง่าย: การเชื่อมต่อเดียว + lock เพียงพอสำหรับเดโม"""
import os
import sqlite3
import threading

DB_PATH = os.environ.get("DB_PATH", "/data/app.db")

# เพิ่มเลขนี้เมื่อแก้ SCHEMA หรือข้อมูลตัวอย่าง ระบบจะล้างฐานข้อมูลเดิมแล้วสร้างใหม่ตอนเริ่มทำงาน
SCHEMA_VERSION = "6"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, address TEXT NOT NULL,
    lat REAL NOT NULL, lng REAL NOT NULL, points INTEGER NOT NULL DEFAULT 0,
    kind TEXT NOT NULL DEFAULT 'home',   -- home = ครัวเรือน, company = บริษัทหรืออาคาร
    phone TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    role TEXT NOT NULL,                  -- user | driver | admin | partner
    ref_id INTEGER,                      -- สมาชิก รถ หรือคู่ค้าที่บัญชีนี้ผูกอยู่
    pw_hash TEXT NOT NULL, pw_salt TEXT NOT NULL, quick INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS partners (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL,
    kind TEXT NOT NULL,                  -- factory = โรงงานรีไซเคิล, shop = ร้านรับซื้อของเก่า
    accepts TEXT NOT NULL,               -- JSON: ประเภทวัสดุที่รับ (plastic, paper, metal, glass)
    lat REAL NOT NULL, lng REAL NOT NULL,
    contact_name TEXT NOT NULL, phone TEXT NOT NULL, line_id TEXT NOT NULL, email TEXT NOT NULL, hours TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    partner_id INTEGER NOT NULL, material TEXT NOT NULL, day TEXT NOT NULL, price REAL NOT NULL,
    entered_at REAL,                     -- เวลาที่คู่ค้าบันทึกราคานี้เอง (ว่าง = ข้อมูลจำลองจาก seed)
    PRIMARY KEY (partner_id, material, day)
);
CREATE TABLE IF NOT EXISTS api_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,     -- เก็บเฉพาะ SHA-256 ของโทเคน ตัวโทเคนแสดงครั้งเดียวตอนสร้าง
    prefix TEXT NOT NULL,                -- อักษรต้นของโทเคน ใช้ให้ผู้ดูแลแยกแยะ
    scopes TEXT NOT NULL,                -- JSON: carbon:read, carbon:write
    member_id INTEGER,                   -- ถ้าระบุ โทเคนนี้เห็นข้อมูลของสมาชิกรายนี้เท่านั้น
    created_at REAL NOT NULL, last_used_at REAL, revoked_at REAL
);
CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT, partner_id INTEGER NOT NULL, text TEXT NOT NULL,
    created_at REAL NOT NULL, ack_at REAL
);
CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, capacity_units INTEGER NOT NULL,  -- พื้นที่บรรทุก เทียบเป็นถุงหิ้ว
    color TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT, member_id INTEGER NOT NULL,
    lat REAL NOT NULL, lng REAL NOT NULL,
    slot TEXT NOT NULL, window_start INTEGER NOT NULL, window_end INTEGER NOT NULL,
    bags TEXT NOT NULL,        -- JSON: ถุงแต่ละใบ พร้อมป้าย รายการของข้างใน และผลตรวจรับ
    items TEXT NOT NULL,       -- JSON: รายการรวมทุกถุง
    materials TEXT NOT NULL,   -- JSON: [{material, share}]
    volume INTEGER NOT NULL,   -- พื้นที่บนรถที่ใช้ รวมจากขนาดของทุกถุง
    est_kg REAL NOT NULL, est_value REAL NOT NULL,
    -- pending = รอรับ, verified = คนขับสแกน QR ยืนยันจุดแล้ว, collected = รับของแล้ว, delivered = ส่งถึงศูนย์คัดแยกแล้ว
    status TEXT NOT NULL DEFAULT 'pending',
    code TEXT NOT NULL,              -- รหัสใน QR ของสมาชิก ใช้ยืนยันว่าคนขับมาถูกจุด
    vehicle_id INTEGER,              -- รถที่มารับ
    verified_at REAL, verify_distance_m REAL, collected_at REAL, delivered_at REAL,
    actual_items TEXT,               -- JSON: รายการรวมของถุงที่คนขับพบจริง
    photos TEXT NOT NULL DEFAULT '[]',  -- JSON: รูปย่อ (data URL) ที่สมาชิกแนบ ถุงแต่ละใบอ้างรูปด้วยลำดับ
    flags TEXT NOT NULL DEFAULT '[]',   -- JSON: กรณีที่ผ่อนปรนให้หรือควรให้ผู้ดูแลตรวจ (ดู FLAGS ใน config)
    actual_kg REAL, note TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- สองตารางด้านล่างเพิ่มด้วย IF NOT EXISTS จึงไม่ต้องเพิ่ม SCHEMA_VERSION (ซึ่งจะล้างข้อมูลเดิมทั้งหมด)
CREATE TABLE IF NOT EXISTS growgreen_links (
    member_id INTEGER PRIMARY KEY,       -- สมาชิกประเภทบริษัทที่เชื่อมกับองค์กรใน GrowGreen
    api_key TEXT NOT NULL,               -- ต้องเก็บตัว key เพื่อใช้เรียก GrowGreen ไม่ส่งกลับไปที่หน้าเว็บ (เดโมนี้ไม่ได้เข้ารหัส)
    key_hint TEXT NOT NULL,              -- อักษรต้นของ key ใช้ให้ผู้ใช้แยกแยะ
    site_code TEXT NOT NULL DEFAULT '',  -- รหัสสถานที่ใน GrowGreen (ว่างได้เมื่อองค์กรมีสถานที่เดียว)
    auto_push INTEGER NOT NULL DEFAULT 1,
    org_name TEXT NOT NULL DEFAULT '', org_code TEXT NOT NULL DEFAULT '',
    updated_at REAL NOT NULL, checked_at REAL
);
CREATE TABLE IF NOT EXISTS growgreen_pushes (
    request_id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL,
    status TEXT NOT NULL,                -- filed = ส่งเป็นร่างแล้ว, failed = ส่งไม่สำเร็จ, held = พักไว้เพราะติดธง
    reference_no TEXT NOT NULL,
    documents TEXT NOT NULL DEFAULT '[]',  -- JSON: [{no, status, category}] เอกสารร่างที่ GrowGreen สร้าง
    emission_kgco2e REAL,                -- การปล่อยที่ GrowGreen คำนวณจากค่าปัจจัยของตัวเอง
    kg REAL, error TEXT NOT NULL DEFAULT '',
    resend TEXT NOT NULL DEFAULT '',     -- JSON: ข้อมูลชุดที่ส่งไปแล้วไม่ได้คำตอบ เก็บไว้ส่งซ้ำให้เหมือนเดิมทุกตัวอักษร
    attempts INTEGER NOT NULL DEFAULT 1, at REAL NOT NULL
);
"""


def _c() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init() -> None:
    with _lock:
        _c().executescript(SCHEMA)
        _c().commit()


def query(sql: str, params: tuple = ()) -> list[dict]:
    with _lock:
        return [dict(r) for r in _c().execute(sql, params).fetchall()]


def execute(sql: str, params: tuple = ()) -> int:
    with _lock:
        cur = _c().execute(sql, params)
        _c().commit()
        return cur.lastrowid


def get_kv(key: str) -> str | None:
    rows = query("SELECT value FROM kv WHERE key=?", (key,))
    return rows[0]["value"] if rows else None


def set_kv(key: str, value: str) -> None:
    execute("INSERT INTO kv(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def reset() -> None:
    with _lock:
        _c().executescript("DROP TABLE IF EXISTS members; DROP TABLE IF EXISTS vehicles; DROP TABLE IF EXISTS requests; DROP TABLE IF EXISTS kv;"
                         " DROP TABLE IF EXISTS users; DROP TABLE IF EXISTS sessions; DROP TABLE IF EXISTS partners;"
                         " DROP TABLE IF EXISTS prices; DROP TABLE IF EXISTS notices; DROP TABLE IF EXISTS api_tokens;")
        # growgreen_links และ growgreen_pushes คงไว้: เอกสารที่ส่งไปแล้วยังอยู่ใน GrowGreen และข้อมูลตัวอย่างถูกสร้างด้วยเลขอ้างอิงเดิม
        # ประวัติการส่งจับคู่กับคำขอด้วยเลขอ้างอิง (เลขคำขอ + รหัสรับของ) แถวของคำขอเก่าที่เลขซ้ำกันจึงไม่ถูกนำมาแสดงผิดรายการ
        _c().executescript(SCHEMA)
        _c().commit()
