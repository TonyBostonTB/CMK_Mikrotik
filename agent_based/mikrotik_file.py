"""CheckMK agent-based check plugin for MikroTik file monitoring."""


import time
from datetime import datetime
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
    render,
)


def parse_mikrotik_file(string_table: StringTable) -> dict[str, dict[str, str]]:
    """Parse MikroTik file information from agent output."""
    data = {}
    current_file = None

    for line in string_table:
        if not line:
            continue

        if line[0] == "name":
            current_file = line[1]
            data[current_file] = {}
            continue

        if current_file is None:
            continue

        data[current_file][line[0]] = " ".join(line[1:])

    # Add watchdog file if not present
    if "autosupout.rif" not in data:
        data["autosupout.rif"] = {
            "type": "file",
            "notfound": "True",
        }

    return data

def discover_mikrotik_file(section: dict[str, dict[str, str]]) -> DiscoveryResult:
    """Discover files to monitor (excluding directories)."""
    for filename, file_data in section.items():
        if file_data.get("type") != "directory":
            yield Service(item=filename)

def check_mikrotik_file(
    item: str,
    params: dict[str, Any],
    section: dict[str, dict[str, str]],
) -> CheckResult:
    """Check file age and status."""
    if item not in section:
        yield Result(state=State.UNKNOWN, summary="File not found")
        return

    file_data = section[item]

    # Special handling for watchdog file
    if item == "autosupout.rif":
        if file_data.get("notfound") == "True":
            yield Result(state=State.OK, summary="Watchdog file not present (expected)")
            return
        else:
            yield Result(state=State.CRIT, summary="Watchdog file present (unexpected)")
            return

    # Check file age
    time_str = file_data.get("creation-time") or file_data.get("last-modified")
    if not time_str:
        yield Result(state=State.UNKNOWN, summary="No timestamp information available")
        return

    # Determine time format pattern
    time_pattern = params.get("pattern", "")
    if not time_pattern:
        time_pattern = "%b/%d/%Y %H:%M:%S" if "/" in time_str else "%Y-%m-%d %H:%M:%S"

    try:
        file_time = datetime.strptime(time_str, time_pattern).timestamp()  # noqa: DTZ007
        current_time = time.time()
        file_age = current_time - file_time

        warn_age, crit_age = params.get("file_age", (90000, 176400))  # Default 25h/49h

        if file_age > crit_age:
            state = State.CRIT
            age_info = f"{render.timespan(file_age)} (above critical threshold)"
        elif file_age > warn_age:
            state = State.WARN
            age_info = f"{render.timespan(file_age)} (above warning threshold)"
        else:
            state = State.OK
            age_info = render.timespan(file_age)

        yield Result(
            state=state,
            summary=f"Last modified: {time_str.capitalize()}, Age: {age_info}",
        )

        # Add metric for file age
        yield Metric(
            name="file_age",
            value=file_age,
            levels=(warn_age, crit_age),
        )

    except ValueError as e:
        yield Result(
            state=State.UNKNOWN,
            summary=f"Cannot parse timestamp '{time_str}': {e!s}",
        )

# Register agent section
agent_section_mikrotik_file = AgentSection(
    name="mikrotik_file",
    parse_function=parse_mikrotik_file,
)

# Register check plugin
check_plugin_mikrotik_file = CheckPlugin(
    name="mikrotik_file",
    service_name="File %s",
    discovery_function=discover_mikrotik_file,
    check_function=check_mikrotik_file,
    check_default_parameters={
        "file_age": (90000, 176400),  # 25h/49h
        "pattern": "",
    },
    check_ruleset_name="mikrotik_file",
)
