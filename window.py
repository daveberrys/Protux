import os
import sys
import threading

import webview as wv
from src.backend.api import API

if getattr(sys, "frozen", False):
    resourceRoot = os.path.abspath(sys._MEIPASS)
    projectRoot = os.path.dirname(os.path.abspath(sys.executable))
else:
    projectRoot = os.path.dirname(os.path.abspath(__file__))
    resourceRoot = projectRoot

distDir = os.path.join(resourceRoot, "src", "frontend", "dist")

iconPath = ""
if sys.platform == "win32":
    iconPath = os.path.join(resourceRoot, "icon", "512.ico")
elif sys.platform == "darwin":
    iconPath = os.path.join(resourceRoot, "icon", "512.icns")
else:
    iconPath = os.path.join(resourceRoot, "icon", "512.png")

def startWindow(dev=False):
    if dev:
        pathToApp = "http://localhost:5173"
    else:
        pathToApp = os.path.join(distDir, "index.html")
        if not os.path.exists(pathToApp):
            raise FileNotFoundError(
                "Frontend build output was not found. Run `python run.py test` or `python run.py compile` first."
            )

    window = wv.create_window(
        title="Protux",
        url=str(pathToApp),
        js_api=API(),
        width=1280,
        height=720,
    )

    def forceShutdown():
        # pywebview should normally exit when the last window closes.
        # If GTK/webview leaves the process alive, terminate the host process.
        threading.Thread(target=lambda: os._exit(0), daemon=True).start()

    window.events.closed += forceShutdown

    wv.start(
        http_server=True,
        private_mode=False,
        debug=not getattr(sys, "frozen", False),
        icon=iconPath,
    )

if __name__ == "__main__":
    startWindow(False)
