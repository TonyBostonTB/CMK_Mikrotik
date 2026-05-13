"""CheckMK agent-based check plugin for MikroTik board monitoring."""


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
from packaging import version  # Sostituisce distutils.version che è deprecato


def parse_mikrotik_board(string_table: StringTable) -> dict[str, str]:
    """Parse MikroTik board information from agent output."""
    relevant_keys = {"board-name", "version"}
    return {
        line[0]: " ".join(line[1:])
        for line in string_table
        if line and line[0] in relevant_keys
    }

def discover_mikrotik_board(section: dict[str, str]) -> DiscoveryResult:
    """Discover service if version information is present."""
    if section.get("version"):
        yield Service()

def check_mikrotik_board(
    params: dict,
    section: dict[str, str],
) -> CheckResult:
    """Check MikroTik board information and version compliance."""
    if not section:
        yield Result(state=State.UNKNOWN, summary="No board information found")
        return

    # Check version compliance if required
    min_version = params.get("min_version", "0.0")
    current_state = State.OK
    summary_parts = []

    if "board-name" in section:
        summary_parts.append(f"Model: {section['board-name']}")

    if "version" in section:
        current_version = section["version"].split(" ")[0]
        summary_parts.append(f"Version: {section['version']}")

        if min_version != "0.0":
            try:
                if version.parse(current_version) < version.parse(min_version):
                    current_state = State.WARN
                    summary_parts.append(
                        f"(below minimum required: {min_version})",
                    )
            except version.InvalidVersion:
                summary_parts.append("(version parsing failed)")
                current_state = State.WARN

    yield Result(
        state=current_state,
        summary=", ".join(summary_parts),
    )

# Register agent section
agent_section_mikrotik_board = AgentSection(
    name="mikrotik_board",
    parse_function=parse_mikrotik_board,
)

# Register check plugin
check_plugin_mikrotik_board = CheckPlugin(
    name="mikrotik_board",
    service_name="RouterOS Info",
    discovery_function=discover_mikrotik_board,
    check_function=check_mikrotik_board,
    check_default_parameters={"min_version": "0.0"},
    check_ruleset_name="mikrotik_board",
)
