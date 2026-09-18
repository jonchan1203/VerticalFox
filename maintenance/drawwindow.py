#!/usr/bin/env python3
"""Capture the browser window using Firefox's own compositor (drawWindow).

OS-level screenshots (GDI CopyFromScreen) are unreliable for chrome-UI
geometry on scaled displays (DPI virtualisation, DWM frame artifacts).
ctx.drawWindow() renders what Firefox actually paints, which makes it the
ground truth for theme debugging.

Start Firefox with `-marionette -remote-allow-system-access` first, then:

    python drawwindow.py [--out result.png] [--width 1536] [--height 974]
"""

import argparse
import base64
import sys

from probe import Marionette


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="drawwindow.png")
    ap.add_argument("--width", type=int, default=1536)
    ap.add_argument("--height", type=int, default=974)
    args = ap.parse_args()

    m = Marionette()
    r = m.cmd("WebDriver:ExecuteScript", {"script": f"""
const win = window;
const doc = win.document;
const canvas = doc.createElementNS('http://www.w3.org/1999/xhtml', 'canvas');
canvas.width = {args.width}; canvas.height = {args.height};
const ctx = canvas.getContext('2d');
ctx.drawWindow(win, 0, 0, {args.width}, {args.height}, '#ff00ff');
return canvas.toDataURL('image/png');
""", "args": []})

    data = r["value"]
    if "," in data:
        data = data.split(",", 1)[1]
    png = base64.b64decode(data)
    with open(args.out, "wb") as fh:
        fh.write(png)
    print("saved", len(png), "bytes ->", args.out)


if __name__ == "__main__":
    sys.exit(main())
