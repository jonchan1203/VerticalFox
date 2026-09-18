#!/usr/bin/env python3
"""Marionette chrome-context probe for debugging Firefox userChrome themes.

Start Firefox with remote debugging first (system access is required for
chrome-context scripting):

    firefox.exe -no-remote -profile <profile-dir> -marionette -remote-allow-system-access

Then run subcommands against the running instance (default port 2828):

    python probe.py static                 sidebar / nav-bar geometry + computed styles
    python probe.py point X Y [X Y ...]    elementFromPoint ancestor chains (chrome doc)
    python probe.py pseudo SELECTOR        ::before / ::after / self backgrounds
    python probe.py urlbar                 walk the urlbar light DOM showing backgrounds
    python probe.py panel                  check #sidebar-panel-header in the webext-panels doc
    python probe.py js "<script>"          run arbitrary chrome JS (must end with: return JSON.stringify(...))

Notes (Firefox 157, protocol 3):
  - wire format: length-prefixed JSON  "<len>:<payload>"
  - command:  [0, id, name, params]   response: [1, id, error, result]
  - "Marionette:SetContext" {"value": "chrome"} switches to privileged scope
  - scripts must `return` their value explicitly
"""

import json
import socket
import sys

HOST, PORT = "127.0.0.1", 2828


class Marionette:
    """Minimal Marionette protocol-3 client (chrome context)."""

    def __init__(self, host=HOST, port=PORT, timeout=60):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.f = self.s.makefile("rwb")
        self.hello = self._read()
        self.i = 0
        self.cmd("WebDriver:NewSession", {"capabilities": {}})
        self.cmd("Marionette:SetContext", {"value": "chrome"})

    def _read(self):
        buf = b""
        while not buf.endswith(b":"):
            c = self.f.read(1)
            if not c:
                raise EOFError("marionette connection closed")
            buf += c
        return json.loads(self.f.read(int(buf[:-1])))

    def cmd(self, name, params=None):
        self.i += 1
        msg = json.dumps([0, self.i, name, params or {}]).encode()
        self.f.write(str(len(msg)).encode() + b":" + msg)
        self.f.flush()
        while True:
            r = self._read()
            if isinstance(r, list) and len(r) >= 4 and r[0] == 1 and r[1] == self.i:
                if r[2]:
                    raise RuntimeError(f"{name} error: {json.dumps(r[2])[:300]}")
                return r[3]

    def script(self, body) -> dict:
        r = self.cmd("WebDriver:ExecuteScript", {"script": body, "args": []})
        return json.loads(r["value"]) if r.get("value") else {}


# ---------------------------------------------------------------- fragments

STATIC_SCRIPT = r"""
const doc = window.document;
function info(id) {
  const el = doc.getElementById(id);
  if (!el) return { exists: false };
  const cs = doc.defaultView.getComputedStyle(el);
  const r = el.getBoundingClientRect();
  return { exists: true, display: cs.display, visibility: cs.visibility,
           overflow: cs.overflow, x: Math.round(r.x), y: Math.round(r.y),
           w: Math.round(r.width), h: Math.round(r.height) };
}
return JSON.stringify({
  chromeWin: window.location.href,
  url: window.gBrowser?.selectedBrowser?.currentURI?.spec,
  dpr: window.devicePixelRatio,
  verticalTabsPref: (() => { try { return String(Services.prefs.getBoolPref("sidebar.verticalTabs", false)); } catch (e) { return "err"; } })(),
  visibilityPref: (() => { try { return Services.prefs.getStringPref("sidebar.visibility", "<unset>"); } catch (e) { return "err"; } })(),
  sidebarContainer: info("sidebar-container"),
  launcherSplitter: info("sidebar-launcher-splitter"),
  sidebarBox: info("sidebar-box"),
  sidebarHeader: info("sidebar-header"),
  sidebarBrowser: info("sidebar"),
  tabsToolbar: info("TabsToolbar"),
  navBar: info("nav-bar"),
  appContent: info("tabbrowser-tabbox"),
  verticalTabsBox: info("vertical-tabs"),
  panelUi: info("PanelUI-button"),
  titlebarBtnNav: (() => { const el = doc.querySelector("#nav-bar .titlebar-buttonbox-container");
      if (!el) return { exists: false };
      const cs = doc.defaultView.getComputedStyle(el); const r = el.getBoundingClientRect();
      return { exists: true, display: cs.display, visibility: cs.visibility, position: cs.position,
               x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; })(),
});
"""

POINT_SCRIPT = r"""
const doc = window.document;
const pts = JSON.parse("%PTS%");
function chainAt(x, y) {
  const el = doc.elementFromPoint(x, y);
  if (!el) return null;
  const parts = [];
  let n = el;
  for (let i = 0; i < 6 && n; i++) {
    parts.push(n.tagName + (n.id ? "#" + n.id : "") +
      (n.className && typeof n.className === "string"
        ? "." + n.className.split(" ").filter(Boolean).slice(0, 3).join(".") : ""));
    n = n.parentElement;
  }
  const cs = doc.defaultView.getComputedStyle(el);
  const r = el.getBoundingClientRect();
  return { at: x + "," + y, chain: parts, bg: cs.backgroundColor,
           img: cs.backgroundImage.substring(0, 80),
           rect: Math.round(r.x) + "," + Math.round(r.y) + " " + Math.round(r.width) + "x" + Math.round(r.height) };
}
return JSON.stringify(pts.map(p => chainAt(p[0], p[1])));
"""

PSEUDO_SCRIPT = r"""
const doc = window.document;
const sel = "%SEL%";
const el = doc.querySelector(sel);
if (!el) { return JSON.stringify({ sel: sel, error: "not found" }); }
const out = { sel: sel };
for (const p of ["::before", "::after"]) {
  const cs = doc.defaultView.getComputedStyle(el, p);
  out[p] = { content: cs.content, img: cs.backgroundImage.substring(0, 100), bg: cs.backgroundColor };
}
const cs = doc.defaultView.getComputedStyle(el);
out.self = { bg: cs.backgroundColor, img: cs.backgroundImage.substring(0, 100) };
return JSON.stringify(out);
"""

URLBAR_SCRIPT = r"""
const doc = window.document;
const ub = doc.getElementById("urlbar");
const out = { tag: ub.tagName, kids: [] };
const walk = (el, depth) => {
  if (depth > 4) return;
  const cs = doc.defaultView.getComputedStyle(el);
  out.kids.push("  ".repeat(depth) + el.tagName + (el.id ? "#" + el.id : "") +
    (el.className && typeof el.className === "string"
      ? "." + el.className.split(" ").filter(Boolean).slice(0, 2).join(".") : "")
    + " | img=" + cs.backgroundImage.substring(0, 60) + " | bg=" + cs.backgroundColor);
  for (const c of el.children) walk(c, depth + 1);
};
walk(ub, 0);
return JSON.stringify(out);
"""

PANEL_SCRIPT = r"""
const doc = window.document;
const sb = doc.getElementById("sidebar");
let panelHeader = "n/a";
try {
  const pd = sb.contentDocument;
  if (pd) {
    const h = pd.getElementById("sidebar-panel-header");
    if (h) {
      const cs = pd.defaultView.getComputedStyle(h);
      const r = h.getBoundingClientRect();
      panelHeader = { display: cs.display, rect: Math.round(r.width) + "x" + Math.round(r.height) };
    } else panelHeader = "not-in-panel-doc";
  }
} catch (e) { panelHeader = "err:" + e.message; }
return JSON.stringify({ panelHeader: panelHeader });
"""


def _fmt(script, mapping):
    for k, v in mapping.items():
        script = script.replace(k, v)
    return script


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, rest = argv[1], argv[2:]
    m = Marionette()
    if cmd == "static":
        out = m.script(STATIC_SCRIPT)
    elif cmd == "point":
        pts = [[int(rest[i]), int(rest[i + 1])] for i in range(0, len(rest) - 1, 2)]
        out = m.script(_fmt(POINT_SCRIPT, {"%PTS%": json.dumps(pts)}))
    elif cmd == "pseudo":
        out = m.script(_fmt(PSEUDO_SCRIPT, {"%SEL%": rest[0]}))
    elif cmd == "urlbar":
        out = m.script(URLBAR_SCRIPT)
    elif cmd == "panel":
        out = m.script(PANEL_SCRIPT)
    elif cmd == "js":
        out = m.script(rest[0])
    else:
        print(__doc__)
        return 2
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
