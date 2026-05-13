"""CheckMK agent-based check plugin for MikroTik ospf monitoring."""


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


def parse_mikrotik_ospf(string_table: StringTable) -> dict[str, dict[str, str]]:
    """Parse MikroTik OSPF neighbor information from agent output."""
    data = {}
    current_neighbor = None

    for line in string_table:
        if not line:
            continue

        if line[0] == "router-id":
            # New neighbor found
            current_neighbor = line[1]
            data[current_neighbor] = {}
            continue

        if current_neighbor is None:
            continue

        if line[0] == "address":
            # Store address but wait for state
            current_address = line[1]
            continue

        if line[0] == "state":
            # Add state information for the current address
            if "current_address" in locals():
                data[current_neighbor][current_address] = " ".join(line[1:])
            else:
                # Handle RouterOS v7 format without separate address lines
                data[current_neighbor]["state"] = " ".join(line[1:])

    return data

def discover_mikrotik_ospf(section: dict[str, dict[str, str]]) -> DiscoveryResult:
    """Discover all OSPF neighbors."""
    for neighbor in section:
        yield Service(item=neighbor)

def check_mikrotik_ospf(
    item: str,
    params: dict[str, Any],
    section: dict[str, dict[str, str]],
) -> CheckResult:
    """Check OSPF neighbor state."""
    if item not in section:
        yield Result(state=State.CRIT, summary="OSPF neighbor not found")
        return

    neighbor_data = section[item]
    ok_states = set(params.get("ok_states", ["Full", "TwoWay", "2-Way"]))

    # Handle different data structures for RouterOS v6 and v7
    if "state" in neighbor_data:
        # RouterOS v7 format
        state = neighbor_data["state"]
        if state in ok_states:
            yield Result(state=State.OK, summary=f"State: {state}")
        elif state == "Down":
            yield Result(state=State.CRIT, summary=f"State: {state} (!!)")
        else:
            yield Result(state=State.WARN, summary=f"State: {state} (!)")
    else:
        # RouterOS v6 format with multiple addresses
        worst_state = State.OK
        state_details = []

        for address, state in neighbor_data.items():
            if state in ok_states:
                state_details.append(f"{address}: {state}")
            elif state == "Down":
                state_details.append(f"{address}: {state} (!!)")
                worst_state = max(worst_state, State.CRIT)
            else:
                state_details.append(f"{address}: {state} (!)")
                worst_state = max(worst_state, State.WARN)

        yield Result(
            state=worst_state,
            summary=f"States: {len(neighbor_data)} interfaces",
            details="\n".join(state_details),
        )

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
