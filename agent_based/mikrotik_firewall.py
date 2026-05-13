"""CheckMK agent-based check plugin for MikroTik firewall monitoring."""


import time
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
    get_rate,
    get_value_store,
    render,
)


def parse_mikrotik_firewall(string_table: StringTable) -> dict[str, dict[str, Any]]:  # noqa: C901
    """Parse MikroTik firewall rules from agent output."""
    data = {}
    current_rule = None
    show_disabled = False

    # detect section flag
    for line in string_table:
        if line and line[0] == "@show_disabled":
            show_disabled = True
            break

    for line in string_table:
        if not line:
            continue

        if line[0] == "@show_disabled":
            continue

        if line[0] == "comment":
            comment = " ".join(line[1:])

            if "checkmk:" in comment:
                current_rule = comment.split("checkmk: ")[1].split(")")[0].strip()
            else:
                current_rule = comment

            data[current_rule] = {
                "comment": comment,
                "disabled": "None",
                "chain": "unknown",
            }
            continue

        if current_rule is None:
            continue

        if line[0] == "bytes":
            data[current_rule]["bytes"] = int(line[1])
        elif line[0] == "packets":
            data[current_rule]["packets"] = int(line[1])
        elif line[0] in ["chain", "disabled"]:
            data[current_rule][line[0]] = " ".join(line[1:])

    # attach global flag
    data["_meta"] = {"show_disabled": show_disabled}

    return data


def discover_mikrotik_firewall(section: dict[str, dict[str, Any]]) -> DiscoveryResult:
    """Discover firewall rules."""
    show_disabled = section.get("_meta", {}).get("show_disabled", False)

    for rule_name, rule_data in section.items():

        if rule_name == "_meta":
            continue

        if rule_name == "None":
            continue

        disabled = rule_data.get("disabled")
        is_disabled = disabled == "true"

        if show_disabled or not is_disabled:
            yield Service(item=rule_name)


def check_mikrotik_firewall(
    item: str,
    params: dict[str, Any],  # noqa: ARG001
    section: dict[str, dict[str, Any]],
) -> CheckResult:
    """Check firewall rule traffic and status."""
    if item not in section:
        yield Result(state=State.UNKNOWN, summary="Firewall rule not found")
        return

    rule_data = section[item]
    value_store = get_value_store()
    now = time.time()

    disabled_raw = rule_data.get("disabled")
    is_disabled = disabled_raw == "true"

    disabled_text = "Yes" if is_disabled else "No"

    # Rule status
    if is_disabled:
        yield Result(
            state=State.CRIT,
            summary=f"Disabled: {disabled_text}",
        )
    else:
        yield Result(
            state=State.OK,
            summary=f"Disabled: {disabled_text}",
        )

    # Rule information
    yield Result(
        state=State.OK,
        summary=f"Chain: {rule_data.get('chain', 'unknown')}",
        details=f"Comment: {rule_data.get('comment', 'No comment')}",
    )

    # Traffic metrics
    if "bytes" in rule_data:
        bytes_rate = get_rate(
            value_store,
            f"mikrotik_firewall.{item}.bytes",
            now,
            rule_data["bytes"],
        )
        yield Metric(
            name="if_total_bps",
            value=bytes_rate * 8,
        )
        yield Result(
            state=State.OK,
            notice=f"Traffic: {render.networkbandwidth(bytes_rate)}",
        )

    if "packets" in rule_data:
        packets_rate = get_rate(
            value_store,
            f"mikrotik_firewall.{item}.packets",
            now,
            rule_data["packets"],
        )
        yield Metric(
            name="packets_per_second",
            value=packets_rate,
        )


# Register agent section
agent_section_mikrotik_firewall = AgentSection(
    name="mikrotik_firewall",
    parse_function=parse_mikrotik_firewall,
)

# Register check plugin
check_plugin_mikrotik_firewall = CheckPlugin(
    name="mikrotik_firewall",
    service_name="Firewall Filter %s",
    discovery_function=discover_mikrotik_firewall,
    check_function=check_mikrotik_firewall,
    check_default_parameters={},
    check_ruleset_name="mikrotik_firewall",
)
