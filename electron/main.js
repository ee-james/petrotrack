const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width:           1400,
    height:          900,
    minWidth:        900,
    minHeight:       600,
    backgroundColor: '#0d0d0d',
    titleBarStyle:   'hiddenInset',   // clean look on macOS; ignored on Windows/Linux
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      nodeIntegration:  false,
      contextIsolation: true,
      sandbox:          false,         // allow preload to use Node built-ins (path, fs)
      webviewTag:       true,          // enables <webview> in the renderer
    },
  });

  win.loadFile(path.join(__dirname, '../frontend/dist/index.html'));
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
