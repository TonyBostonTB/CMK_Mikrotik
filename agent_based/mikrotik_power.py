"""CheckMK agent-based check plugin for MikroTik power monitoring."""


import contextlib
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
)

# mA readings from RouterOS v7 are > 100; below this values are already in A.
_MA_TO_A_THRESHOLD = 100


def _parse_psu_line(line: list[str]) -> tuple[str, str, float] | None:
    """Return (psu_name, metric_type, value) for a PSU line, or None if unparseable."""
    metric = line[0]
    # Normalize bare current/voltage (single-PSU devices without psuN prefix)
    if metric in {"current", "voltage"}:
        metric = f"psu0-{metric}"
    if "psu" not in metric:
        return None
    try:
        psu_id, metric_type = metric.split("-", 1)
        value = float(line[1])
        # Convert mA back to A (v7 agent multiplies A→mA for current readings)
        if metric_type == "current" and value > _MA_TO_A_THRESHOLD:
            value /= 1000
        return psu_id.upper(), metric_type, value
    except (ValueError, IndexError):
        return None


def parse_mikrotik_power(string_table: StringTable) -> dict[str, Any]:
    """Parse MikroTik power supply information from agent output."""
    psus: dict[str, dict[str, float]] = {}
    total_power = 0.0

    for line in string_table:
        if not line:
            continue

        # Capture RouterOS's pre-calculated total power consumption (Watts)
        if line[0] == "power-consumption":
            with contextlib.suppress(ValueError, IndexError):
                total_power = float(line[1])
            continue

        parsed = _parse_psu_line(line)
        if parsed is None:
            continue

        psu_name, metric_type, value = parsed
        if psu_name not in psus:
            psus[psu_name] = {}
        psus[psu_name][metric_type] = value

    # Calculate per-PSU watts
    for psu_data in psus.values():
        psu_data["power"] = psu_data.get("current", 0.0) * psu_data.get("voltage", 0.0)

    # Use RouterOS total if provided, otherwise sum per-PSU calculated watts
    if not total_power:
        total_power = sum(p["power"] for p in psus.values())

    return {"psus": psus, "total_power": total_power}


def discover_mikrotik_power(section: dict[str, Any]) -> DiscoveryResult:
    """Discover one service per power supply unit."""
    for psu_name in section["psus"]:
        yield Service(item=psu_name)


def check_mikrotik_power(
    item: str,
    params: dict[str, Any],
    section: dict[str, Any],
) -> CheckResult:
    """Check voltage, current, and calculated wattage for one PSU."""
    if item not in section.get("psus", {}):
        yield Result(state=State.UNKNOWN, summary="PSU not found in monitoring data")
        return

    psu_data = section["psus"][item]
    crit_voltage = params.get("crit_voltage", 10)

    voltage = psu_data.get("voltage")
    current = psu_data.get("current")
    power = psu_data.get("power", 0.0)

    if voltage is not None:
        if voltage < crit_voltage:
            yield Result(
                state=State.CRIT,
                summary=f"Voltage: {voltage:.2f}V (below {crit_voltage}V threshold)",
            )
        else:
            yield Result(state=State.OK, summary=f"Voltage: {voltage:.2f}V")
        yield Metric(name="voltage", value=voltage)

    if current is not None:
        yield Result(state=State.OK, notice=f"Current: {current:.3f}A")
        yield Metric(name="current", value=current)

    if power > 0:
        yield Result(state=State.OK, summary=f"Power: {power:.2f}W")
        yield Metric(name="power", value=power)


# Register agent section
agent_section_mikrotik_power = AgentSection(
    name="mikrotik_power",
    parse_function=parse_mikrotik_power,
)

# Register check plugin
check_plugin_mikrotik_power = CheckPlugin(
    name="mikrotik_power",
    service_name="Power %s",
    discovery_function=discover_mikrotik_power,
    check_function=check_mikrotik_power,
    check_default_parameters={"crit_voltage": 10},
    check_ruleset_name="mikrotik_power",
)
