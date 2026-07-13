# Sigorta Kontrol - Yönetim Paneli PRD

## Problem Statement
"Danışmanların, ay içinde yaptığı TRAFİK KASKO PSA KASKO adetlerini, onaylanmayan kaç adet teklifleri olduğu, ve bunların hangi marka olduğunu yönetebileceğim bir yönetim uygulaması oluştur."

## User Personas
- **Yönetici (Admin):** Tek kullanıcı. Danışman performansını, sigorta onaylarını ve marka bazlı reddedilen teklifleri takip eder.

## User Choices
- Tek admin girişi (email/şifre + JWT)
- Manuel form + Excel toplu yükleme
- Tarih: kaydın oluşturulma tarihi yeterli
- Durum: ONAY / RED / — (YOK) — 3 seçenekli
- Dashboard: danışman aylık istatistikleri, onaylanmayan marka dağılımı, marka toplamları, ay/yıl filtre

## Tech Stack
- **Backend:** FastAPI + MongoDB (motor), JWT auth (PyJWT), bcrypt, pandas + openpyxl (Excel)
- **Frontend:** React 19 + React Router v7, TailwindCSS, Shadcn UI, Recharts, Sonner (toasts), Axios
- **Fonts:** Cabinet Grotesk (heading), Figtree (body), IBM Plex Mono (data)

## Implemented (2026-02-04)

### Backend (`/app/backend/server.py`)
- `POST /api/auth/login` — Email/şifre ile JWT token
- `GET /api/auth/me` — Mevcut kullanıcı
- Admin seed: startup'ta MongoDB'ye admin@sigorta.com / admin123 (env'den) yazılıyor
- `GET/POST/PUT/DELETE /api/records` — CRUD + filtreler (marka, danışman, durum, year, month)
- `POST /api/records/upload` — Excel toplu yükleme (Türkçe başlıklar destekli)
- `GET /api/stats?year=&month=` — KPI + marka dağılımı + danışman detayları
- `GET /api/filters` — Distinct marka/danışman listeleri

### Frontend
- `/login` — Sağda form, solda otomotif showroom görseli
- `/` (Dashboard) — 5 KPI, marka bar chart, onaylanmayan donut chart, danışman performans tablosu, filtrelenebilir kayıt tablosu
- Yeni Kayıt / Düzenle dialog
- Excel Yükle dialog
- Ay/Yıl filtresi ve arama + marka/danışman/durum filtreleri

## Test Credentials
- Email: `admin@sigorta.com`
- Password: `admin123`

## Backlog (P1)
- Danışman ekleme/yönetim ekranı (varsayılan liste)
- Ay bazlı grafik trendleri (line chart)
- CSV/Excel export
- İşlem tarihi alanı (kayıt bazında override)
- Danışman rol/kullanıcı desteği (multi-user)
- Recharts render sırasındaki `width/height=-1` uyarısını gidermek için ResponsiveContainer min-height

## Backlog (P2)
- Bildirim/hatırlatma (RED tekliflerin follow-up'ı)
- Karanlık tema
- Rapor PDF çıktısı

## Next Actions
- Kullanıcı testinden sonra danışman listesi ve rol yönetimi eklenebilir
- Aylık trend grafiği ile karşılaştırmalı analiz

## Changelog

### 2026-02-13 — Combobox + Export
- **Marka / Donanım / Danışman** artık ayrı seçim listelerinden (`/api/options/{kind}`) geliyor:
  - Varsayılan markalar: OPEL, CITROEN, PEUGEOT
  - Varsayılan donanımlar & danışmanlar Excel dosyasından seed edildi
  - Combobox: mevcut değeri seç, ara veya "Yeni ekle" ile anında liste ekle
  - Kayıt kaydı sırasında yeni marka/donanım/danışman otomatik listeye eklenir (manuel + Excel yüklemesi)
- **Excel İndir** ve **PDF İndir** butonları: mevcut ay/yıl + marka/danışman/durum filtrelerine göre indirir.
  - Excel: `/api/export/excel` (`openpyxl`)
  - PDF: `/api/export/pdf` (ReportLab, DejaVu font, ONAY yeşil / RED kırmızı renk kodlu)
