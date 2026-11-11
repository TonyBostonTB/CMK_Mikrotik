"""CheckMK check plugins for MikroTik MLAG (multi-chassis link aggregation).

Agent module "mlag" (RouterOS 7, CRS3xx/CRS5xx), pipe separated:
    bridge|<name>|<field>|<value>      bridge with an MLAG peer port
    bridgemon|<name>|<field>|<value>   "/interface/bridge/monitor once":
                                       mlag-state, mlag-active-role, ...
    bond|<name>|<field>|<value>        bonding with an mlag-id
    bondmon|<name>|<field>|<value>     "/interface/bonding/monitor once":
                                       active-ports, inactive-ports,
                                       lacp-partner-system-id, ...

Services:
- "MLAG <bridge>": state of the connection to the MLAG peer (ICCP) and the
  role of this node (primary/secondary, optionally an expected role).
- "MLAG bond <bond>": active/inactive member ports and LACP partner of a
  dual-connected bond.

Field names follow the MikroTik MLAG documentation (RouterOS 7).

Contributed by Klaus Paulitsch <kp@workitout.at>.

SPDX-License-Identifier: GPL-3.0-only
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    Result,
    Service,
    State,
    StringTable,
)


@dataclass
class Section:
    bridges: dict[str, dict[str, Any]] = field(default_factory=dict)
    bonds: dict[str, dict[str, Any]] = field(default_factory=dict)


_KINDS = {
    "bridge": ("bridges", False),
    "bridgemon": ("bridges", True),
    "bond": ("bonds", False),
    "bondmon": ("bonds", True),
}


def parse_mikrotik_mlag(string_table: StringTable) -> Section | None:
    """Parse bridge/bond lines; None if the module delivered nothing."""
    section = Section()
    for line in string_table:
        if len(line) < 4 or line[0] not in _KINDS or not line[1]:
            continue
        group, is_monitor = _KINDS[line[0]]
        row = getattr(section, group).setdefault(line[1], {"name": line[1], "monitor": {}})
        target = row["monitor"] if is_monitor else row
        target[line[2]] = "|".join(line[3:])
    return section if (section.bridges or section.bonds) else None


def _ports(value: Any) -> list[str]:
    """'sfp1,sfp2' / ['sfp1', 'sfp2'] / '' -> list of port names."""
    if isinstance(value, list):
        return [str(p) for p in value if p]
    return [p.strip() for p in str(value or "").split(",") if p.strip()]


# ---------------------------------------------------------------------------
# MLAG peer status per bridge
# ---------------------------------------------------------------------------


def discover_mikrotik_mlag(section: Section) -> DiscoveryResult:
    for name in section.bridges:
        yield Service(item=name)


def check_mikrotik_mlag(
    item: str, params: Mapping[str, Any], section: Section
) -> CheckResult:
    if (row := section.bridges.get(item)) is None:
        return
    mon = row.get("monitor") or {}
    mlag_state = str(mon.get("mlag-state") or "").strip()

    if mlag_state == "connected":
        yield Result(state=State.OK, summary="Peer connected")
    elif mlag_state == "connecting":
        yield Result(
            state=State(params.get("connecting_state", 2)),
            summary="Connecting to peer (peer link down or peer not reachable)",
        )
    elif not mlag_state:
        yield Result(
            state=State(params.get("error_state", 2)),
            summary="No MLAG state reported",
        )
    else:
        yield Result(
            state=State(params.get("error_state", 2)),
            summary=f"MLAG state: {mlag_state}",
        )

    role = str(mon.get("mlag-active-role") or "").strip()
    expected = params.get("expected_role", "any")
    if role:
        if expected in ("primary", "secondary") and role != expected:
            yield Result(
                state=State(params.get("role_mismatch_state", 1)),
                summary=f"Role: {role} (expected {expected})",
            )
        else:
            yield Result(state=State.OK, summary=f"Role: {role}")

    details = [
        f"{label}: {row[key]}"
        for key, label in (
            ("mlag-peer-port", "Peer port"),
            ("mlag-priority", "Priority"),
            ("mlag-heartbeat", "Heartbeat"),
        )
        if row.get(key)
    ] + [
        f"{label}: {mon[key]}"
        for key, label in (("state", "Bridge state"), ("bridge-id", "Bridge ID"))
        if mon.get(key)
    ]
    if details:
        yield Result(state=State.OK, notice="\n".join(details))


agent_section_mikrotik_mlag = AgentSection(
    name="mikrotik_mlag",
    parse_function=parse_mikrotik_mlag,
)

check_plugin_mikrotik_mlag = CheckPlugin(
    name="mikrotik_mlag",
    service_name="MLAG %s",
    discovery_function=discover_mikrotik_mlag,
    check_function=check_mikrotik_mlag,
    check_ruleset_name="mikrotik_mlag",
    check_default_parameters={
        "connecting_state": 2,
        "error_state": 2,
        "expected_role": "any",
        "role_mismatch_state": 1,
    },
)


# ---------------------------------------------------------------------------
# MLAG bonds
# ---------------------------------------------------------------------------


def discover_mikrotik_mlag_bond(section: Section) -> DiscoveryResult:
    for name in section.bonds:
        yield Service(item=name)


def check_mikrotik_mlag_bond(
    item: str, params: Mapping[str, Any], section: Section
) -> CheckResult:
    if (row := section.bonds.get(item)) is None:
        return
    mon = row.get("monitor") or {}
    active = _ports(mon.get("active-ports"))
    inactive = _ports(mon.get("inactive-ports"))
    running = str(row.get("running", "true")).lower() in ("true", "yes")

    if not running or not active:
        yield Result(
            state=State(params.get("no_active_state", 2)),
            summary="No active member port" + ("" if running else " (bond not running)"),
        )
    else:
        yield Result(state=State.OK, summary=f"Active: {', '.join(active)}")

    if inactive:
        yield Result(
            state=State(params.get("inactive_state", 1)),
            summary=f"Inactive: {', '.join(inactive)}",
        )

    partner = str(mon.get("lacp-partner-system-id") or "").strip()
    if partner and partner not in ("00:00:00:00:00:00", "none"):
        yield Result(state=State.OK, notice=f"LACP partner: {partner}")
    elif str(mon.get("mode") or row.get("mode") or "802.3ad") == "802.3ad":
        yield Result(
            state=State(params.get("no_partner_state", 1)),
            summary="No LACP partner",
        )

    yield Metric("mikrotik_mlag_bond_active", len(active))
    details = [
        f"{label}: {row[key]}"
        for key, label in (("mlag-id", "MLAG ID"), ("slaves", "Member ports"), ("mode", "Mode"))
        if row.get(key)
    ]
    if mon.get("lacp-system-id"):
        details.append(f"LACP system ID: {mon['lacp-system-id']}")
    if details:
        yield Result(state=State.OK, notice="\n".join(details))


check_plugin_mikrotik_mlag_bond = CheckPlugin(
    name="mikrotik_mlag_bond",
    sections=["mikrotik_mlag"],
    service_name="MLAG bond %s",
    discovery_function=discover_mikrotik_mlag_bond,
    check_function=check_mikrotik_mlag_bond,
    check_ruleset_name="mikrotik_mlag_bond",
    check_default_parameters={
        "no_active_state": 2,
        "inactive_state": 1,
        "no_partner_state": 1,
    },
)
