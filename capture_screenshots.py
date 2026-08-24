import sys
import os
import time
import ctypes
from ctypes import wintypes

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

# Find duAI window by title
EnumWindows = ctypes.windll.user32.EnumWindows
GetWindowTextW = ctypes.windll.user32.GetWindowTextW
GetWindowTextLengthW = ctypes.windll.user32.GetWindowTextLengthW
IsWindowVisible = ctypes.windll.user32.IsWindowVisible
GetWindowRect = ctypes.windll.user32.GetWindowRect
PrintWindow = ctypes.windll.user32.PrintWindow

def find_duAI_window():
    result = []
    def callback(hwnd, _):
        if IsWindowVisible(hwnd):
            length = GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if "duAI" in title:
                    result.append(hwnd)
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    EnumWindows(WNDENUMPROC(callback), 0)
    return result[0] if result else None

def capture_window(hwnd, filename):
    rect = wintypes.RECT()
    GetWindowRect(hwnd, ctypes.byref(rect))
    x, y = rect.left, rect.top
    w = rect.right - rect.left
    h = rect.bottom - rect.top

    if w <= 0 or h <= 0:
        print(f"  Ventana no valida: {w}x{h}")
        return False

    screen = QApplication.primaryScreen()
    pixmap = screen.grabWindow(hwnd, x, y, w, h)
    pixmap.save(filename, "PNG")
    size_kb = os.path.getsize(filename) / 1024
    print(f"  Guardado: {filename} ({size_kb:.0f} KB, {w}x{h})")
    return True

def main():
    hwnd = find_duAI_window()
    if not hwnd:
        print("No se encontro la ventana de duAI")
        sys.exit(1)

    print(f"Ventana encontrada: HWND={hwnd}")

    out_dir = os.path.join(os.path.dirname(__file__), "website", "assets", "screenshots")
    os.makedirs(out_dir, exist_ok=True)

    tab_names = [
        "dashboard",
        "scan",
        "clean",
        "panic",
        "session",
        "settings",
        "terminal",
    ]

    app = QApplication.instance() or QApplication(sys.argv)

    for i, name in enumerate(tab_names):
        print(f"Capturando tab {i}: {name}...")
        # Signal the running duAI app to switch tabs via command file
        # We'll use a temp file approach
        cmd_file = os.path.join(os.environ.get("LOCALAPPDATA", ""), "duAI", "screenshot_cmd.txt")
        with open(cmd_file, "w") as f:
            f.write(str(i))

        time.sleep(1.5)

        filename = os.path.join(out_dir, f"{name}.png")
        capture_window(hwnd, filename)

    print(f"\nScreenshots guardados en: {out_dir}")

if __name__ == "__main__":
    main()
