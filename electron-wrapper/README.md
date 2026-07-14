# Sigorta Kontrol - Windows Kurulum Dosyası Oluşturma

Bu klasör, deploy edilmiş web uygulamanızı bir Windows masaüstü uygulaması (.exe) haline getirmenizi sağlar. Emergent platformu masaüstü derlemesi yapmadığı için bu işlemi **kendi Windows bilgisayarınızda** yapmanız gerekir.

## Gereksinimler
1. **Node.js 20+** yüklü olmalı → https://nodejs.org (LTS sürümü indirin)
2. Bu `electron-wrapper/` klasörünü Windows bilgisayarınıza kopyalayın

## Adımlar (Windows PowerShell veya CMD)

```bash
# 1. Klasöre girin
cd electron-wrapper

# 2. Bağımlılıkları yükleyin (ilk seferde birkaç dakika sürer)
npm install

# 3. Uygulamayı önce test edin (bir pencere açılacak)
npm start

# 4. Kurulum dosyasını (.exe installer) oluşturun
npm run build
```

Derleme bittiğinde `dist/` klasörü altında şu dosyalar oluşacak:
- **`Sigorta Kontrol Setup 1.0.0.exe`** — kurulum dosyası (arkadaşlarınıza/ekibinize dağıtabileceğiniz kurulumcu)
- **`win-unpacked/`** — kurulum yapmadan direkt çalıştırılabilir sürüm

## Portable (kurulum gerektirmeyen tek dosya) sürüm
```bash
npm run build:portable
```
`dist/Sigorta Kontrol 1.0.0.exe` dosyası çift tıklayarak direkt çalıştırılabilir.

## İkon Ekleme (opsiyonel)
Kendi ikonunuz için `assets/icon.ico` dosyası oluşturun (256x256 px önerilir). Yoksa Electron varsayılanı kullanılır. `.png` dosyasını `.ico`'ya çevirmek için: https://convertio.co/tr/png-ico/

## Farklı URL için (dev/preview)
`main.js` dosyasında `APP_URL` değerini istediğiniz URL'e değiştirebilirsiniz:
- Production: `https://traffic-kasko-admin.emergent.host`
- Preview: `https://traffic-kasko-admin.preview.emergentagent.com`

## Otomatik Güncelleme
Web uygulamanız Emergent'te güncellendiğinde (Deploy butonuyla), masaüstü uygulamanız bir sonraki açılışta **otomatik olarak** yeni sürümü gösterir — Electron sadece bir tarayıcı penceresi olarak URL'yi açıyor. Yani her seferinde .exe'yi yeniden derlemenize gerek yok.

## Sık Karşılaşılan Hatalar
- **"node veya npm bulunamadı"** → Node.js kurulu değil. https://nodejs.org adresinden LTS sürümü indirin.
- **"electron-builder EACCES"** → PowerShell'i **yönetici olarak** çalıştırın.
- **"Cannot find module 'electron'"** → `npm install` komutunu unutmuşsunuz.
