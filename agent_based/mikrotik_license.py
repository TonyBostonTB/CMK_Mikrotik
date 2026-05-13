"""CheckMK agent-based check plugin for MikroTik license monitoring."""


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


def parse_mikrotik_license(string_table: StringTable) -> dict[str, str]:
    """Parse MikroTik license information from agent output."""
    return {line[0]: " ".join(line[1:]) for line in string_table if line}

def discover_mikrotik_license(section: dict[str, str]) -> DiscoveryResult:
    """Discover license service if deadline information is present."""
    if "deadline-at" in section:
        yield Service()

def check_mikrotik_license(
    params: dict[str, Any],
    section: dict[str, str],
) -> CheckResult:
    """Check MikroTik license expiration and renewal time."""
    if "deadline-at" not in section or "next-renewal-at" not in section:
        yield Result(state=State.UNKNOWN, summary="No license information found")
        return

    try:
        # Determine time format pattern
        time_pattern = params.get("pattern", "")
        if not time_pattern:
            time_pattern = (
                "%b/%d/%Y %H:%M:%S" if "/" in section["deadline-at"]
                else "%Y-%m-%d %H:%M:%S"
            )

        # Parse license times
        # MikroTik returns local time without timezone; naive datetime is intentional.
        deadline_time = datetime.strptime(  # noqa: DTZ007
            section["deadline-at"], time_pattern,
        ).timestamp()
        renewal_time = datetime.strptime(  # noqa: DTZ007
            section["next-renewal-at"], time_pattern,
        ).timestamp()

        current_time = time.time()
        time_remaining = deadline_time - current_time
        renewal_remaining = renewal_time - current_time

        warn, crit = params.get("time_remaining", (1209600, 259200))  # Default 14d/3d

        # Determine state based on remaining time
        if time_remaining < crit:
            state = State.CRIT
            time_info = f"Expiry in {render.timespan(time_remaining)} (critical)"
        elif time_remaining < warn:
            state = State.WARN
            time_info = f"Expiry in {render.timespan(time_remaining)} (warning)"
        else:
            state = State.OK
            time_info = f"Expiry in {render.timespan(time_remaining)}"

        yield Result(
            state=state,
            summary=time_info,
            details=f"Renewal in {render.timespan(renewal_remaining)}",
        )

        yield Metric(
            name="license_time_remaining",
            value=time_remaining,
            levels=(warn, crit),
            boundaries=(0, None),
        )

    except ValueError as e:
        yield Result(
            state=State.UNKNOWN,
            summary=f"Cannot parse license timestamps: {e!s}",
        )

# Register agent section
agent_section_mikrotik_license = AgentSection(
    name="mikrotik_license",
    parse_function=parse_mikrotik_license,
)

# Register check plugin
check_plugin_mikrotik_license = CheckPlugin(
    name="mikrotik_license",
    service_name="License",
    discovery_function=discover_mikrotik_license,
    check_function=check_mikrotik_license,
    check_default_parameters={
        "time_remaining": (1209600, 259200),  # 14d/3d
        "pattern": "",
    },
    check_ruleset_name="mikrotik_license",
)
