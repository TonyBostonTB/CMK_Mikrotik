"""CheckMK check plugins for MikroTik system resources.

CPU utilization, memory, system disk, uptime and NAND bad blocks, all from
one /system/resource request of the opt-in agent module "system" (RouterOS
6 and 7). The agent prints three key value sections:

    mikrotik_system         cpu-load, cpu-count, cpu, cpu-frequency,
                            free-hdd-space, total-hdd-space, bad-blocks,
                            write-sect-since-reboot, write-sect-total
    mikrotik_system_mem     total-memory, free-memory
    mikrotik_system_uptime  uptime
The checks use the standard Checkmk libraries and rule sets, so they look
and behave like the CPU, memory, filesystem and uptime services of any other
host:

    CPU utilization       -> CPU utilization for simple devices
    Memory (used)         -> Checkmk's own mem_used check: Memory levels
    Filesystem system disk -> File systems (used space and growth)
    Uptime                -> Checkmk's own uptime check: Uptime since last reboot

Memory and uptime use the parsed sections of Checkmk's own checks
(mem_used, uptime), so service names, rules and output are the same as via
SNMP. The sections supersede the matching SNMP sections (hr_fs, hr_mem,
snmp_uptime), so a host that is polled via SNMP as well gets every service
once; the parse functions return None without data, so SNMP stays in
charge then.

CPU is the exception: the module's CPU service is only discovered if the
host has no SNMP CPU data (section hr_cpu). cpu-load of /system/resource is
a short-term value and, on a host polled via SNMP, lands in the load of the
SNMP query that Checkmk runs at the same time (about 20 % instead of 2 % on
a hEX), while hrProcessorLoad is a one-minute average (RFC 2790). So hosts
with SNMP keep the SNMP CPU service, hosts without SNMP get the module's.

Note: cpu_util, df and uptime come from cmk.plugins.lib, Checkmk's own
shared code and not one of the versioned plug-in APIs. They have to be
rechecked with every Checkmk major release.

Contributed by Klaus Paulitsch <kp@workitout.at>.

SPDX-License-Identifier: GPL-3.0-only
"""

import re
import time
from collections.abc import Mapping
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
    get_value_store,
)
from cmk.plugins.lib import uptime
from cmk.plugins.lib.cpu_util import check_cpu_util
from cmk.plugins.lib.df import FILESYSTEM_DEFAULT_PARAMS, df_check_filesystem_single

Section = Mapping[str, str]


def parse_mikrotik_system(string_table: StringTable) -> Section | None:
    """Key value lines; values may contain spaces. None without data."""
    section = {line[0]: " ".join(line[1:]) for line in string_table if len(line) >= 2}
    return section or None


# CPU and system disk (and NAND bad blocks); supersedes the SNMP filesystem
# section of the host resources MIB. Not hr_cpu: see the CPU check.
agent_section_mikrotik_system = AgentSection(
    name="mikrotik_system",
    parse_function=parse_mikrotik_system,
    supersedes=["hr_fs"],
)

SYSTEM_DISK = "system disk"


def _percent(value: str | None) -> float | None:
    """'0.1' / '0.1%' -> 0.1 (RouterOS reports bad blocks in percent)."""
    match = re.match(r"\s*(\d+(?:\.\d+)?)", str(value or ""))
    return float(match.group(1)) if match else None


def _number(section: Section, key: str) -> float | None:
    """/system/resource values are plain numbers (bytes, percent, MHz)."""
    try:
        return float(section[key])
    except (KeyError, ValueError):
        return None


# ---------------------------------------------------------------------------
# CPU utilization
# ---------------------------------------------------------------------------


def discover_mikrotik_cpu(
    section_mikrotik_system: Section | None,
    section_hr_cpu: object | None,
) -> DiscoveryResult:
    """Only on hosts without SNMP CPU data, see the module docstring."""
    if section_hr_cpu is not None or section_mikrotik_system is None:
        return
    if _number(section_mikrotik_system, "cpu-load") is not None:
        yield Service()


def check_mikrotik_cpu(
    params: Mapping[str, Any],
    section_mikrotik_system: Section | None,
    section_hr_cpu: object | None,
) -> CheckResult:
    """CPU utilization from cpu-load; hr_cpu is only used for the discovery."""
    if (section := section_mikrotik_system) is None:
        return
    if (util := _number(section, "cpu-load")) is None:
        return
    yield from check_cpu_util(
        util=util,
        params=params,
        this_time=time.time(),
        value_store=get_value_store(),
    )
    cores = section.get("cpu-count")
    if section.get("cpu") or cores:
        yield Result(
            state=State.OK,
            notice=f"CPU: {section.get('cpu', 'unknown')}"
            + (f", {cores} cores" if cores else "")
            + (f", {section['cpu-frequency']} MHz" if section.get("cpu-frequency") else ""),
        )


check_plugin_mikrotik_cpu = CheckPlugin(
    name="mikrotik_cpu",
    # hr_cpu only to leave the CPU to SNMP when the host has it
    sections=["mikrotik_system", "hr_cpu"],
    service_name="CPU utilization",
    discovery_function=discover_mikrotik_cpu,
    check_function=check_mikrotik_cpu,
    check_ruleset_name="cpu_utilization_os",
    check_default_parameters={"util": (80.0, 90.0)},  # same as hr_cpu via SNMP
)


# ---------------------------------------------------------------------------
# Memory -> Checkmk's own mem_used check
# ---------------------------------------------------------------------------
# Same parsed section as SNMP hr_mem ("mem_used"), so the service, its rule
# (Memory levels) and its output are identical to SNMP, and the section
# supersedes hr_mem: a host polled via SNMP too never gets it twice.


def parse_mikrotik_system_mem(string_table: StringTable) -> dict[str, int] | None:
    values = {line[0]: line[1] for line in string_table if len(line) >= 2}
    try:
        total = int(values["total-memory"])
        free = int(values["free-memory"])
    except (KeyError, ValueError):
        return None
    if total <= 0:
        return None
    return {"MemTotal": total, "MemFree": free, "Cached": 0}


agent_section_mikrotik_system_mem = AgentSection(
    name="mikrotik_system_mem",
    parsed_section_name="mem_used",
    parse_function=parse_mikrotik_system_mem,
    supersedes=["hr_mem"],
)


# ---------------------------------------------------------------------------
# Filesystem system disk
# ---------------------------------------------------------------------------


def discover_mikrotik_fs(section: Section) -> DiscoveryResult:
    if _number(section, "total-hdd-space") and _number(section, "free-hdd-space") is not None:
        yield Service(item=SYSTEM_DISK)


def check_mikrotik_fs(
    item: str, params: Mapping[str, Any], section: Section
) -> CheckResult:
    if item != SYSTEM_DISK:
        return
    total = _number(section, "total-hdd-space")
    free = _number(section, "free-hdd-space")
    if total is None or free is None:
        return
    mib = 1024.0 * 1024.0
    yield from df_check_filesystem_single(
        value_store=get_value_store(),
        mountpoint=item,
        filesystem_size=total / mib,
        free_space=free / mib,
        reserved_space=0.0,
        inodes_total=None,
        inodes_avail=None,
        params=params,
        this_time=time.time(),
    )
    # bad blocks have their own service with configurable levels
    # (NAND bad blocks), here only for information
    if (bad := _percent(section.get("bad-blocks"))) is not None:
        yield Result(state=State.OK, notice=f"Bad blocks: {bad:.1f}% (service NAND bad blocks)")


check_plugin_mikrotik_fs = CheckPlugin(
    name="mikrotik_fs",
    sections=["mikrotik_system"],
    service_name="Filesystem %s",
    discovery_function=discover_mikrotik_fs,
    check_function=check_mikrotik_fs,
    check_ruleset_name="filesystem",
    check_default_parameters=FILESYSTEM_DEFAULT_PARAMS,
)


# ---------------------------------------------------------------------------
# Uptime
# ---------------------------------------------------------------------------

_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def parse_routeros_uptime(text: str) -> float | None:
    """'2w3d4h5m6s' (API) or '2w3d04:05:06' (CLI style) -> seconds."""
    text = text.strip()
    if not text:
        return None
    seconds = 0.0
    clock = re.search(r"(\d+):(\d{2}):(\d{2})$", text)
    if clock:
        h, m, s = (int(x) for x in clock.groups())
        seconds += h * 3600 + m * 60 + s
        text = text[: clock.start()]
    parts = re.findall(r"(\d+)([wdhms])", text)
    if not parts and not clock:
        return None
    seconds += sum(int(n) * _UNITS[u] for n, u in parts)
    return seconds


def parse_mikrotik_system_uptime(string_table: StringTable) -> uptime.Section | None:
    for line in string_table:
        if len(line) >= 2 and line[0] == "uptime":
            seconds = parse_routeros_uptime(" ".join(line[1:]))
            if seconds is not None:
                return uptime.Section(uptime_sec=seconds, message=None)
    return None


# Same parsed section as SNMP ("uptime"): Checkmk's own uptime check, rule
# and output; supersedes snmp_uptime.
agent_section_mikrotik_system_uptime = AgentSection(
    name="mikrotik_system_uptime",
    parsed_section_name="uptime",
    parse_function=parse_mikrotik_system_uptime,
    supersedes=["snmp_uptime"],
)


# ---------------------------------------------------------------------------
# NAND bad blocks
# ---------------------------------------------------------------------------
# RouterOS reports "bad-blocks" in percent of the NAND flash. A small share
# of bad blocks is normal for NAND (often already from the factory) and is
# handled by the flash management; it only matters if it grows.


def discover_mikrotik_bad_blocks(section: Section) -> DiscoveryResult:
    if _percent(section.get("bad-blocks")) is not None:
        yield Service()


def check_mikrotik_bad_blocks(
    params: Mapping[str, Any], section: Section
) -> CheckResult:
    if (bad := _percent(section.get("bad-blocks"))) is None:
        return
    yield from check_levels(
        bad,
        levels_upper=params.get("levels"),
        metric_name="mikrotik_bad_blocks",
        render_func=lambda v: f"{v:.1f}%",
        label="Bad blocks",
        boundaries=(0, 100),
    )
    for key, label in (
        ("write-sect-since-reboot", "Sectors written since reboot"),
        ("write-sect-total", "Sectors written in total"),
    ):
        if section.get(key):
            yield Result(state=State.OK, notice=f"{label}: {section[key]}")


check_plugin_mikrotik_bad_blocks = CheckPlugin(
    name="mikrotik_bad_blocks",
    sections=["mikrotik_system"],
    service_name="NAND bad blocks",
    discovery_function=discover_mikrotik_bad_blocks,
    check_function=check_mikrotik_bad_blocks,
    check_ruleset_name="mikrotik_bad_blocks",
    check_default_parameters={"levels": ("fixed", (2.0, 5.0))},
)
