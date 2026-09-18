#!/usr/bin/env python3
"""Deploy Sidebery Styles-editor CSS into the profile's LSNG storage.

Since Firefox ~14x, extension `storage.local` no longer lives in
`browser-extension-data/<id>/storage.js` (that directory is dead).
It is stored in an LSNG SQLite database instead:

    <profile>/storage/default/moz-extension+++<addon-uuid>/ls/data.sqlite

Table `data` schema:
    (key TEXT PK, utf16_length INT, conversion_type INT,
     compression_type INT, last_access_time INT, value BLOB)

Existing reference row written by Firefox itself:  ('sdbr', 1, 1, 0, 0, b'+')
For a pure-ASCII string the correct encoding is:
    conversion_type = 1, compression_type = 0, value = ascii bytes,
    utf16_length = character count

Sidebery (v5.x, id {3c078156-979c-498b-8990-85f7987dd929}) stores the
Styles editor content in storage.local key **"sidebarCSS"**.

Usage:
    python deploy_sidebery_css.py [--profile <path>] [--css <file>] [--uuid <uuid>]

Firefox must be CLOSED while running this script.
If the styles do not show up after relaunch, fall back to pasting the CSS
into Sidebery Settings -> Styles editor by hand (always works).
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

SIDEBERY_ID = "{3c078156-979c-498b-8990-85f7987dd929}"
DEFAULT_CSS = Path(__file__).resolve().parent.parent / "sidebery" / "sidebery_styles.css"


def find_uuid(profile: Path) -> str:
    """Read the Sidebery add-on UUID from <profile>/prefs.js."""
    import json
    prefs = profile / "prefs.js"
    text = prefs.read_text(encoding="utf-8", errors="ignore")
    m = re.search(
        r'user_pref\("extensions\.webextensions\.uuids", "(.*)"\);', text
    )
    if not m:
        sys.exit("ERROR: extensions.webextensions.uuids not found in prefs.js")
    try:
        mapping = json.loads(m.group(1).replace('\\"', '"'))
    except json.JSONDecodeError as e:
        sys.exit(f"ERROR: failed to parse uuids pref: {e}")
    uuid = mapping.get(SIDEBERY_ID)
    if not uuid:
        sys.exit(f"ERROR: UUID for {SIDEBERY_ID} not found in uuids pref")
    return uuid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="Firefox profile directory")
    ap.add_argument("--css", default=str(DEFAULT_CSS), help="Sidebery CSS file")
    ap.add_argument("--uuid", default=None, help="Override Sidebery UUID")
    args = ap.parse_args()

    profile = Path(args.profile)
    if not profile.is_dir():
        sys.exit(f"ERROR: profile not found: {profile}")

    css = Path(args.css).read_text(encoding="utf-8")
    if not css.isascii():
        print("WARNING: CSS contains non-ASCII characters; "
              "conversion_type=1 (Latin1) may not be correct. "
              "Consider falling back to manual paste.")

    uuid = args.uuid or find_uuid(profile)
    db = profile / "storage" / "default" / f"moz-extension+++{uuid}" / "ls" / "data.sqlite"
    if not db.is_file():
        sys.exit(f"ERROR: LSNG database not found: {db}\n"
                 "(launch Sidebery once so Firefox creates it)")

    con = sqlite3.connect(str(db))
    cur = con.cursor()
    old = cur.execute("SELECT utf16_length, length(value) FROM data WHERE key=?",
                      ("sidebarCSS",)).fetchone()
    cur.execute(
        "INSERT OR REPLACE INTO data "
        "(key, utf16_length, conversion_type, compression_type, last_access_time, value) "
        "VALUES (?,?,?,?,?,?)",
        ("sidebarCSS", len(css), 1, 0, 0, css.encode("ascii", errors="replace")),
    )
    con.commit()
    rows = cur.execute("SELECT key, utf16_length FROM data").fetchall()
    con.close()

    print(f"uuid        : {uuid}")
    print(f"db          : {db}")
    print(f"previous    : {old}")
    print(f"written     : sidebarCSS = {len(css)} chars")
    print(f"table now   : {rows}")
    print("Done. Start Firefox and verify visually.")


if __name__ == "__main__":
    main()
