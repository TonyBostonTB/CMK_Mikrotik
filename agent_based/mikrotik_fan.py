"""CheckMK agent-based check plugin for MikroTik fan monitoring."""


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


def parse_mikrotik_fan(string_table: StringTable) -> dict[str, dict[str, int]]:
    """Parse MikroTik fan information from agent output."""
    data = {}

    for line in string_table:
        if not line or "speed" not in line[0]:
            continue

        fan_name = line[0].split("-")[0]
        try:
            data[fan_name] = {"speed": int(line[1])}
        except (IndexError, ValueError):
            continue

    return data

def discover_mikrotik_fan(section: dict[str, dict[str, int]]) -> DiscoveryResult:
    """Discover active fans (speed > 0)."""
    for fan_name, fan_data in section.items():
        if fan_data.get("speed", 0) > 0:
            yield Service(item=fan_name)

def check_mikrotik_fan(
    item: str,
    params: dict,
    section: dict[str, dict[str, int]],
) -> CheckResult:
    """Check fan speed against configured thresholds."""
    if item not in section:
        yield Result(state=State.UNKNOWN, summary="Fan not found in monitoring data")
        return

    fan_speed = section[item].get("speed")
    if fan_speed is None:
        yield Result(state=State.UNKNOWN, summary="No speed data available")
        return

    # SimpleLevels format: ("fixed", (warn, crit)) or ("no_levels", None)
    # Legacy format stored by old WATO rules: (warn, crit)
    lower_raw = params.get("lower", ("fixed", (2000, 1000)))
    if isinstance(lower_raw, tuple) and len(lower_raw) == 2 and isinstance(lower_raw[0], str):
        if lower_raw[0] == "no_levels":
            warn, crit = None, None
        else:
            warn, crit = lower_raw[1]
    else:
        warn, crit = lower_raw

    if crit is not None and fan_speed < crit:
        state = State.CRIT
        summary = f"Speed: {fan_speed} RPM (below critical threshold {crit})"
    elif warn is not None and fan_speed < warn:
        state = State.WARN
        summary = f"Speed: {fan_speed} RPM (below warning threshold {warn})"
    else:
        state = State.OK
        summary = f"Speed: {fan_speed} RPM"

    yield Result(state=state, summary=summary)
    yield Metric(name="fan_speed", value=fan_speed, boundaries=(0, None))

# Register agent section
agent_section_mikrotik_fan = AgentSection(
    name="mikrotik_fan",
    parse_function=parse_mikrotik_fan,
)

# Register check plugin
check_plugin_mikrotik_fan = CheckPlugin(
    name="mikrotik_fan",
    service_name="FAN %s",
    discovery_function=discover_mikrotik_fan,
    check_function=check_mikrotik_fan,
    check_default_parameters={
        "lower": ("fixed", (2000, 1000)),
    },
    check_ruleset_name="mikrotik_fan",
)
