#!/usr/bin/env python3
"""Automated test for the VerticalFox sidebar auto-hide behaviour.

Requires Windows (uses SetCursorPos to simulate hovering).

Steps performed:
  1. launch Firefox with the given profile (with Marionette enabled)
  2. assert collapsed strip (~40 CSS px) with cursor away
  3. hover the left strip  -> assert expanded overlay (>= 200 px) and
     that the page area is NOT pushed aside (overlay behaviour)
  4. move cursor away      -> assert collapsed again

Usage:
    python hovertest.py --profile <path> [--firefox <path>] [--keep-open]
"""

import argparse
import ctypes
import subprocess
import sys
import time
from pathlib import Path

from probe import Marionette, STATIC_SCRIPT

user32 = ctypes.windll.user32


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass  # best effort


def find_firefox_window():
    hwnd = user32.FindWindowW("MozillaWindowClass", None)
    return hwnd if hwnd else None


def window_rect(hwnd):
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
    r = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    dpi = ctypes.windll.user32.GetDpiForWindow(hwnd) if hasattr(
        ctypes.windll.user32, "GetDpiForWindow") else 96
    scale = dpi / 96.0
    return r, scale


def move_mouse(x, y):
    user32.SetCursorPos(int(x), int(y))


def summarize(tag, d):
    sb, box, app = d["sidebarBrowser"], d["sidebarBox"], d["appContent"]
    print(f"[{tag}] sidebar w={sb['w']} x={sb['x']} | box x={box['x']} w={box['w']} | page x={app.get('x')}")


def run_probe() -> dict:
    m = Marionette()
    return m.script(STATIC_SCRIPT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--firefox", default=r"C:\Program Files\Firefox Developer Edition\firefox.exe")
    ap.add_argument("--wait", type=float, default=13, help="seconds to wait for startup")
    ap.add_argument("--keep-open", action="store_true", help="do not close Firefox afterwards")
    args = ap.parse_args()

    set_dpi_aware()

    print("== launching firefox ==")
    subprocess.run(["taskkill", "/IM", "firefox.exe", "/F"], capture_output=True)
    time.sleep(3)
    subprocess.Popen([args.firefox, "-no-remote", "-profile", args.profile,
                      "-marionette", "-remote-allow-system-access"])
    time.sleep(args.wait)

    hwnd = find_firefox_window()
    if not hwnd:
        sys.exit("ERROR: Firefox window not found")
    rect, scale = window_rect(hwnd)
    strip_x = rect.left + 20 * scale          # inside the collapsed 40px strip
    page_x = rect.left + 800 * scale          # well inside the page area
    print(f"window rect: {rect.left},{rect.top} - {rect.right},{rect.bottom} (scale x{scale})")

    move_mouse(page_x, rect.top + 500)
    time.sleep(0.8)
    d0 = run_probe(); summarize("static", d0)

    move_mouse(strip_x, rect.top + 500)
    time.sleep(1.0)
    d1 = run_probe(); summarize("hover", d1)

    move_mouse(page_x, rect.top + 500)
    time.sleep(1.0)
    d2 = run_probe(); summarize("unhover", d2)

    ok = (d0["sidebarBrowser"]["w"] <= 60 and d1["sidebarBrowser"]["w"] >= 200
          and d2["sidebarBrowser"]["w"] <= 60)
    page_stable = d0["appContent"]["x"] == d1["appContent"]["x"] == d2["appContent"]["x"]
    print("AUTO-HIDE+EXPAND:", "PASS" if ok else "FAIL",
          "| PAGE NOT PUSHED:", "PASS" if page_stable else "FAIL")

    if not args.keep_open:
        subprocess.run(["taskkill", "/IM", "firefox.exe"], capture_output=True)


if __name__ == "__main__":
    main()
