"""CheckMK agent-based check plugin for MikroTik psu monitoring."""


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


def parse_mikrotik_psu(string_table: StringTable) -> dict[str, dict[str, str]]:
    """Parse MikroTik PSU status information from agent output.

    Handles both switch (state only) and router (voltage/current) formats,
    though voltage/current metrics are processed in the power plugin.
    """
    data = {}

    for line in string_table:
        if not line or len(line) < 2:  # noqa: PLR2004
            continue

        # Focus only on state information (voltage/current handled in power plugin)
        if "state" in line[0]:
            psu_name = line[0].split("-")[0]
            data[psu_name] = {
                "state": line[1],
                "raw_line": " ".join(line),
            }

    return data

def discover_mikrotik_psu(section: dict[str, dict[str, str]]) -> DiscoveryResult:
    """Discover all power supply units."""
    for psu_name in section:
        yield Service(item=psu_name)

def check_mikrotik_psu(
    item: str,
    params: dict[str, Any],
    section: dict[str, dict[str, str]],
) -> CheckResult:
    """Check power supply unit status."""
    if item not in section:
        yield Result(state=State.UNKNOWN, summary="PSU not found in monitoring data")
        return

    psu_data = section[item]
    ok_states = params.get("ok_states", ["ok"])

    if psu_data["state"] in ok_states:
        yield Result(
            state=State.OK,
            summary=f"Status: {psu_data['state'].upper()}",
        )
    else:
        yield Result(
            state=State.CRIT,
            summary=f"Problem: {psu_data['raw_line']}",
            details="PSU status indicates a problem",
        )

# Register agent section
agent_section_mikrotik_psu = AgentSection(
    name="mikrotik_psu",
    parse_function=parse_mikrotik_psu,
)

# Register check plugin
check_plugin_mikrotik_psu = CheckPlugin(
    name="mikrotik_psu",
    service_name="PSU %s",
    discovery_function=discover_mikrotik_psu,
    check_function=check_mikrotik_psu,
    check_default_parameters={
        "ok_states": ["ok"],
    },
    check_ruleset_name="mikrotik_psu",
)
