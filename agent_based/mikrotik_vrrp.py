"""CheckMK agent-based check plugin for MikroTik vrrp monitoring."""


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


def parse_mikrotik_vrrp(string_table: StringTable) -> dict[str, dict[str, str]]:
    """Parse MikroTik VRRP information from agent output."""
    data = {}
    current_session = None

    for line in string_table:
        if not line:
            continue

        if line[0] == "name":
            current_session = line[1]
            data[current_session] = {}

        if current_session is not None:
            data[current_session][line[0]] = " ".join(line[1:])

    return data

def discover_mikrotik_vrrp(section: dict[str, dict[str, str]]) -> DiscoveryResult:
    """Discover active VRRP instances (not disabled)."""
    for session, session_data in section.items():
        if session_data.get("disabled", "").lower() == "false":
            yield Service(item=session)

def check_mikrotik_vrrp(
    item: str,
    params: dict[str, Any],  # noqa: ARG001
    section: dict[str, dict[str, str]],
) -> CheckResult:
    """Check VRRP instance status."""
    if item not in section:
        yield Result(state=State.UNKNOWN, summary="VRRP instance not found")
        return

    data = section[item]

    # Check if disabled
    if data.get("disabled", "").lower() != "false":
        yield Result(
            state=State.WARN,
            summary=f"VRRP instance is disabled ({data['disabled']})",
        )
        return

    iface = data.get("interface", "unknown interface")
    vrid = data.get("vrid", "unknown")
    mac = data.get("mac-address", "unknown")

    # Determine state based on running/master/backup status
    if data.get("running", "").lower() == "true":
        if data.get("master", "").lower() == "true":
            yield Result(
                state=State.OK,
                summary=f"Master on {iface}",
                details=f"VRID: {vrid}, MAC: {mac}",
            )
        else:
            yield Result(
                state=State.CRIT,
                summary=f"Running on {iface} but not master",
                details=f"VRID: {vrid} (expected master)",
            )
    elif data.get("backup", "").lower() == "true":
        yield Result(
            state=State.OK,
            summary=f"Backup on {iface}",
            details=f"VRID: {vrid}, MAC: {mac}",
        )
    else:
        yield Result(
            state=State.CRIT,
            summary=f"Not running on {iface} and not backup",
            details=f"VRID: {vrid} (inconsistent state)",
        )

# Register agent section
agent_section_mikrotik_vrrp = AgentSection(
    name="mikrotik_vrrp",
    parse_function=parse_mikrotik_vrrp,
)

# Register check plugin
check_plugin_mikrotik_vrrp = CheckPlugin(
    name="mikrotik_vrrp",
    service_name="VRRP %s",
    discovery_function=discover_mikrotik_vrrp,
    check_function=check_mikrotik_vrrp,
    check_default_parameters={},
    check_ruleset_name="mikrotik_vrrp",
)
