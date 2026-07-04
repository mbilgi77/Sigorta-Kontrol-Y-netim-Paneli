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
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from starlette.middleware.cors import CORSMiddleware

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
    return doc

@api_router.put("/records/{record_id}", response_model=RecordOut)
async def update_record(record_id: str, body: RecordUpdate, user=Depends(get_current_user)):
    existing = await db.records.find_one({"id": record_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    update = body.model_dump()
    await db.records.update_one({"id": record_id}, {"$set": update})
    existing.update(update)
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
        # sync password to .env value
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
