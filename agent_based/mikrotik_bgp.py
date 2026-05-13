"""CheckMK agent-based check plugin for MikroTik bgp monitoring."""


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


def parse_mikrotik_bgp(string_table: StringTable) -> dict[str, dict[str, str]]:
    """Parse MikroTik BGP session data from agent output.

    Handles both v6 (hyphen-separated) and v7 (dot-separated) key formats.
    """
    data = {}
    current_session = None

    for line in string_table:
        if not line:  # skip empty lines
            continue

        if line[0] == "name":
            current_session = line[1]
            data[current_session] = {}
            continue

        if current_session is None:
            continue

        # Normalize keys (v6 '-' vs v7 '.')
        key = line[0].replace("-", ".")
        value = " ".join(line[1:])
        data[current_session][key] = value

    return data

def discover_mikrotik_bgp(section: dict[str, dict[str, str]]) -> DiscoveryResult:
    """Discover all BGP sessions present in the parsed data."""
    for session in section:
        yield Service(item=session)

def check_mikrotik_bgp(
    item: str,
    params: dict,  # noqa: ARG001
    section: dict[str, dict[str, str]],
) -> CheckResult:
    """Check the state of a specific BGP session."""
    if item not in section:
        yield Result(state=State.CRIT, summary="BGP session not found")
        return

    data = section[item]

    # Check if session is established
    bgp_state = data.get("established", "").lower()
    if not bgp_state:
        yield Result(state=State.CRIT, summary="No BGP state information available")
        return

    if bgp_state != "true":
        yield Result(
            state=State.CRIT,
            summary=f"BGP session not established (state: {bgp_state})",
        )
        return

    # Session is established - collect details
    remote_as = data.get("remote.as", "unknown")
    remote_addr = data.get("remote.address", "unknown")

    yield Result(
        state=State.OK,
        summary=f"Established with AS{remote_as} ({remote_addr})",
    )

    # Add metrics if available
    for metric_name in ["updates.received", "updates.sent", "withdrawn.received"]:
        if metric_name in data and data[metric_name].isdigit():
            yield Metric(
                name=f"bgp_{metric_name.replace('.', '_')}",
                value=int(data[metric_name]),
            )

# Register agent section
agent_section_mikrotik_bgp = AgentSection(
    name="mikrotik_bgp",
    parse_function=parse_mikrotik_bgp,
)

# Register check plugin
check_plugin_mikrotik_bgp = CheckPlugin(
    name="mikrotik_bgp",
    service_name="BGP %s",
    discovery_function=discover_mikrotik_bgp,
    check_function=check_mikrotik_bgp,
    check_default_parameters={},
    check_ruleset_name="mikrotik_bgp",
)
