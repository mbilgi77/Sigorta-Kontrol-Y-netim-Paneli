"""
Tests for the upload-with-year/month bug fix.
POST /api/records/upload now accepts optional multipart form fields `year` and `month`.
When provided, uploaded rows are stamped with created_at = <year>-<month>-15T12:00:00+00:00.
"""
import io
import os
import uuid
import pytest
import requests
import pandas as pd

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://traffic-kasko-admin.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@sigorta.com"
ADMIN_PASSWORD = "admin123"

# Unique per-run tag to identify test rows for later cleanup
RUN_TAG = f"TEST_UPLOAD_MONTH_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _build_xlsx(danisman_tag):
    """Build a small xlsx in-memory with 2 rows tagged uniquely via danisman name."""
    df = pd.DataFrame({
        "MARKA": ["PEUGEOT", "OPEL"],
        "MODEL": ["A", "B"],
        "DANIŞMAN": [f"{danisman_tag}_1", f"{danisman_tag}_2"],
        "TRAFİK": ["ONAY", "ONAY"],
        "KASKO": ["X", "ONAY"],
        "PSA KASKO": ["ONAY", "X"],
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf


def _cleanup(danisman_tag, headers):
    """Delete records created with this tag."""
    try:
        r = requests.get(f"{API}/records", headers=headers, params={"limit": 5000}, timeout=30)
        if r.status_code != 200:
            return
        data = r.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        for rec in items:
            if str(rec.get("danisman", "")).startswith(danisman_tag):
                rid = rec.get("id")
                if rid:
                    requests.delete(f"{API}/records/{rid}", headers=headers, timeout=15)
    except Exception:
        pass


# --- Bug regression: upload with year/month stamps created_at to that period ---
def test_upload_with_year_month_stamps_created_at(auth_headers):
    tag = f"{RUN_TAG}_MARCH"
    try:
        xlsx = _build_xlsx(tag)
        files = {"file": ("upload_march.xlsx", xlsx.getvalue(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {"year": "2025", "month": "3"}
        r = requests.post(f"{API}/records/upload", headers=auth_headers, files=files, data=data, timeout=60)
        assert r.status_code == 200, f"Upload failed: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("inserted", 0) >= 2, f"Expected >=2 inserted, got {body}"

        # Verify via GET /api/records?year=2025&month=3 -- our tag should be there
        r2 = requests.get(f"{API}/records", headers=auth_headers,
                          params={"year": 2025, "month": 3, "limit": 5000}, timeout=30)
        assert r2.status_code == 200, r2.text
        items = r2.json().get("items", r2.json()) if isinstance(r2.json(), dict) else r2.json()
        tagged = [rec for rec in items if str(rec.get("danisman", "")).startswith(tag)]
        assert len(tagged) >= 2, f"Expected uploaded rows to appear when filtered by 2025/3, got {len(tagged)}"
        # Verify created_at is actually inside March 2025
        for rec in tagged:
            ca = rec.get("created_at", "")
            assert ca.startswith("2025-03"), f"created_at not in March 2025: {ca}"
    finally:
        _cleanup(tag, auth_headers)


# --- Backward compatibility: no year/month -> current datetime is used ---
def test_upload_without_year_month_uses_current_datetime(auth_headers):
    from datetime import datetime, timezone
    tag = f"{RUN_TAG}_NOW"
    try:
        xlsx = _build_xlsx(tag)
        files = {"file": ("upload_now.xlsx", xlsx.getvalue(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{API}/records/upload", headers=auth_headers, files=files, timeout=60)
        assert r.status_code == 200, f"Upload without year/month failed: {r.status_code} {r.text}"
        assert r.json().get("inserted", 0) >= 2

        now = datetime.now(timezone.utc)
        r2 = requests.get(f"{API}/records", headers=auth_headers,
                          params={"year": now.year, "month": now.month, "limit": 5000}, timeout=30)
        assert r2.status_code == 200
        items = r2.json().get("items", r2.json()) if isinstance(r2.json(), dict) else r2.json()
        tagged = [rec for rec in items if str(rec.get("danisman", "")).startswith(tag)]
        assert len(tagged) >= 2, f"Expected uploaded rows in current month, found {len(tagged)}"
    finally:
        _cleanup(tag, auth_headers)


# --- Invalid year/month should return 400 with Turkish error 'Geçersiz yıl/ay' ---
def test_upload_invalid_month_returns_400(auth_headers):
    tag = f"{RUN_TAG}_INVALID"
    xlsx = _build_xlsx(tag)
    files = {"file": ("bad.xlsx", xlsx.getvalue(),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    data = {"year": "2025", "month": "13"}
    r = requests.post(f"{API}/records/upload", headers=auth_headers, files=files, data=data, timeout=30)
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    body = r.json()
    detail = body.get("detail", "")
    if isinstance(detail, list):
        detail = " ".join(str(d) for d in detail)
    assert "Geçersiz" in detail and ("yıl" in detail or "ay" in detail), f"Missing Turkish error: {detail}"


# --- /api/stats?year=2025&month=3 should include uploaded batch ---
def test_stats_reflects_uploaded_batch(auth_headers):
    tag = f"{RUN_TAG}_STATS"
    try:
        # Baseline stats
        r_base = requests.get(f"{API}/stats", headers=auth_headers,
                              params={"year": 2025, "month": 3}, timeout=30)
        assert r_base.status_code == 200
        base = r_base.json()
        base_total = base.get("total", 0)

        # Upload 2 rows for March 2025
        xlsx = _build_xlsx(tag)
        files = {"file": ("upload_stats.xlsx", xlsx.getvalue(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {"year": "2025", "month": "3"}
        r = requests.post(f"{API}/records/upload", headers=auth_headers, files=files, data=data, timeout=60)
        assert r.status_code == 200
        inserted = r.json().get("inserted", 0)
        assert inserted >= 2

        # New stats
        r_new = requests.get(f"{API}/stats", headers=auth_headers,
                             params={"year": 2025, "month": 3}, timeout=30)
        assert r_new.status_code == 200
        new = r_new.json()
        new_total = new.get("total", 0)
        assert new_total == base_total + inserted, \
            f"Stats total not updated: base={base_total} new={new_total} inserted={inserted}"

        # Brand totals should include our PEUGEOT/OPEL uploads
        brand_totals = new.get("brand_totals", {}) or new.get("brands", {})
        # brand_totals could be dict or list; normalize to dict
        if isinstance(brand_totals, list):
            brand_totals = {b.get("marka") or b.get("brand"): b.get("count", 0) for b in brand_totals}
        assert brand_totals, f"brand_totals missing in stats response: {new.keys()}"
    finally:
        _cleanup(tag, auth_headers)
