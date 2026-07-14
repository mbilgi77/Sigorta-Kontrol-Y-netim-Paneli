const { app, BrowserWindow, Menu, shell } = require("electron");
const path = require("path");

// Production URL - üretim ortamındaki uygulamanız
const APP_URL = "https://traffic-kasko-admin.emergent.host";

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: "Sigorta Kontrol Yönetim Paneli",
    icon: path.join(__dirname, "assets", "icon.ico"),
    backgroundColor: "#0f172a",
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  win.loadURL(APP_URL);

  // Yeni pencere yerine varsayılan tarayıcıda aç (dış linkler için)
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(APP_URL)) {
      shell.openExternal(url);
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  // Menü tamamen kaldır (temiz görünüm için)
  Menu.setApplicationMenu(null);
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
