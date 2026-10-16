#!/usr/bin/env python3
"""Build the MikroTik CheckMK extension package (MKP).

Run from the repository root:

    python3 build_mkp.py

Produces mikrotik-<VERSION>.mkp in the current directory.

The MKP format is a gzipped tar containing:
  info         – legacy Python-repr metadata (still read by some CMK versions)
  info.json    – JSON metadata (primary, required by CMK 2.3+)
  cmk_addons_plugins.tar – inner tar with all plugin files under mikrotik/
  web.tar      – inner tar for legacy WATO files (empty in this release)
"""

import io
import json
import os
import stat
import tarfile
import time

PACKAGE_NAME = "mikrotik"
VERSION = "4.2.0"
OUTPUT = f"{PACKAGE_NAME}-{VERSION}.mkp"

# (source path relative to repo root, archive path inside cmk_addons_plugins.tar)
ADDON_FILES: list[tuple[str, str]] = [
    # agent-based check plugins
    ("agent_based/mikrotik_bgp.py",      "mikrotik/agent_based/mikrotik_bgp.py"),
    ("agent_based/mikrotik_board.py",    "mikrotik/agent_based/mikrotik_board.py"),
    ("agent_based/mikrotik_fan.py",      "mikrotik/agent_based/mikrotik_fan.py"),
    ("agent_based/mikrotik_file.py",     "mikrotik/agent_based/mikrotik_file.py"),
    ("agent_based/mikrotik_firewall.py", "mikrotik/agent_based/mikrotik_firewall.py"),
    ("agent_based/mikrotik_ipsec.py",    "mikrotik/agent_based/mikrotik_ipsec.py"),
    ("agent_based/mikrotik_license.py",  "mikrotik/agent_based/mikrotik_license.py"),
    ("agent_based/mikrotik_ospf.py",     "mikrotik/agent_based/mikrotik_ospf.py"),
    ("agent_based/mikrotik_poe.py",       "mikrotik/agent_based/mikrotik_poe.py"),
    ("agent_based/mikrotik_power.py",    "mikrotik/agent_based/mikrotik_power.py"),
    ("agent_based/mikrotik_psu.py",      "mikrotik/agent_based/mikrotik_psu.py"),
    ("agent_based/mikrotik_vrrp.py",     "mikrotik/agent_based/mikrotik_vrrp.py"),
    ("agent_based/mikrotik_wifi.py",     "mikrotik/agent_based/mikrotik_wifi.py"),
    # check man pages
    ("checkman/mikrotik_bgp",            "mikrotik/checkman/mikrotik_bgp"),
    ("checkman/mikrotik_board",          "mikrotik/checkman/mikrotik_board"),
    ("checkman/mikrotik_fan",            "mikrotik/checkman/mikrotik_fan"),
    ("checkman/mikrotik_file",           "mikrotik/checkman/mikrotik_file"),
    ("checkman/mikrotik_firewall",       "mikrotik/checkman/mikrotik_firewall"),
    ("checkman/mikrotik_ipsec",          "mikrotik/checkman/mikrotik_ipsec"),
    ("checkman/mikrotik_ospf",           "mikrotik/checkman/mikrotik_ospf"),
    ("checkman/mikrotik_power",          "mikrotik/checkman/mikrotik_power"),
    ("checkman/mikrotik_psu",            "mikrotik/checkman/mikrotik_psu"),
    ("checkman/mikrotik_vrrp",           "mikrotik/checkman/mikrotik_vrrp"),
    ("checkman/mikrotik_wifi",           "mikrotik/checkman/mikrotik_wifi"),
    # data collection agent (executed on the CheckMK server, must be executable)
    ("libexec/agent_mikrotik",           "mikrotik/libexec/agent_mikrotik"),
    # rule spec definitions — replaces legacy wato/ files, requires CMK 2.5+
    ("rulesets/mikrotik_agent.py",       "mikrotik/rulesets/mikrotik_agent.py"),
    ("rulesets/mikrotik_checks.py",      "mikrotik/rulesets/mikrotik_checks.py"),
    # server-side call definition (builds agent command line with proper Secret handling)
    ("server_side_calls/mikrotik.py",    "mikrotik/server_side_calls/mikrotik.py"),
    # documentation
    ("CHANGELOG.MD",                     "mikrotik/CHANGELOG.MD"),
    ("README.MD",                        "mikrotik/README.MD"),
]

# CheckMK version this release was built and tested on. Shown on the Exchange
# as "Built on Checkmk version" - update it with every release.
CMK_PACKAGED = "2.5.0p14"

# Version description shown on the Checkmk Exchange. The Exchange shows it as
# plain text: line breaks collapse, Markdown is not rendered and ` ' " are
# shown as HTML entities (&#96; ...), _ is shown as \_, < > are rejected as
# HTML. So the text is generated as plain sentences from CHANGELOG.MD.
SUMMARY = (
    "MikroTik RouterOS monitoring: BGP, OSPF, VRRP; fan, PSU, temperature and "
    "per-PSU power; RouterOS Info and HW/SW inventory (model, serial number, "
    "RouterOS version, RouterBOOT firmware); CHR license expiry; IPsec and "
    "firewall filter rules; WiFi clients, signal and radios per SSID, also via CAPsMAN; file age and crashfile handling. "
    "Requires CheckMK 2.4.0 or later. Full changelog: CHANGELOG.MD in the "
    "source repository."
)

_FORBIDDEN = set("<>`'\"*#[]_")


def _changelog_section(version: str) -> tuple[str, list[str]]:
    """Return heading and body lines of the CHANGELOG.MD section of *version*.

    Fails the build if the section is missing, so the version description on
    the Exchange can never drift from the changelog again.
    """
    lines = open("CHANGELOG.MD", encoding="utf-8").read().splitlines()
    heading = f"## [{version}]"
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith(heading))
    except StopIteration:
        raise SystemExit(f"ERROR: no '{heading}' section in CHANGELOG.MD")
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## [")),
        len(lines),
    )
    return lines[start], lines[start + 1:end]


def _plain(text: str) -> str:
    """Drop Markdown emphasis/code marks and quotes."""
    for ch in "`*\"'":
        text = text.replace(ch, "")
    return " ".join(text.split())


def _version_description(version: str) -> str:
    """'Changes in 4.1.0 (2026-10-13): Added: a; b. Changed: c.' as one line."""
    heading, body = _changelog_section(version)
    date = heading.split("] - ", 1)[1].strip() if "] - " in heading else ""
    groups: list[tuple[str, list[str]]] = []
    for line in body:
        if line.startswith("### "):
            groups.append((line[4:].strip(), []))
        elif line.lstrip().startswith("- ") and groups:
            groups[-1][1].append(line.lstrip()[2:])
        elif line.strip() and groups and groups[-1][1]:
            groups[-1][1][-1] += " " + line.strip()  # bullet continuation
    parts = [
        f"{title}: " + "; ".join(_plain(b).rstrip(".") for b in bullets) + "."
        for title, bullets in groups if bullets
    ]
    head = f"Changes in {version}" + (f" ({date})" if date else "") + ":"
    return " ".join([head, *parts])


DESCRIPTION = SUMMARY + " " + _version_description(VERSION)
if bad := _FORBIDDEN & set(DESCRIPTION):
    raise SystemExit(f"ERROR: description contains {sorted(bad)}, the Exchange mangles or rejects them")

INFO: dict = {
    "title": "Mikrotik",
    "name": PACKAGE_NAME,
    "description": DESCRIPTION,
    "version": VERSION,
    "version.packaged": CMK_PACKAGED,
    "version.min_required": "2.4.0",
    "version.usable_until": None,  # no upper limit
    "author": "Tony Boston (tboston@csitlab.org)",
    "download_url": "https://github.com/TonyBostonTB/CMK_Mikrotik",
    "files": {
        "cmk_addons_plugins": [arc for _, arc in ADDON_FILES],
    },
}

# Permissions for the agent script: rwxr-xr-x
_EXEC_MODE = (
    stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
)


def _add_file(tar: tarfile.TarFile, src: str, arc: str) -> None:
    ti = tar.gettarinfo(src, arcname=arc)
    if "libexec" in arc:
        ti.mode = _EXEC_MODE
    with open(src, "rb") as fh:
        tar.addfile(ti, fh)


def _build_inner_tar(files: list[tuple[str, str]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:") as t:
        for src, arc in files:
            if not os.path.exists(src):
                print(f"  WARNING: {src} not found, skipping")
                continue
            _add_file(t, src, arc)
            print(f"  + {arc}")
    return buf.getvalue()


def _bytes_entry(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    ti = tarfile.TarInfo(name=name)
    ti.size = len(data)
    ti.mtime = int(time.time())
    tar.addfile(ti, io.BytesIO(data))


def main() -> None:
    print(f"Building {OUTPUT} ...")

    addon_bytes = _build_inner_tar(ADDON_FILES)

    # Empty web.tar — no legacy WATO files in this release
    web_buf = io.BytesIO()
    with tarfile.open(fileobj=web_buf, mode="w:"):
        pass

    info_json = json.dumps(INFO, indent=2, ensure_ascii=False).encode()
    info_legacy = repr(INFO).encode()

    with tarfile.open(OUTPUT, "w:gz") as outer:
        _bytes_entry(outer, "info", info_legacy)
        _bytes_entry(outer, "info.json", info_json)
        _bytes_entry(outer, "cmk_addons_plugins.tar", addon_bytes)
        _bytes_entry(outer, "web.tar", web_buf.getvalue())

    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"\nDone: {OUTPUT} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
