"""CheckMK agent-based check plugin for MikroTik ipsec monitoring."""


import time
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
    get_rate,
    get_value_store,
    render,
)


def parse_mikrotik_ipsec(string_table: StringTable) -> dict[str, dict[str, Any]]:
    """Parse MikroTik IPsec information from agent output."""
    data = {}

    for line in string_table:
        if not line:
            continue

        if line[0] == "peer":
            # New peer found
            peer_name = line[1]
            my_addr = line[2]
            peer_addr = line[3]

            data[peer_addr] = {
                "myaddr": my_addr,
                "peer": peer_name,
                "sa_states": set(),
                "sacount": 0,
                "if_in_bps": 0,
                "if_out_bps": 0,
            }
            continue

        if line[0] == "sa":
            # Security Association data
            if line[1] in data:
                # Outbound traffic
                data[line[1]]["if_out_bps"] += int(line[4])
                data[line[1]]["sacount"] += 1
                data[line[1]]["sa_states"].add(line[3])
            elif line[2] in data:
                # Inbound traffic
                data[line[2]]["if_in_bps"] += int(line[4])
                data[line[2]]["sacount"] += 1
                data[line[2]]["sa_states"].add(line[3])
            continue

        if line[0] == "invip":
            # Standby gateway information
            for peer_data in data.values():
                if peer_data["myaddr"] == line[1]:
                    peer_data["interface"] = line[2]
                    break

    return data

def discover_mikrotik_ipsec(section: dict[str, dict[str, Any]]) -> DiscoveryResult:
    """Discover all IPsec peers."""
    for peer_data in section.values():
        yield Service(item=peer_data["peer"])

def check_mikrotik_ipsec(
    item: str,
    params: dict[str, Any],
    section: dict[str, dict[str, Any]],
) -> CheckResult:
    """Check IPsec tunnel status and traffic."""
    # Find the peer data
    peer_data = None
    for data in section.values():
        if data["peer"] == item:
            peer_data = data
            break

    if not peer_data:
        yield Result(state=State.UNKNOWN, summary="IPsec peer not found")
        return

    value_store = get_value_store()
    now = time.time()
    results = []
    metrics = []

    # Calculate traffic rates
    bytes_i_rate = get_rate(
        value_store,
        f"mikrotik_ipsec.{item}.bytes_i",
        now,
        peer_data["if_in_bps"],
    )
    bytes_o_rate = get_rate(
        value_store,
        f"mikrotik_ipsec.{item}.bytes_o",
        now,
        peer_data["if_out_bps"],
    )

    metrics.extend([
        Metric("if_in_bps", bytes_i_rate * 8),
        Metric("if_out_bps", bytes_o_rate * 8),
    ])

    # Check SA status
    if peer_data["sacount"] > 0:
        # Active tunnel
        peer_addr = next(addr for addr in section if section[addr]["peer"] == item)
        results.append(Result(
            state=State.OK,
            summary=f"Active: {peer_data['myaddr']} ↔ {peer_addr}",
            details=f"Security Associations: {peer_data['sacount']}",
        ))

        # Check SA states
        ok = set(params.get("ok_states", ["dying", "mature"]))
        bad_states = peer_data["sa_states"] - ok
        if bad_states:
            results.append(Result(
                state=State.CRIT,
                summary=f"Bad SA states: {', '.join(bad_states)}",
            ))

        # Add traffic info
        results.append(Result(
            state=State.OK,
            notice=(
                f"In: {render.networkbandwidth(bytes_i_rate)}, "
                f"Out: {render.networkbandwidth(bytes_o_rate)}"
            ),
        ))
    elif "interface" in peer_data:
        # Standby tunnel
        results.append(Result(
            state=State.OK,
            summary=f"Standby on {peer_data['interface']}",
            details=f"{peer_data['myaddr']} not active",
        ))
    else:
        # Tunnel down
        results.append(Result(
            state=State.CRIT,
            summary="Not established",
        ))

    # Yield all results and metrics
    yield from results
    yield from metrics

# Register agent section
agent_section_mikrotik_ipsec = AgentSection(
    name="mikrotik_ipsec",
    parse_function=parse_mikrotik_ipsec,
)

# Register check plugin
check_plugin_mikrotik_ipsec = CheckPlugin(
    name="mikrotik_ipsec",
    service_name="IPsec %s",
    discovery_function=discover_mikrotik_ipsec,
    check_function=check_mikrotik_ipsec,
    check_default_parameters={
        "ok_states": ["dying", "mature"],
    },
    check_ruleset_name="mikrotik_ipsec",
)
