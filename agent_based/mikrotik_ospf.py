"""CheckMK agent-based check plugin for MikroTik ospf monitoring."""


from dataclasses import dataclass
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
)


# Neighbor states that are not (yet) established; Down is CRIT,
# anything not listed here and not in ok_states is UNKNOWN.
WARN_STATES = {"Attempt", "Init", "ExStart", "Exchange", "Loading"}


@dataclass
class Adjacency:
    address: str = ""
    interface: str = ""
    instance: str = ""
    state: str = ""


Section = dict[str, list[Adjacency]]  # router-id -> adjacencies


def parse_mikrotik_ospf(string_table: StringTable) -> Section:
    """Parse MikroTik OSPF neighbor information from agent output.

    Every "router-id" line starts a new adjacency. The same router-id
    appears once per interface and, on RouterOS 7, once per OSPF version,
    so all of its adjacencies are kept. "interface" and "instance" are
    only sent by agent 4.2.1 and newer.
    """
    data: Section = {}
    current = None

    for line in string_table:
        if not line:
            continue

        key, value = line[0], " ".join(line[1:])

        if key == "router-id":
            current = Adjacency()
            data.setdefault(value, []).append(current)
            continue

        if current is None:
            continue

        if key in ("address", "interface", "instance", "state"):
            setattr(current, key, value)

    # drop adjacencies the agent sent without a state
    return {
        router_id: [adj for adj in adjacencies if adj.state]
        for router_id, adjacencies in data.items()
        if any(adj.state for adj in adjacencies)
    }

def discover_mikrotik_ospf(section: Section) -> DiscoveryResult:
    """Discover all OSPF neighbors."""
    for neighbor in section:
        yield Service(item=neighbor)

def _describe(adj: Adjacency) -> str:
    where = ", ".join(part for part in (adj.interface, adj.instance) if part)
    name = adj.address or "unknown address"
    return f"{name} ({where})" if where else name

def check_mikrotik_ospf(
    item: str,
    params: dict[str, Any],
    section: Section,
) -> CheckResult:
    """Check the state of every adjacency with an OSPF neighbor."""
    if item not in section:
        yield Result(state=State.CRIT, summary="OSPF neighbor not found")
        return

    adjacencies = section[item]
    ok_states = set(params.get("ok_states", ["Full", "TwoWay", "2-Way"]))

    yield Result(
        state=State.OK,
        summary=f"{len(adjacencies)} adjacenc{'y' if len(adjacencies) == 1 else 'ies'}",
    )

    for adj in adjacencies:
        text = f"{_describe(adj)}: {adj.state}"
        if adj.state in ok_states:
            yield Result(state=State.OK, notice=text)
        elif adj.state == "Down":
            yield Result(state=State.CRIT, summary=text)
        elif adj.state in WARN_STATES:
            yield Result(state=State.WARN, summary=text)
        else:
            yield Result(state=State.UNKNOWN, summary=f"{text} (unknown state)")

# Register agent section
agent_section_mikrotik_ospf = AgentSection(
    name="mikrotik_ospf",
    parse_function=parse_mikrotik_ospf,
)

# Register check plugin
check_plugin_mikrotik_ospf = CheckPlugin(
    name="mikrotik_ospf",
    service_name="OSPF Neighbor %s",
    discovery_function=discover_mikrotik_ospf,
    check_function=check_mikrotik_ospf,
    check_default_parameters={
        "ok_states": ["Full", "TwoWay", "2-Way"],
    },
    check_ruleset_name="mikrotik_ospf",
)
