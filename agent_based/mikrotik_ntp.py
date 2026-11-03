"""CheckMK agent-based check plugin for the MikroTik NTP client.

Agent module "ntp" (RouterOS 7, /system/ntp/client), key value lines:
    enabled true
    mode unicast
    servers ntp.example.com
    status synchronized
    synced-server ntp.example.com
    synced-stratum 2
    system-offset -0.578
    freq-drift 12.003

Service "NTP Time": synchronisation status, absolute time offset and
stratum. The API returns system-offset as a plain number in milliseconds
(the CLI shows it with "ms"); values with a unit are accepted as well.

Contributed by Klaus Paulitsch <kp@workitout.at>.

SPDX-License-Identifier: GPL-3.0-only
"""

import re
from typing import Any

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Result,
    Service,
    State,
    StringTable,
    check_levels,
    render,
)

Section = dict[str, str]

# unit -> factor to seconds; no unit means milliseconds
_OFFSET_UNITS = {"ns": 1e-9, "us": 1e-6, "µs": 1e-6, "ms": 1e-3, "s": 1.0, "": 1e-3}


def parse_mikrotik_ntp(string_table: StringTable) -> Section:
    """Parse key value lines; values may contain spaces."""
    return {line[0]: " ".join(line[1:]) for line in string_table if line}


def offset_seconds(text: str | None) -> float | None:
    """'-0.578' / '-0.104ms' / '123us' / '0.5s' -> seconds."""
    match = re.match(r"\s*([-+]?\d+(?:\.\d+)?)\s*(ns|us|µs|ms|s)?\s*$", text or "")
    if not match:
        return None
    return float(match.group(1)) * _OFFSET_UNITS[match.group(2) or ""]


def _enabled(section: Section) -> bool:
    return section.get("enabled", "").lower() in ("true", "yes")


def discover_mikrotik_ntp(section: Section) -> DiscoveryResult:
    """One service if the NTP client is enabled."""
    if _enabled(section):
        yield Service()


def check_mikrotik_ntp(params: dict[str, Any], section: Section) -> CheckResult:
    """Check synchronisation status, offset and stratum of the NTP client."""
    if not section:
        return
    if not _enabled(section):
        yield Result(
            state=State(params.get("disabled_state", 1)),
            summary="NTP client disabled",
        )
        return

    status = section.get("status", "unknown")
    server = section.get("synced-server")
    if status == "synchronized":
        yield Result(
            state=State.OK,
            summary="Synchronized" + (f" with {server}" if server else ""),
        )
    else:
        yield Result(
            state=State(params.get("not_synced_state", 1)),
            summary=f"Status: {status}",
        )

    offset = offset_seconds(section.get("system-offset"))
    if offset is not None:
        # absolute offset with levels as metric, like the Checkmk timesyncd
        # check: the time_offset graph and Perf-O-Meter start at 0 and draw
        # the WARN/CRIT lines from the metric levels
        yield from check_levels(
            abs(offset),
            levels_upper=params.get("offset_levels"),
            metric_name="time_offset",
            render_func=render.timespan,
            label="Offset" + (" (negative)" if offset < 0 else ""),
        )

    stratum = section.get("synced-stratum", "")
    if stratum.isdigit():
        yield from check_levels(
            int(stratum),
            levels_upper=params.get("stratum_upper"),
            render_func=lambda v: f"{int(v)}",
            label="Stratum",
        )

    drift = section.get("freq-drift", "")
    details = [
        f"{label}: {section[key]}"
        for key, label in (
            ("mode", "Mode"),
            ("servers", "Servers"),
            ("vrf", "VRF"),
        )
        if section.get(key)
    ]
    if drift:
        details.append(
            f"Frequency drift: {drift if 'ppm' in drift.lower() else drift + ' PPM'}"
        )
    if section.get("system-offset"):
        details.append(f"System offset (raw): {section['system-offset']}")
    if details:
        yield Result(state=State.OK, notice="\n".join(details))


# Register agent section
agent_section_mikrotik_ntp = AgentSection(
    name="mikrotik_ntp",
    parse_function=parse_mikrotik_ntp,
)

# Register check plugin
check_plugin_mikrotik_ntp = CheckPlugin(
    name="mikrotik_ntp",
    service_name="NTP Time",
    discovery_function=discover_mikrotik_ntp,
    check_function=check_mikrotik_ntp,
    check_default_parameters={
        "not_synced_state": 1,
        "disabled_state": 1,
        "offset_levels": ("fixed", (0.2, 0.5)),
        "stratum_upper": ("fixed", (10, 15)),
    },
    check_ruleset_name="mikrotik_ntp",
)
