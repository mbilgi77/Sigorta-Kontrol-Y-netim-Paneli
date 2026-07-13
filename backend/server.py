from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import io
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import bcrypt
import jwt
import pandas as pd
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from starlette.middleware.cors import CORSMiddleware
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# ---- Setup ----
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI()
api_router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)

JWT_ALGO = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 7 days for admin convenience

# ---- Utilities ----
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def create_token(email: str) -> str:
    payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "type": "access",
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGO)

async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Yetkisiz")
    try:
        payload = jwt.decode(creds.credentials, os.environ["JWT_SECRET"], algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Oturum süresi doldu")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token")
    email = payload.get("sub")
    user = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
    return user

# ---- Models ----
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    token: str
    user: dict

StatusValue = Literal["ONAY", "RED", "YOK"]

class RecordBase(BaseModel):
    marka: str
    model: str = ""
    donanim: str = ""
    sasi: str = ""
    renk: str = ""
    danisman: str
    musteri: str = ""
    trafik: StatusValue = "YOK"
    kasko: StatusValue = "YOK"
    psa_kasko: StatusValue = "YOK"
    aciklama: str = ""

class RecordCreate(RecordBase):
    pass

class RecordUpdate(RecordBase):
    pass

class RecordOut(RecordBase):
    id: str
    created_at: str

# ---- Options (markalar / donanimlar / danismanlar) ----
OPTION_KINDS = {"brands", "donanims", "consultants"}

DEFAULT_BRANDS = ["OPEL", "CITROEN", "PEUGEOT"]

DEFAULT_DONANIMS = [
    "ALLURE 1.2 PureTech 130hp EAT8 Euro 6.4 (E0)",
    "ALLURE 1.2 PureTech 130 hp EAT8 6.4 (H0)",
    "GT 1.2 PureTech 130hp EAT8",
    "Yeni 3008 e ALLURE 157kW",
    "VIVARO CARGO 2.2 180 HP AT8 ULTIMATE XL",
    "CORSA ELEKTRIK GS_V2 (H6)",
    "CORSA GS 1.2 100HP AT8_V2 (H4)",
    "CORSA 1.2 145 (136 HP) HYBRID E-DCT6 GS",
    "ASTRA 1.2 130 HP AT8 GS",
    "Jumper Van 3.5T L4H2 (15m3) 2.2 BlueHDi 180 AT",
    "C4 X",
]

DEFAULT_CONSULTANTS = [
    "ORHANCAN YILMAZ",
    "EREN TÜRKAN",
    "BATUHAN OLGAÇ",
    "SEHER SÖNMEZ",
    "PINAR YILDIRIM",
    "MEHMET ALİ YAĞCI",
    "BETÜL KARAN",
    "ORÇUN DEMİRAY",
]

async def add_option(kind: str, value: str):
    v = (value or "").strip()
    if not v or kind not in OPTION_KINDS:
        return
    await db.options.update_one(
        {"kind": kind, "value": v},
        {"$setOnInsert": {"kind": kind, "value": v, "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )

class OptionBody(BaseModel):
    value: str

@api_router.get("/options/{kind}")
async def list_options(kind: str, user=Depends(get_current_user)):
    if kind not in OPTION_KINDS:
        raise HTTPException(status_code=400, detail="Geçersiz tür")
    docs = await db.options.find({"kind": kind}, {"_id": 0}).to_list(2000)
    values = sorted({d["value"] for d in docs if d.get("value")})
    return {"kind": kind, "values": values}

@api_router.post("/options/{kind}")
async def add_option_endpoint(kind: str, body: OptionBody, user=Depends(get_current_user)):
    if kind not in OPTION_KINDS:
        raise HTTPException(status_code=400, detail="Geçersiz tür")
    v = body.value.strip()
    if not v:
        raise HTTPException(status_code=400, detail="Boş değer eklenemez")
    await add_option(kind, v)
    return {"success": True, "value": v}

@api_router.delete("/options/{kind}/{value}")
async def delete_option(kind: str, value: str, user=Depends(get_current_user)):
    if kind not in OPTION_KINDS:
        raise HTTPException(status_code=400, detail="Geçersiz tür")
    await db.options.delete_one({"kind": kind, "value": value})
    return {"success": True}


# ---- Auth endpoints ----
@api_router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı")
    token = create_token(email)
    return LoginResponse(
        token=token,
        user={"email": user["email"], "name": user.get("name", "Admin"), "role": user.get("role", "admin")},
    )

@api_router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user

# ---- Record endpoints ----
def normalize_status(v) -> str:
    if v is None:
        return "YOK"
    s = str(v).strip().upper()
    if s in ("ONAY", "APPROVED", "OK"):
        return "ONAY"
    if s in ("RED", "REDDEDILDI", "REJECTED", "REJEKT", "REJECT"):
        return "RED"
    if s in ("X", "-", "—", "YOK", "", "NAN", "NONE"):
        return "YOK"
    # anything else default to YOK
    return "YOK"

@api_router.get("/records")
async def list_records(
    year: Optional[int] = None,
    month: Optional[int] = None,
    marka: Optional[str] = None,
    danisman: Optional[str] = None,
    durum: Optional[str] = None,  # ONAY / RED / YOK - filters by any status field
    user=Depends(get_current_user),
):
    query: dict = {}
    if marka:
        query["marka"] = marka
    if danisman:
        query["danisman"] = danisman
    if durum:
        query["$or"] = [
            {"trafik": durum},
            {"kasko": durum},
            {"psa_kasko": durum},
        ]
    docs = await db.records.find(query, {"_id": 0}).sort("created_at", -1).to_list(5000)
    if year or month:
        filtered = []
        for d in docs:
            try:
                dt = datetime.fromisoformat(d["created_at"])
            except Exception:
                continue
            if year and dt.year != year:
                continue
            if month and dt.month != month:
                continue
            filtered.append(d)
        docs = filtered
    return docs

@api_router.post("/records", response_model=RecordOut)
async def create_record(body: RecordCreate, user=Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    doc = body.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = now
    await db.records.insert_one(doc)
    doc.pop("_id", None)
    # auto-add new options
    await add_option("brands", doc.get("marka", ""))
    await add_option("donanims", doc.get("donanim", ""))
    await add_option("consultants", doc.get("danisman", ""))
    return doc

@api_router.put("/records/{record_id}", response_model=RecordOut)
async def update_record(record_id: str, body: RecordUpdate, user=Depends(get_current_user)):
    existing = await db.records.find_one({"id": record_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    update = body.model_dump()
    await db.records.update_one({"id": record_id}, {"$set": update})
    existing.update(update)
    await add_option("brands", update.get("marka", ""))
    await add_option("donanims", update.get("donanim", ""))
    await add_option("consultants", update.get("danisman", ""))
    return existing

@api_router.delete("/records/{record_id}")
async def delete_record(record_id: str, user=Depends(get_current_user)):
    res = await db.records.delete_one({"id": record_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    return {"success": True}

@api_router.post("/records/upload")
async def upload_records(file: UploadFile = File(...), user=Depends(get_current_user)):
    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel okunamadı: {e}")

    # Normalize headers
    df.columns = [str(c).strip().upper() for c in df.columns]

    col_map = {
        "MARKA": "marka",
        "MODEL": "model",
        "DONANIM": "donanim",
        "ŞASİ": "sasi",
        "SASI": "sasi",
        "RENK": "renk",
        "DANIŞMAN": "danisman",
        "DANISMAN": "danisman",
        "MÜŞTERİ": "musteri",
        "MUSTERI": "musteri",
        "TRAFİK": "trafik",
        "TRAFIK": "trafik",
        "KASKO": "kasko",
        "PSA KASKO": "psa_kasko",
        "AÇIKLAMA": "aciklama",
        "ACIKLAMA": "aciklama",
    }

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    docs = []
    for _, row in df.iterrows():
        rec = {
            "id": str(uuid.uuid4()),
            "marka": "",
            "model": "",
            "donanim": "",
            "sasi": "",
            "renk": "",
            "danisman": "",
            "musteri": "",
            "trafik": "YOK",
            "kasko": "YOK",
            "psa_kasko": "YOK",
            "aciklama": "",
            "created_at": now,
        }
        for col, val in row.items():
            key = col_map.get(col)
            if not key:
                continue
            v = str(val).strip() if val is not None else ""
            if key in ("trafik", "kasko", "psa_kasko"):
                rec[key] = normalize_status(v)
            else:
                rec[key] = v
        # Skip fully empty rows
        if not rec["marka"] and not rec["danisman"] and not rec["sasi"]:
            continue
        if not rec["marka"]:
            rec["marka"] = "BILINMIYOR"
        if not rec["danisman"]:
            rec["danisman"] = "BILINMIYOR"
        docs.append(rec)

    if docs:
        await db.records.insert_many(docs)
        inserted = len(docs)
        # collect new options
        for d in docs:
            await add_option("brands", d.get("marka", ""))
            await add_option("donanims", d.get("donanim", ""))
            await add_option("consultants", d.get("danisman", ""))
    return {"inserted": inserted}

# ---- Stats ----
@api_router.get("/stats")
async def stats(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user=Depends(get_current_user),
):
    docs = await db.records.find({}, {"_id": 0}).to_list(50000)
    if year or month:
        filtered = []
        for d in docs:
            try:
                dt = datetime.fromisoformat(d["created_at"])
            except Exception:
                continue
            if year and dt.year != year:
                continue
            if month and dt.month != month:
                continue
            filtered.append(d)
        docs = filtered

    total = len(docs)
    trafik_onay = sum(1 for d in docs if d.get("trafik") == "ONAY")
    kasko_onay = sum(1 for d in docs if d.get("kasko") == "ONAY")
    psa_onay = sum(1 for d in docs if d.get("psa_kasko") == "ONAY")

    unapproved = [d for d in docs if "RED" in (d.get("trafik"), d.get("kasko"), d.get("psa_kasko"))]
    unapproved_count = len(unapproved)

    # Brand distribution of unapproved
    brand_unapproved: dict = {}
    for d in unapproved:
        brand_unapproved[d.get("marka", "?")] = brand_unapproved.get(d.get("marka", "?"), 0) + 1

    # Brand totals (all records)
    brand_totals: dict = {}
    for d in docs:
        brand_totals[d.get("marka", "?")] = brand_totals.get(d.get("marka", "?"), 0) + 1

    # Per-consultant counts
    consultants: dict = {}
    for d in docs:
        c = d.get("danisman", "?")
        if c not in consultants:
            consultants[c] = {
                "danisman": c,
                "trafik_onay": 0,
                "kasko_onay": 0,
                "psa_kasko_onay": 0,
                "trafik_red": 0,
                "kasko_red": 0,
                "psa_kasko_red": 0,
                "toplam": 0,
            }
        row = consultants[c]
        row["toplam"] += 1
        if d.get("trafik") == "ONAY":
            row["trafik_onay"] += 1
        elif d.get("trafik") == "RED":
            row["trafik_red"] += 1
        if d.get("kasko") == "ONAY":
            row["kasko_onay"] += 1
        elif d.get("kasko") == "RED":
            row["kasko_red"] += 1
        if d.get("psa_kasko") == "ONAY":
            row["psa_kasko_onay"] += 1
        elif d.get("psa_kasko") == "RED":
            row["psa_kasko_red"] += 1

    return {
        "total": total,
        "trafik_onay": trafik_onay,
        "kasko_onay": kasko_onay,
        "psa_kasko_onay": psa_onay,
        "unapproved_count": unapproved_count,
        "brand_unapproved": [{"marka": k, "adet": v} for k, v in sorted(brand_unapproved.items(), key=lambda x: -x[1])],
        "brand_totals": [{"marka": k, "adet": v} for k, v in sorted(brand_totals.items(), key=lambda x: -x[1])],
        "consultants": sorted(consultants.values(), key=lambda x: -x["toplam"]),
    }

@api_router.get("/filters")
async def filters(user=Depends(get_current_user)):
    markalar = await db.records.distinct("marka")
    danismanlar = await db.records.distinct("danisman")
    return {
        "markalar": sorted([m for m in markalar if m]),
        "danismanlar": sorted([d for d in danismanlar if d]),
    }


# ---- Exports ----
async def _query_records_filtered(year, month, marka, danisman, durum):
    query: dict = {}
    if marka:
        query["marka"] = marka
    if danisman:
        query["danisman"] = danisman
    if durum:
        query["$or"] = [{"trafik": durum}, {"kasko": durum}, {"psa_kasko": durum}]
    docs = await db.records.find(query, {"_id": 0}).sort("created_at", -1).to_list(20000)
    if year or month:
        filtered = []
        for d in docs:
            try:
                dt = datetime.fromisoformat(d["created_at"])
            except Exception:
                continue
            if year and dt.year != year:
                continue
            if month and dt.month != month:
                continue
            filtered.append(d)
        docs = filtered
    return docs

STATUS_LABEL = {"ONAY": "ONAY", "RED": "RED", "YOK": "-"}

@api_router.get("/export/excel")
async def export_excel(
    year: Optional[int] = None,
    month: Optional[int] = None,
    marka: Optional[str] = None,
    danisman: Optional[str] = None,
    durum: Optional[str] = None,
    user=Depends(get_current_user),
):
    docs = await _query_records_filtered(year, month, marka, danisman, durum)
    rows = []
    for d in docs:
        rows.append({
            "MARKA": d.get("marka", ""),
            "MODEL": d.get("model", ""),
            "DONANIM": d.get("donanim", ""),
            "ŞASİ": d.get("sasi", ""),
            "RENK": d.get("renk", ""),
            "DANIŞMAN": d.get("danisman", ""),
            "MÜŞTERİ": d.get("musteri", ""),
            "TRAFİK": STATUS_LABEL.get(d.get("trafik", "YOK"), d.get("trafik", "")),
            "KASKO": STATUS_LABEL.get(d.get("kasko", "YOK"), d.get("kasko", "")),
            "PSA KASKO": STATUS_LABEL.get(d.get("psa_kasko", "YOK"), d.get("psa_kasko", "")),
            "AÇIKLAMA": d.get("aciklama", ""),
            "TARIH": (d.get("created_at") or "")[:10],
        })
    df = pd.DataFrame(rows, columns=["MARKA","MODEL","DONANIM","ŞASİ","RENK","DANIŞMAN","MÜŞTERİ","TRAFİK","KASKO","PSA KASKO","AÇIKLAMA","TARIH"])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Kayitlar")
    buf.seek(0)
    fname = f"sigorta-kayitlar-{datetime.now().strftime('%Y%m%d-%H%M')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )

# Register a Unicode font once (for Turkish chars in PDF)
_PDF_FONT = "Helvetica"
_PDF_FONT_BOLD = "Helvetica-Bold"
for _c in [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]:
    try:
        if _c.endswith("Bold.ttf"):
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", _c))
            _PDF_FONT_BOLD = "DejaVuSans-Bold"
        else:
            pdfmetrics.registerFont(TTFont("DejaVuSans", _c))
            _PDF_FONT = "DejaVuSans"
    except Exception:
        pass

@api_router.get("/export/pdf")
async def export_pdf(
    year: Optional[int] = None,
    month: Optional[int] = None,
    marka: Optional[str] = None,
    danisman: Optional[str] = None,
    durum: Optional[str] = None,
    user=Depends(get_current_user),
):
    docs = await _query_records_filtered(year, month, marka, danisman, durum)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=1.2*cm, rightMargin=1.2*cm, topMargin=1*cm, bottomMargin=1*cm,
        title="Sigorta Kontrol Kayitlari",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=styles["Title"], fontName=_PDF_FONT_BOLD, fontSize=16, textColor=colors.HexColor("#0f172a"))
    sub_style = ParagraphStyle("s", parent=styles["Normal"], fontName=_PDF_FONT, fontSize=9, textColor=colors.HexColor("#64748b"))

    story = []
    filt_bits = []
    if year: filt_bits.append(f"Yıl: {year}")
    if month: filt_bits.append(f"Ay: {month}")
    if marka: filt_bits.append(f"Marka: {marka}")
    if danisman: filt_bits.append(f"Danışman: {danisman}")
    if durum: filt_bits.append(f"Durum: {durum}")
    story.append(Paragraph("Sigorta Kontrol - Kayıt Listesi", title_style))
    story.append(Paragraph(
        f"Oluşturulma: {datetime.now().strftime('%d.%m.%Y %H:%M')}  ·  Toplam kayıt: {len(docs)}"
        + (("  ·  Filtre: " + ", ".join(filt_bits)) if filt_bits else ""),
        sub_style,
    ))
    story.append(Spacer(1, 0.4*cm))

    header = ["Marka", "Model", "Danışman", "Müşteri", "ŞASİ", "TRAFİK", "KASKO", "PSA KASKO", "Tarih"]
    data = [header]
    for d in docs:
        data.append([
            d.get("marka",""),
            d.get("model",""),
            d.get("danisman",""),
            d.get("musteri",""),
            d.get("sasi",""),
            STATUS_LABEL.get(d.get("trafik","YOK"), ""),
            STATUS_LABEL.get(d.get("kasko","YOK"), ""),
            STATUS_LABEL.get(d.get("psa_kasko","YOK"), ""),
            (d.get("created_at") or "")[:10],
        ])

    table = Table(data, repeatRows=1, colWidths=[2.4*cm, 2.6*cm, 3.6*cm, 3.6*cm, 4.2*cm, 1.8*cm, 1.8*cm, 2.2*cm, 2.0*cm])
    ts = [
        ("FONTNAME", (0, 0), (-1, -1), _PDF_FONT),
        ("FONTNAME", (0, 0), (-1, 0), _PDF_FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (5, 1), (7, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i, row in enumerate(data[1:], start=1):
        for col_idx in (5, 6, 7):
            val = row[col_idx]
            if val == "ONAY":
                ts.append(("TEXTCOLOR", (col_idx, i), (col_idx, i), colors.HexColor("#059669")))
            elif val == "RED":
                ts.append(("TEXTCOLOR", (col_idx, i), (col_idx, i), colors.HexColor("#e11d48")))
    table.setStyle(TableStyle(ts))
    story.append(table)

    doc.build(story)
    buf.seek(0)
    fname = f"sigorta-kayitlar-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )

@api_router.get("/")
async def root():
    return {"message": "Sigorta Kontrol API"}

# ---- App startup ----
@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.records.create_index("marka")
    await db.records.create_index("danisman")
    await db.records.create_index("created_at")
    await db.options.create_index([("kind", 1), ("value", 1)], unique=True)

    for v in DEFAULT_BRANDS:
        await add_option("brands", v)
    for v in DEFAULT_DONANIMS:
        await add_option("donanims", v)
    for v in DEFAULT_CONSULTANTS:
        await add_option("consultants", v)

    admin_email = os.environ["ADMIN_EMAIL"].lower().strip()
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Admin",
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        if not verify_password(admin_password, existing["password_hash"]):
            await db.users.update_one(
                {"email": admin_email},
                {"$set": {"password_hash": hash_password(admin_password)}},
            )

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

