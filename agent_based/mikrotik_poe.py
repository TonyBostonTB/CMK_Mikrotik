"""CheckMK agent-based check plugin for MikroTik PoE output consumption."""


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


def parse_mikrotik_poe(string_table: StringTable) -> dict[str, float]:
    """Parse MikroTik PoE output consumption from agent output."""
    data: dict[str, float] = {}
    for line in string_table:
        if len(line) >= 2 and line[0] == "poe-out-consumption":  # noqa: PLR2004
            try:
                data["consumption"] = float(line[1])
            except ValueError:
                pass
    return data


def discover_mikrotik_poe(section: dict[str, float]) -> DiscoveryResult:
    """Discover PoE consumption service if data is present."""
    if "consumption" in section:
        yield Service()


def check_mikrotik_poe(section: dict[str, float]) -> CheckResult:
    """Report PoE output consumption in watts."""
    if "consumption" not in section:
        yield Result(state=State.UNKNOWN, summary="PoE consumption data not available")
        return

    consumption = section["consumption"]
    yield Result(state=State.OK, summary=f"PoE output: {consumption:.1f}W")
    yield Metric(name="poe_consumption", value=consumption)


# Register agent section
agent_section_mikrotik_poe = AgentSection(
    name="mikrotik_poe",
    parse_function=parse_mikrotik_poe,
)

# Register check plugin
check_plugin_mikrotik_poe = CheckPlugin(
    name="mikrotik_poe",
    service_name="PoE Consumption",
    discovery_function=discover_mikrotik_poe,
    check_function=check_mikrotik_poe,
)
