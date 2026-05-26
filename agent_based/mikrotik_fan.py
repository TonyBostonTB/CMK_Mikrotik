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


def parse_mikrotik_fan(string_table: StringTable) -> dict[str, dict]:
    """Parse MikroTik fan information from agent output."""
    data: dict[str, dict] = {}

    for line in string_table:
        if not line or len(line) < 2:  # noqa: PLR2004
            continue

        if "speed" in line[0]:
            fan_name = line[0].split("-")[0]
            try:
                data[fan_name] = {"speed": int(line[1])}
            except ValueError:
                continue
        elif line[0] == "fan-state":
            data["Status"] = {"state": line[1]}

    return data


def discover_mikrotik_fan(section: dict[str, dict]) -> DiscoveryResult:
    """Discover active fans and overall fan status."""
    for fan_name, fan_data in section.items():
        if "speed" in fan_data and fan_data["speed"] > 0:
            yield Service(item=fan_name)
        elif "state" in fan_data:
            yield Service(item=fan_name)


def check_mikrotik_fan(
    item: str,
    params: dict,
    section: dict[str, dict],
) -> CheckResult:
    """Check fan speed or overall fan status."""
    if item not in section:
        yield Result(state=State.UNKNOWN, summary="Fan not found in monitoring data")
        return

    fan_data = section[item]

    # Overall fan state (fan-state field)
    if "state" in fan_data:
        state_val = fan_data["state"]
        if state_val == "ok":
            yield Result(state=State.OK, summary=f"Status: {state_val.upper()}")
        else:
            yield Result(state=State.CRIT, summary=f"Status: {state_val.upper()}")
        return

    # Per-fan speed check
    fan_speed = fan_data.get("speed")
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
