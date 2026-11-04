"""CheckMK agent-based check plugin for a UPS connected to a MikroTik router.

Agent module "ups" (/system/ups, needs the RouterOS package ups.npk),
pipe separated:
    ups|<name>|<field>|<value>    configuration (model, serial, version, ...)
    mon|<name>|<field>|<value>    "/system/ups/monitor once" of this UPS

One service per UPS that is not disabled ("UPS <name>"): power source,
battery low / replace battery / overload flags, battery charge, runtime
left, load and temperature with levels; voltages and frequency as metrics.
Without monitor data (UPS not connected or not supported) the service
goes CRIT by default.

Contributed by Klaus Paulitsch <kp@workitout.at>.

SPDX-License-Identifier: GPL-3.0-only
"""

import re
from dataclasses import dataclass, field
from typing import Any

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    InventoryPlugin,
    InventoryResult,
    Result,
    Service,
    State,
    StringTable,
    TableRow,
    check_levels,
    render,
)


@dataclass
class Ups:
    config: dict[str, str] = field(default_factory=dict)
    monitor: dict[str, str] = field(default_factory=dict)


Section = dict[str, Ups]


def parse_mikrotik_ups(string_table: StringTable) -> Section | None:
    """Parse ups/mon lines; None if the module delivered nothing."""
    section: Section = {}
    for line in string_table:
        if len(line) < 4 or line[0] not in ("ups", "mon") or not line[1]:
            continue
        ups = section.setdefault(line[1], Ups())
        target = ups.config if line[0] == "ups" else ups.monitor
        target[line[2]] = "|".join(line[3:])
    return section or None


def _num(value: str | None) -> float | None:
    """'100' / '100%' / '27V' / '27.3 V' / '50Hz' -> float."""
    match = re.match(r"\s*(-?\d+(?:\.\d+)?)", value or "")
    return float(match.group(1)) if match else None


def _flag(value: str | None) -> bool:
    return (value or "").lower() in ("true", "yes")


_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}


def runtime_seconds(value: str | None) -> float | None:
    """'20m' / '1h5m30s' / '00:20:00' / '1d02:00:00' -> seconds."""
    text = (value or "").strip()
    if not text:
        return None
    seconds = 0.0
    clock = re.search(r"(\d+):(\d{2}):(\d{2})$", text)
    if clock:
        hours, minutes, secs = (int(x) for x in clock.groups())
        seconds += hours * 3600 + minutes * 60 + secs
        text = text[: clock.start()]
    parts = re.findall(r"(\d+)(ms|[wdhms])", text)
    if not parts and not clock:
        return None
    seconds += sum(int(n) * _UNITS[u] for n, u in parts if u != "ms")
    return seconds


def discover_mikrotik_ups(section: Section) -> DiscoveryResult:
    """One service per UPS that is not disabled."""
    for name, ups in section.items():
        if not _flag(ups.config.get("disabled")):
            yield Service(item=name)


def check_mikrotik_ups(item: str, params: dict[str, Any], section: Section) -> CheckResult:
    """Check power source, battery and load of a UPS."""
    if (ups := section.get(item)) is None:
        return
    mon = ups.monitor
    if not mon:
        yield Result(
            state=State(params.get("no_data_state", 2)),
            summary="No monitoring data from the UPS (not connected or not supported)",
        )
        return

    if _flag(mon.get("on-battery")) or ("on-line" in mon and not _flag(mon.get("on-line"))):
        cause = mon.get("transfer-cause")
        yield Result(
            state=State(params.get("on_battery_state", 2)),
            summary="On battery" + (f" ({cause})" if cause else ""),
        )
    else:
        yield Result(state=State.OK, summary="On line power")

    for keys, label, param, default in (
        (("low-battery",), "Battery low", "low_battery_state", 2),
        (("replace-battery",), "Replace battery", "replace_battery_state", 1),
        (("overload", "overloaded-output"), "Output overloaded", "overload_state", 1),
    ):
        if any(_flag(mon.get(key)) for key in keys):
            yield Result(state=State(params.get(param, default)), summary=label)

    if (charge := _num(mon.get("battery-charge"))) is not None:
        yield from check_levels(
            charge,
            levels_lower=params.get("battery_charge_lower"),
            metric_name="battery_capacity",
            render_func=render.percent,
            label="Battery charge",
            boundaries=(0, 100),
        )
    if (runtime := runtime_seconds(mon.get("runtime-left"))) is not None:
        yield from check_levels(
            runtime,
            levels_lower=params.get("runtime_lower"),
            metric_name="battery_seconds_remaining",
            render_func=render.timespan,
            label="Runtime left",
        )
    if (load := _num(mon.get("load"))) is not None:
        yield from check_levels(
            load,
            levels_upper=params.get("load_upper"),
            metric_name="output_load",
            render_func=render.percent,
            label="Load",
            boundaries=(0, 100),
        )
    if (temp := _num(mon.get("temperature"))) is not None:
        yield from check_levels(
            temp,
            levels_upper=params.get("temperature_upper"),
            metric_name="temp",
            render_func=lambda v: f"{v:.1f} °C",
            label="Temperature",
        )
    for key, metric, label in (
        ("line-voltage", "mikrotik_ups_input_voltage", "Input voltage"),
        ("output-voltage", "mikrotik_ups_output_voltage", "Output voltage"),
        ("battery-voltage", "mikrotik_ups_battery_voltage", "Battery voltage"),
    ):
        if (volt := _num(mon.get(key))) is not None:
            yield from check_levels(
                volt,
                metric_name=metric,
                render_func=lambda v: f"{v:.1f} V",
                label=label,
                notice_only=True,
            )
    if (freq := _num(mon.get("frequency"))) is not None:
        yield from check_levels(
            freq,
            metric_name="frequency",
            render_func=lambda v: f"{v:.1f} Hz",
            label="Frequency",
            notice_only=True,
        )
    details = [
        f"{label}: {ups.config[key]}"
        for key, label in (("model", "Model"), ("serial", "Serial"), ("version", "Version"))
        if ups.config.get(key)
    ]
    if details:
        yield Result(state=State.OK, notice=", ".join(details))


def inventory_mikrotik_ups(section: Section) -> InventoryResult:
    """UPS as hardware component (model, serial, firmware)."""
    for name, ups in section.items():
        yield TableRow(
            path=["hardware", "components", "psus"],
            key_columns={"index": name},
            inventory_columns={
                "name": name,
                "description": "UPS",
                "model": ups.config.get("model", ""),
                "serial": ups.config.get("serial", ""),
                "software": ups.config.get("version", ""),
            },
        )


# Register agent section
agent_section_mikrotik_ups = AgentSection(
    name="mikrotik_ups",
    parse_function=parse_mikrotik_ups,
)

# Register check plugin
check_plugin_mikrotik_ups = CheckPlugin(
    name="mikrotik_ups",
    service_name="UPS %s",
    discovery_function=discover_mikrotik_ups,
    check_function=check_mikrotik_ups,
    check_default_parameters={
        "on_battery_state": 2,
        "low_battery_state": 2,
        "replace_battery_state": 1,
        "overload_state": 1,
        "no_data_state": 2,
        "battery_charge_lower": ("fixed", (50.0, 25.0)),
        "runtime_lower": ("fixed", (600.0, 300.0)),
        "load_upper": ("fixed", (80.0, 90.0)),
    },
    check_ruleset_name="mikrotik_ups",
)

# Register inventory plugin
inventory_plugin_mikrotik_ups = InventoryPlugin(
    name="mikrotik_ups",
    inventory_function=inventory_mikrotik_ups,
)
