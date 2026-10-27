"""CheckMK agent-based check plugin for MikroTik CHR license monitoring.

A paid CHR license (p1, p10, p-unlimited) is perpetual. The CHR only has to
reach the MikroTik account server before deadline-at to renew it; if that
fails, the router keeps its level but RouterOS upgrades and package changes
are blocked (limited-upgrades: yes). The free level is limited to 1 Mbit/s
upload per interface.

Agent section (key value, written by agent module "license", CHR):
    system-id <id>
    level <free|p1|p10|p-unlimited>
    limited-upgrades <true|false>
    next-renewal-at <time>
    deadline-at <time>
"""

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


def parse_mikrotik_license(string_table: StringTable) -> dict[str, str]:
    """Parse MikroTik license information from agent output."""
    return {line[0]: " ".join(line[1:]) for line in string_table if line}


def discover_mikrotik_license(section: dict[str, str]) -> DiscoveryResult:
    """One service on a CHR. RouterBOARD licenses have no system-id and level."""
    if "system-id" in section and "level" in section:
        yield Service()


def check_mikrotik_license(
    params: dict[str, Any],
    section: dict[str, str],
) -> CheckResult:
    """Valid license, no license (free) or renewal failed (upgrades blocked)."""
    level = section.get("level", "")
    if not level:
        yield Result(state=State.UNKNOWN, summary="No license information found")
        return

    if level == "free":
        yield Result(
            state=State(params.get("free_state", 2)),
            summary="No license (free, 1 Mbit/s upload per interface)",
        )
    # the API reports true/false, the CLI yes/no
    elif section.get("limited-upgrades") in ("true", "yes"):
        yield Result(
            state=State(params.get("limited_upgrades_state", 1)),
            summary=f"License {level} not renewed, upgrades blocked",
        )
    else:
        yield Result(state=State.OK, summary=f"Valid license: {level}")

    for key, label in (("next-renewal-at", "Next renewal"), ("deadline-at", "Renewal deadline")):
        if value := section.get(key):
            yield Result(state=State.OK, notice=f"{label}: {value}")


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
        "free_state": 2,
        "limited_upgrades_state": 1,
    },
    check_ruleset_name="mikrotik_license",
)
