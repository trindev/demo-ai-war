"""ค่าตั้งต้นของระบบ: ชนิดวัสดุ ขนาดถุง ช่วงเวลานัด ศูนย์คัดแยก และค่าตั้งต้นของเกณฑ์ที่ผู้ดูแลแก้ได้

ราคา น้ำหนักต่อชิ้น และตำแหน่งต่าง ๆ เป็น "ค่าตัวอย่าง" สำหรับเดโม
ค่าที่ผู้ดูแลระบบแก้ผ่านหน้าหลังบ้านจะเก็บในฐานข้อมูล และทับค่าตั้งต้นในไฟล์นี้ (ดู settings.py)
"""

# price = บาทต่อกิโลกรัมที่ใช้ประเมินมูลค่าให้สมาชิก, unit_kg = น้ำหนักเฉลี่ยต่อชิ้น (กก.), factory = ประเภทโรงงานปลายทาง
MATERIALS = {
    "pet": {"label": "ขวดพลาสติกใส (PET)", "price": 8, "unit_kg": 0.025, "factory": "plastic"},
    "hdpe": {"label": "พลาสติกขุ่น (HDPE)", "price": 6, "unit_kg": 0.05, "factory": "plastic"},
    "other_plastic": {"label": "พลาสติกอื่น ๆ", "price": 2, "unit_kg": 0.02, "factory": "plastic"},
    "cardboard": {"label": "กระดาษลัง", "price": 2, "unit_kg": 0.35, "factory": "paper"},
    "paper": {"label": "กระดาษ", "price": 2, "unit_kg": 0.15, "factory": "paper"},
    "aluminum": {"label": "กระป๋องอะลูมิเนียม", "price": 45, "unit_kg": 0.015, "factory": "metal"},
    "steel": {"label": "กระป๋องเหล็ก/โลหะ", "price": 2.5, "unit_kg": 0.05, "factory": "metal"},
    "glass": {"label": "ขวดแก้ว", "price": 1, "unit_kg": 0.3, "factory": "glass"},
    "non_recyclable": {"label": "ไม่รับ", "price": 0, "unit_kg": 0, "factory": None},
}

# ขนาดถุงใช้จองพื้นที่บนรถ (ของรีไซเคิลเบาแต่กินที่ รถจึงเต็มด้วยปริมาตรก่อนน้ำหนัก)
# units = พื้นที่ที่ใช้ เทียบเป็นจำนวนถุงหิ้ว
SIZES = {
    "S": {"label": "เล็ก (ถุงหิ้ว 1 ใบ)", "units": 1},
    "M": {"label": "กลาง (ถุงดำ 1 ใบ)", "units": 3},
    "L": {"label": "ใหญ่ (หลายถุง/ลัง)", "units": 8},
}

# นาทีนับจากเที่ยงคืน
SLOTS = [
    {"id": "09-11", "label": "09:00–11:00", "start": 540, "end": 660},
    {"id": "11-13", "label": "11:00–13:00", "start": 660, "end": 780},
    {"id": "13-15", "label": "13:00–15:00", "start": 780, "end": 900},
    {"id": "15-17", "label": "15:00–17:00", "start": 900, "end": 1020},
]
SLOT_BY_ID = {s["id"]: s for s in SLOTS}

DEPOT = {"name": "ศูนย์คัดแยก (ตัวอย่าง)", "lat": 13.8050, "lng": 100.5530}

VEHICLE_COLORS = ["#2563eb", "#ea580c", "#7c3aed", "#0891b2"]

# ตัวอักษรของรหัสรับของ ตัดตัวที่อ่านสับสนออก (0/O, 1/I)
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
QR_PREFIX = "YAEKTOOK"

# ป้ายของถุงในหนึ่งคำขอ ถุงใบแรกคือ A (ข้ามตัว I ที่อ่านสับสนกับเลข 1) จึงรับได้สูงสุด 12 ถุงต่อคำขอ
BAG_TAGS = "ABCDEFGHJKLM"

# ---------- เกณฑ์การรับของและการผ่อนปรน (ค่าตั้งต้น ผู้ดูแลแก้ได้ที่หน้าหลังบ้าน) ----------
DEFAULT_SETTINGS = {
    # วัสดุที่รับ ราคา และน้ำหนักต่อชิ้น เติมจาก MATERIALS ตอนโหลด
    "materials": {},
    "min_request_kg": 0.3,            # น้ำหนักรวมขั้นต่ำต่อคำขอ (กก. โดยประมาณ)
    "below_min_policy": "allow_flag",  # block = ไม่รับ, allow_flag = ผ่อนปรนให้รับแต่ติดธง
    "mixed_policy": "warn",            # ถุงที่ของปนกัน: accept รับตามปกติ, warn รับแต่ติดธง, reject ไม่รับ
    "scan_max_distance_m": 200,        # ระยะห่างสูงสุดจากหมุดตอนคนขับสแกน QR
    "scan_far_policy": "allow_flag",   # block = ไม่ให้ยืนยันจุด, allow_flag = ผ่อนปรนแต่ติดธง
    "allow_partial_pickup": True,      # รับได้แม้ไม่พบบางถุง
    "weight_tolerance_pct": 50,        # น้ำหนักจริงต่างจากที่ประเมินเกินกี่เปอร์เซ็นต์จึงติดธง
    "points_per_kg": 10,
    "carbon_price_thb": 100,           # ราคาคาร์บอนที่ใช้ตีมูลค่า (บาทต่อ tCO2e) เป็นค่าสมมติ
    "road_routing": True,              # ใช้บริการเส้นทางตามถนนภายนอก (OSRM สาธารณะ) ในโหมดนำทางของคนขับ
}

POLICIES = {
    "below_min_policy": ("block", "allow_flag"),
    "mixed_policy": ("accept", "warn", "reject"),
    "scan_far_policy": ("block", "allow_flag"),
}

# รหัสธงของคำขอ: กรณีที่ผ่อนปรนให้ หรือควรให้ผู้ดูแลตรวจ
FLAGS = {
    "below_min": "ต่ำกว่าน้ำหนักขั้นต่ำ (ผ่อนปรนให้)",
    "mixed_bag": "มีถุงที่ของปนกัน",
    "scan_far": "สแกนไกลจากหมุดเกินเกณฑ์ (ผ่อนปรนให้)",
    "missing_bag": "ไม่พบบางถุง",
    "mismatch": "ของในถุงไม่ตรงกับที่แจ้ง",
    "weight_diff": "น้ำหนักจริงต่างจากที่ประเมินเกินเกณฑ์",
}

# ---------- แหล่งอ้างอิงของราคารับซื้อ ----------
# ตัวเลขด้านล่างคัดจากหน้าเว็บของแหล่งข่าว (เปิดอ่านเมื่อ 23 พ.ย. 2569) เป็นราคาในอดีต ไม่ใช่ราคาปัจจุบัน
# ใช้เป็นกรอบตั้งต้นของข้อมูลราคาจำลอง และแสดงเป็นที่มาอ้างอิงในหน้ากระดานราคา
PRICE_SOURCES = {
    "sanook2568": {
        "name": "Sanook News", "url": "https://www.sanook.com/news/9853242/",
        "published": "28 ต.ค. 2568", "unit": "บาท/กก.",
        "basis": "ราคาโดยประมาณจากโรงงานและร้านรับซื้อของเก่าทั่วประเทศ ช่วง ส.ค.–ต.ค. 2568",
    },
    "wongpanit2565": {
        "name": "กรุงเทพธุรกิจ (อ้างราคากลางของวงษ์พาณิชย์)", "url": "https://www.bangkokbiznews.com/social/1003317",
        "published": "ข้อมูล ณ 9 พ.ค. 2565", "unit": "บาทต่อหน่วย",
        "basis": "ราคากลางจากวงษ์พาณิชย์ ต้นฉบับระบุว่ากระป๋อง กระดาษ และขวดพลาสติกมักชั่งเป็นกิโลกรัม ส่วนขวดแก้วขายเป็นขวด",
    },
}
# วัสดุ: [(แหล่ง, ชื่อรายการตามต้นฉบับ, ราคาต่ำ, ราคาสูง)] รายการแรกของแต่ละวัสดุใช้เป็นกรอบของข้อมูลจำลอง
PRICE_REFS = {
    "pet": [("sanook2568", "ขวด PET ใส", 9.00, 10.50), ("wongpanit2565", "ขวดน้ำ PET ใส", 13.20, 14.20)],
    "hdpe": [("sanook2568", "พลาสติกขุ่น (HDPE)", 8.00, 8.00), ("wongpanit2565", "ขวดน้ำขาวขุ่น (HDPE)", 5.00, 5.00)],
    "other_plastic": [("sanook2568", "พลาสติกกรอบ/แก้วน้ำ", 3.00, 3.80)],
    "cardboard": [("sanook2568", "กระดาษลัง", 2.45, 3.80), ("wongpanit2565", "กล่องกระดาษแข็งน้ำตาล", 5.50, 5.80)],
    "paper": [("sanook2568", "กระดาษเศษ/จั๊บ", 2.00, 3.00), ("sanook2568", "กระดาษขาว-ดำแผ่น", 4.00, 5.30),
              ("wongpanit2565", "กระดาษหนังสือพิมพ์ หนังสือเล่ม", 3.20, 3.20)],
    "aluminum": [("sanook2568", "อลูมิเนียมกระป๋อง", 60.00, 67.00), ("wongpanit2565", "กระป๋องอะลูมิเนียม", 53.00, 53.00)],
    "steel": [("sanook2568", "เหล็กบาง/สังกะสี", 2.60, 3.80), ("sanook2568", "เหล็กหนา", 7.00, 9.00)],
    # ขวดแก้ว: แหล่งที่พบให้ราคาต่อขวด ไม่มีราคาต่อกิโลกรัม จึงไม่ใช้เป็นกรอบของข้อมูลจำลอง
    "glass": [("wongpanit2565", "ขวดเบียร์สีเขียว (ต่อขวด)", 0.50, 0.50), ("wongpanit2565", "ขวดเบียร์สีชา (ต่อขวด)", 0.30, 0.30)],
}
PRICE_FRAME = {k: v[0][2:] for k, v in PRICE_REFS.items() if k != "glass"}   # (ต่ำ, สูง) ต่อกิโลกรัม

# ---------- คาร์บอน ----------
# ปัจจัยการปล่อยสุทธิของการรีไซเคิล จาก US EPA WARM รุ่น 16 หน่วย MTCO2E ต่อ short ton (ค่าลบ = หลีกเลี่ยงการปล่อย)
# ที่มา: Documentation for Greenhouse Gas Emission and Energy Factors Used in WARM, Management Practices Chapters (ธ.ค. 2566)
# เป็นค่าของสหรัฐฯ ใช้ประมาณการเบื้องต้นเท่านั้น งานที่ต้องยื่นขอคาร์บอนเครดิตต้องใช้ค่าและระเบียบวิธีที่ อบก. รับรอง
WARM_RECYCLING_MTCO2E_PER_SHORT_TON = {
    "pet": -1.04, "hdpe": -0.76, "other_plastic": -0.93,   # other_plastic ใช้ค่า Mixed Plastics
    "cardboard": -3.14, "paper": -3.55,                     # paper ใช้ค่า Mixed Paper (general)
    "aluminum": -9.13, "steel": -1.83, "glass": -0.28,
}
SHORT_TON_KG = 907.185

# การปล่อยจาก "กระบวนการรีไซเคิลเอง" (ขนส่งไปโรงงานและแปรรูป) เป็นคนละตัวเลขกับค่าที่หลีกเลี่ยงได้ด้านบน
# บริษัทใช้ตัวเลขนี้ในบัญชีก๊าซเรือนกระจกขององค์กร Scope 3 หมวด 5 (ของเสียจากการดำเนินงาน) ห้ามนำไปหักกับค่าที่หลีกเลี่ยงได้
# ที่มา: US EPA GHG Emission Factors Hub 2025 ตารางที่ 9 คอลัมน์ Recycled หน่วย MTCO2e ต่อ short ton (ฐาน GWP AR4)
# เป็นชุดเดียวกับที่ระบบ GrowGreen ใช้ในหมวด 3-5-3 ตัวเลขของสองระบบจึงตรงกัน
# pet, hdpe และ other_plastic ใช้ค่า Mixed Plastics; steel ใช้ค่า Mixed Metals; paper ใช้ค่า Mixed Paper (general)
HUB_RECYCLED_MTCO2E_PER_SHORT_TON = {
    "pet": 0.22, "hdpe": 0.22, "other_plastic": 0.22,
    "cardboard": 0.11, "paper": 0.07,
    "aluminum": 0.06, "steel": 0.23, "glass": 0.05,
}
INVENTORY_META = {
    "source": "US EPA GHG Emission Factors Hub 2025 ตารางที่ 9 (Recycled)", "version": "2025",
    "reference_url": "https://www.epa.gov/climateleadership/ghg-emission-factors-hub",
    "note": "ค่าของสหรัฐฯ ฐาน GWP AR4 ใช้กับ Scope 3 หมวด 5 ของผู้ก่อของเสีย ไม่มีค่าที่ อบก. ประกาศแยกรายวัสดุสำหรับการรีไซเคิล",
}

# ---------- เชื่อมต่อ GrowGreen ----------
# วัสดุของระบบนี้ -> รหัสกิจกรรมรีไซเคิลของ GrowGreen (หมวด 3-5-3 หน่วยกิโลกรัม)
GROWGREEN_ACTIVITY = {
    "pet": "RCY_MIXED_PLASTIC", "hdpe": "RCY_MIXED_PLASTIC", "other_plastic": "RCY_MIXED_PLASTIC",
    "cardboard": "RCY_CARDBOARD", "paper": "RCY_MIXED_PAPER",
    "aluminum": "RCY_ALUMINIUM_CAN", "steel": "RCY_MIXED_METAL", "glass": "RCY_GLASS",
}
GROWGREEN_VENDOR = "แยกถูก รับถึงบ้าน"
# คำขอที่ติดธงเหล่านี้จะไม่ถูกส่งอัตโนมัติ ต้องมีคนตรวจแล้วกดส่งเอง
GROWGREEN_HOLD_FLAGS = ("mismatch", "weight_diff")

CARBON_DEFAULT_META = {
    "source": "US EPA WARM รุ่น 16", "version": "ธ.ค. 2566",
    "reference_url": "https://www.epa.gov/system/files/documents/2024-01/warm_management_practices_v16_dec.pdf",
    "effective_date": "2023-12-01",
    "note": "ค่าตั้งต้นเป็นของสหรัฐฯ แทนที่ได้ด้วยค่าของ อบก. ผ่าน API หรือหน้าคาร์บอนของผู้ดูแล",
}
