"""ทดสอบการเชื่อมต่อ GrowGreen และรายงานคาร์บอนสองชุด โดยใช้เซิร์ฟเวอร์ GrowGreen จำลองในเครื่อง

รัน: python -m unittest discover -s tests   (ต้องติดตั้งตาม requirements.txt และ httpx สำหรับ TestClient)
"""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("GROWGREEN_API_URL", None)
os.environ.pop("GROWGREEN_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402

from app import carbon, db, growgreen, main  # noqa: E402

GOOD_KEY = "gg_live_abcdef123456_secretsecretsecret"
READ_ONLY_KEY = "gg_live_readonly0000_secretsecretsecret"
COMPANY, HOME = 25, 1


class FakeGrowGreen(BaseHTTPRequestHandler):
    """ตอบเหมือน /ext ของ GrowGreen เท่าที่ตัวเชื่อมต่อใช้: GET /ext และ POST /ext/activity-data"""
    posts: list = []
    filed_refs: set = set()
    fail_next = 0
    empty_next = 0
    sites = ["S1"]

    def log_message(self, *_):
        pass

    def _send(self, status: int, body: dict):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _key(self) -> str:
        return (self.headers.get("Authorization") or "").removeprefix("Bearer ")

    def do_GET(self):
        if self._key() not in (GOOD_KEY, READ_ONLY_KEY):
            return self._send(401, {"error": {"code": "UNAUTHORIZED", "message": "invalid API key"}})
        # รูปแบบคำตอบคัดจาก GrowGreen จริง (2026-11-24): คำตอบที่สำเร็จห่อใน {"data": ...} และ siteCodes เป็น null เมื่อไม่จำกัด
        if self.path.endswith("/ext/sites"):
            return self._send(200, {"data": [{"code": c, "name": c, "nameTh": c, "departments": []} for c in FakeGrowGreen.sites]})
        scopes = ["activity:read", "activity:write"] if self._key() == GOOD_KEY else ["activity:read"]
        self._send(200, {"data": {"organization": {"code": "DEMO", "name": "Test Organization"}, "key": {"scopes": scopes, "siteCodes": None}}})

    def do_POST(self):
        cls = FakeGrowGreen
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        dry = "dryRun=true" in self.path
        cls.posts.append({"path": self.path, "body": body, "idem": self.headers.get("Idempotency-Key")})
        if self._key() != GOOD_KEY:
            return self._send(401, {"error": {"code": "UNAUTHORIZED", "message": "invalid API key"}})
        if cls.fail_next:
            cls.fail_next -= 1
            return self._send(400, {"error": {"code": "VALIDATION", "message": "invalid records"}, "records": [
                {"index": 0, "status": "error", "errors": [{"field": "activityCode", "code": "unknown", "message": "unknown activity"}]}]})
        if cls.empty_next:
            cls.empty_next -= 1
            return self._send(200, {"items": []})
        ref = body["records"][0]["referenceNo"]
        if not dry and ref in cls.filed_refs:
            return self._send(400, {"error": {"code": "VALIDATION", "message": "duplicate receipt"}, "records": []})
        total = round(sum(r["quantity"] for r in body["records"]) * 0.1, 3)
        if dry:
            return self._send(200, {"data": {"dryRun": True, "totalKgco2e": total, "documents": [{"approvalStatus": "DRAFT"}], "records": [
                {"index": i, "status": "ok", "activityCode": r["activityCode"], "emissionKgco2e": r["quantity"] * 0.1}
                for i, r in enumerate(body["records"])]}})
        cls.filed_refs.add(ref)
        self._send(201, {"data": {"dryRun": False, "totalKgco2e": total, "records": [],
                                  "documents": [{"documentNo": "V-TEST-1", "approvalStatus": "DRAFT", "categoryCode": "3-5"}]}})


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeGrowGreen)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/api/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        db.init()
        main.reseed()
        db.execute("DELETE FROM growgreen_links")
        FakeGrowGreen.posts, FakeGrowGreen.filed_refs, FakeGrowGreen.fail_next, FakeGrowGreen.empty_next = [], set(), 0, 0
        FakeGrowGreen.sites = ["S1"]
        os.environ.pop("GROWGREEN_API_KEY", None)
        db.execute("DELETE FROM growgreen_pushes")
        os.environ["GROWGREEN_API_URL"] = self.url

    def login(self, username: str) -> TestClient:
        c = TestClient(main.app)
        res = c.post("/api/login", json={"username": username, "password": os.environ.get("DEMO_PASSWORD", "demo1234")})
        self.assertEqual(res.status_code, 200)
        return c

    def delivered(self, member: int = COMPANY) -> list[int]:
        return [r["id"] for r in db.query("SELECT id FROM requests WHERE member_id = ? AND status = 'delivered' ORDER BY id", (member,))]


class CarbonTwoLedgers(Base):
    def test_report_carries_both_numbers_and_never_nets_them(self):
        rep = self.login("admin").get("/api/carbon").json()
        total = rep["total"]
        self.assertGreater(total["co2e_kg"], 0)
        self.assertGreater(total["recycling_co2e_kg"], 0)
        # ค่าที่หลีกเลี่ยงได้ต้องคำนวณจากค่าปัจจัยของมันอย่างเดียว ไม่ถูกหักด้วยการปล่อยจากการรีไซเคิล
        self.assertAlmostEqual(total["co2e_kg"], carbon.avoided_kg(total["by_material"]), delta=0.2)
        self.assertAlmostEqual(total["recycling_co2e_kg"], carbon.emitted_kg(total["by_material"]), delta=0.02)
        self.assertLess(total["recycling_co2e_kg"], total["co2e_kg"])
        for row in rep["members"] + rep["monthly"]:
            self.assertIn("recycling_co2e_kg", row)

    def test_no_output_carries_a_netted_figure(self):
        admin = self.login("admin")
        for text in (admin.get("/api/carbon").text, admin.get("/api/v1/carbon/summary").text):
            self.assertNotIn('"net', text.lower())

    def test_inventory_factors_match_the_published_table(self):
        # EPA Hub 2025 ตารางที่ 9 Recycled: Mixed Plastics 0.22, Corrugated 0.11 MTCO2e ต่อ short ton
        self.assertAlmostEqual(carbon.INVENTORY_FACTORS["pet"], 0.2425, places=4)
        self.assertAlmostEqual(carbon.INVENTORY_FACTORS["cardboard"], 0.1213, places=4)
        self.assertEqual(set(carbon.INVENTORY_FACTORS), set(carbon.DEFAULT_FACTORS))

    def test_changing_avoided_factors_leaves_recycling_emissions_alone(self):
        admin = self.login("admin")
        before = admin.get("/api/carbon").json()["total"]
        admin.put("/api/v1/carbon/factors", json={"source": "test", "factors": {"pet": 5, "paper": 5, "cardboard": 5, "aluminum": 5}})
        after = admin.get("/api/carbon").json()["total"]
        self.assertNotEqual(before["co2e_kg"], after["co2e_kg"])
        self.assertEqual(before["recycling_co2e_kg"], after["recycling_co2e_kg"])

    def test_external_api_and_csv_expose_the_second_number(self):
        admin = self.login("admin")
        pub = admin.get("/api/v1/carbon/summary").json()
        self.assertIn("recycling_co2e_kg", pub["total"])
        self.assertIn("inventory_factors", pub)
        self.assertIn("Scope 3", admin.get("/api/carbon.csv").text.splitlines()[0])


class Connector(Base):
    def link(self, client: TestClient, key: str = GOOD_KEY, **extra):
        return client.put("/api/growgreen/link", json={"api_key": key, **extra})

    def test_link_checks_the_key_and_hides_it(self):
        c = self.login("company1")
        res = self.link(c)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["org_name"], "Test Organization")
        self.assertNotIn("api_key", res.json())
        self.assertNotIn(GOOD_KEY, c.get("/api/growgreen").text)

    def test_single_site_is_filled_in_and_several_sites_must_be_chosen(self):
        c = self.login("company1")
        self.assertEqual(self.link(c).json()["site_code"], "S1")
        FakeGrowGreen.sites = ["S1", "S2"]
        self.assertEqual(self.link(c, site_code="").status_code, 400)   # หลายสถานที่: ต้องเลือกเอง
        self.assertEqual(self.link(c, site_code="NOPE").status_code, 400)
        self.assertEqual(self.link(c, site_code="S2").json()["site_code"], "S2")

    def test_server_key_is_used_when_the_member_leaves_the_key_blank(self):
        os.environ["GROWGREEN_API_KEY"] = GOOD_KEY
        c = self.login("company1")
        res = c.put("/api/growgreen/link", json={"api_key": ""})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["org_name"], "Test Organization")
        self.assertNotIn(GOOD_KEY, c.get("/api/growgreen").text)

    def test_key_pasted_into_the_address_setting_is_explained(self):
        os.environ["GROWGREEN_API_URL"] = GOOD_KEY
        view = self.login("admin").get("/api/growgreen").json()
        self.assertFalse(view["configured"])
        self.assertIn("GROWGREEN_API_KEY", view["config_problem"])

    def test_link_refuses_bad_and_read_only_keys(self):
        c = self.login("company1")
        self.assertEqual(self.link(c, "gg_live_wrongwrong00_secretsecretsecret").status_code, 502)
        self.assertEqual(self.link(c, READ_ONLY_KEY).status_code, 400)
        self.assertEqual(self.link(c, "short").status_code, 400)
        self.assertIsNone(growgreen.get_link(COMPANY))

    def test_households_and_other_members_are_refused(self):
        self.assertEqual(self.link(self.login("somchai")).status_code, 403)
        rid = self.delivered()[0]
        other = self.login("company2")
        self.assertEqual(other.get(f"/api/growgreen/requests/{rid}/preview").status_code, 404)
        self.assertEqual(other.post(f"/api/growgreen/requests/{rid}/push").status_code, 404)
        self.assertEqual(self.login("driver1").get("/api/growgreen").status_code, 403)

    def test_records_carry_weighed_kg_per_activity_and_no_co2e(self):
        rid = self.delivered()[0]
        req = growgreen._load(rid)
        records = growgreen.build_records(req, "HQ")
        weighed = sum(b["actual_kg"] for b in req["bags"] if b["found"])
        self.assertAlmostEqual(sum(r["quantity"] for r in records), weighed, delta=0.01)
        self.assertEqual(len({r["activityCode"] for r in records}), len(records))
        for r in records:
            self.assertEqual(r["unitCode"], "KG")
            self.assertEqual(r["siteCode"], "HQ")
            self.assertNotIn("emissionKgco2e", r)
            self.assertTrue(r["referenceNo"].startswith(f"YT-{rid}-"))
            self.assertFalse(any("co2" in k.lower() or "emission" in k.lower() for k in r))

    def test_push_files_a_draft_once(self):
        c = self.login("company1")
        self.link(c)
        rid = self.delivered()[0]
        res = c.post(f"/api/growgreen/requests/{rid}/push").json()
        self.assertEqual(res["status"], "filed")
        self.assertEqual(res["documents"][0], {"no": "V-TEST-1", "status": "DRAFT", "category": "3-5"})
        real = [p for p in FakeGrowGreen.posts if "dryRun" not in p["path"]]
        self.assertEqual(real[0]["idem"], real[0]["body"]["records"][0]["referenceNo"])
        again = c.post(f"/api/growgreen/requests/{rid}/push").json()   # ส่งซ้ำ: ไม่เรียก GrowGreen อีก
        self.assertEqual(again["status"], "filed")
        self.assertEqual(len([p for p in FakeGrowGreen.posts if "dryRun" not in p["path"]]), 1)

    def test_a_later_failure_never_overwrites_a_filed_push(self):
        c = self.login("company1")
        self.link(c)
        rid = self.delivered()[0]
        c.post(f"/api/growgreen/requests/{rid}/push")
        growgreen._record_push(growgreen._load(rid), "failed", error="duplicate receipt")
        self.assertEqual(growgreen.push_status(rid)["status"], "filed")

    def test_failed_push_is_recorded_and_can_be_retried(self):
        c = self.login("company1")
        self.link(c)
        rid = self.delivered()[0]
        FakeGrowGreen.fail_next = 1
        res = c.post(f"/api/growgreen/requests/{rid}/push").json()
        self.assertEqual(res["status"], "failed")
        self.assertIn("unknown activity", res["error"])
        res = c.post(f"/api/growgreen/requests/{rid}/push").json()
        self.assertEqual((res["status"], res["attempts"]), ("filed", 2))

    def test_preview_dry_runs_and_writes_nothing(self):
        c = self.login("company1")
        self.link(c)
        rid = self.delivered()[0]
        pv = c.get(f"/api/growgreen/requests/{rid}/preview").json()
        self.assertTrue(pv["checked"])
        self.assertGreater(pv["emission_kgco2e"], 0)
        self.assertTrue(all("dryRun=true" in p["path"] for p in FakeGrowGreen.posts))
        self.assertIsNone(growgreen.push_status(rid))

    def test_without_server_url_it_previews_but_does_not_send(self):
        os.environ.pop("GROWGREEN_API_URL")
        c = self.login("company1")
        self.assertEqual(self.link(c).status_code, 200)   # บันทึกได้ แต่ยังไม่ได้ตรวจกับ GrowGreen
        rid = self.delivered()[0]
        pv = c.get(f"/api/growgreen/requests/{rid}/preview").json()
        self.assertFalse(pv["checked"])
        self.assertTrue(pv["records"])
        self.assertEqual(c.post(f"/api/growgreen/requests/{rid}/push").status_code, 409)
        self.assertEqual(FakeGrowGreen.posts, [])

    def _collect_one(self, flag: bool) -> int:
        """จำลองการรับของบริษัทหนึ่งครั้งที่ยังอยู่บนรถคัน 1 (สถานะ collected)"""
        rid = self.delivered()[0]
        db.execute("UPDATE requests SET status = 'collected', vehicle_id = 1, delivered_at = NULL, flags = ? WHERE id = ?",
                   (json.dumps(["weight_diff"] if flag else []), rid))
        return rid

    def test_dropoff_pushes_linked_company_automatically(self):
        self.link(self.login("company1"))
        rid = self._collect_one(flag=False)
        self.assertEqual(self.login("driver1").post("/api/dropoff").status_code, 200)
        self.assertEqual(growgreen.push_status(rid)["status"], "filed")

    def test_dropoff_holds_flagged_pickup_until_a_person_sends_it(self):
        c = self.login("company1")
        self.link(c)
        rid = self._collect_one(flag=True)
        self.login("driver1").post("/api/dropoff")
        self.assertEqual(growgreen.push_status(rid)["status"], "held")
        self.assertEqual([p for p in FakeGrowGreen.posts if "dryRun" not in p["path"]], [])
        self.assertEqual(c.post(f"/api/growgreen/requests/{rid}/push").json()["status"], "filed")

    def test_dropoff_respects_auto_push_off_and_survives_an_unreachable_server(self):
        self.link(self.login("company1"), auto_push=False)
        rid = self._collect_one(flag=False)
        self.login("driver1").post("/api/dropoff")
        self.assertIsNone(growgreen.push_status(rid))
        # เปิดส่งอัตโนมัติ แต่ GrowGreen ล่ม: การปิดรอบของคนขับต้องสำเร็จ และบันทึกว่าส่งไม่สำเร็จ
        self.link(self.login("company1"), auto_push=True)
        db.execute("UPDATE requests SET status = 'collected', delivered_at = NULL WHERE id = ?", (rid,))
        os.environ["GROWGREEN_API_URL"] = "http://127.0.0.1:9/api/v1"
        self.assertEqual(self.login("driver1").post("/api/dropoff").status_code, 200)
        self.assertEqual(growgreen.push_status(rid)["status"], "failed")

    def test_admin_sees_all_companies_and_reset_keeps_the_link(self):
        self.link(self.login("company1"))
        admin = self.login("admin")
        view = admin.get("/api/growgreen").json()
        self.assertEqual([l["member_id"] for l in view["links"]], [COMPANY])
        self.assertTrue({r["member_id"] for r in view["pickups"]} >= {25, 26})
        rid = self.delivered()[0]
        admin.post(f"/api/growgreen/requests/{rid}/push")
        admin.post("/api/reset")
        self.assertIsNotNone(growgreen.get_link(COMPANY))
        # ข้อมูลตัวอย่างถูกสร้างด้วยเลขอ้างอิงเดิม รายการที่ส่งไปแล้วจึงยังขึ้นว่าส่งแล้ว ไม่ชวนให้ส่งซ้ำ
        self.assertEqual(growgreen.push_status(rid)["status"], "filed")
        # แถวของคำขอเก่าที่เลขคำขอซ้ำแต่รหัสรับของต่างกัน ไม่ถูกนับเป็นของคำขอใหม่
        db.execute("UPDATE requests SET code = 'ZZZZZZ' WHERE id = ?", (rid,))
        self.assertIsNone(growgreen.push_status(rid))

    def test_unknown_outcome_resends_the_same_body_even_after_settings_change(self):
        c = self.login("company1")
        self.link(c)
        rid = self.delivered()[0]
        os.environ["GROWGREEN_API_URL"] = "http://127.0.0.1:9/api/v1"      # ไม่ได้คำตอบ
        self.assertEqual(c.post(f"/api/growgreen/requests/{rid}/push").json()["status"], "failed")
        first = growgreen.build_records(growgreen._load(rid), "S1")
        os.environ["GROWGREEN_API_URL"] = self.url
        self.login("admin").put("/api/admin/settings", json={"materials": {"pet": {"unit_kg": 0.5}, "paper": {"accepted": False}}})
        self.assertNotEqual(growgreen.build_records(growgreen._load(rid), "S1"), first)
        self.assertEqual(c.post(f"/api/growgreen/requests/{rid}/push").json()["status"], "filed")
        self.assertEqual(FakeGrowGreen.posts[-1]["body"]["records"], first)

    def test_answer_without_documents_is_not_counted_as_filed(self):
        c = self.login("company1")
        self.link(c)
        rid = self.delivered()[0]
        FakeGrowGreen.empty_next = 1
        res = c.post(f"/api/growgreen/requests/{rid}/push").json()
        self.assertEqual(res["status"], "failed")

    def test_plain_http_is_refused_except_on_this_machine(self):
        os.environ["GROWGREEN_API_URL"] = "http://growgreen.example/api/v1"
        self.assertFalse(growgreen.configured())
        os.environ["GROWGREEN_API_URL"] = "https://growgreen.example/api/v1"
        self.assertTrue(growgreen.configured())


if __name__ == "__main__":
    unittest.main()
