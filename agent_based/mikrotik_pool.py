"""CheckMK agent-based check plugin for MikroTik IP pools.

Agent module "pools" (/ip/pool and the number of /ip/pool/used entries),
pipe separated because the ranges contain commas:
    pool|<name>|<ranges>|<next-pool>|<used addresses>

One service per pool ("IP Pool <name>") with used and free addresses. The
pool size is computed from the ranges: from-to, prefix or single address,
several separated by commas.

Contributed by Klaus Paulitsch <kp@workitout.at>.

SPDX-License-Identifier: GPL-3.0-only
"""

import ipaddress
from dataclasses import dataclass
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
    check_levels,
    render,
)


@dataclass(frozen=True)
class Pool:
    ranges: str
    next_pool: str
    used: int


Section = dict[str, Pool]


def parse_mikrotik_pool(string_table: StringTable) -> Section | None:
    """Parse pool lines; None if the module delivered nothing."""
    section: Section = {}
    for line in string_table:
        if len(line) < 5 or line[0] != "pool" or not line[1]:  # noqa: PLR2004
            continue
        try:
            used = int(line[4])
        except ValueError:
            used = 0
        section[line[1]] = Pool(ranges=line[2], next_pool=line[3], used=used)
    return section or None


def pool_size(ranges: str) -> int | None:
    """Number of addresses of a RouterOS ranges string.

    '10.0.0.10-10.0.0.20,10.0.1.0/24,10.0.2.5' -> 11 + 256 + 1
    """
    total = 0
    for part in (p.strip() for p in ranges.split(",")):
        if not part:
            continue
        try:
            if "-" in part:
                first, last = (ipaddress.ip_address(x.strip()) for x in part.split("-", 1))
                total += int(last) - int(first) + 1
            elif "/" in part:
                total += ipaddress.ip_network(part, strict=False).num_addresses
            else:
                ipaddress.ip_address(part)
                total += 1
        except ValueError:
            return None
    return total or None


def discover_mikrotik_pool(section: Section) -> DiscoveryResult:
    """One service per pool."""
    for name in section:
        yield Service(item=name)


def check_mikrotik_pool(item: str, params: dict[str, Any], section: Section) -> CheckResult:
    """Check used and free addresses of an IP pool."""
    if (pool := section.get(item)) is None:
        return
    size = pool_size(pool.ranges)
    if not size:
        yield Result(state=State.UNKNOWN, summary=f"Cannot parse ranges {pool.ranges!r}")
        return
    free = max(size - pool.used, 0)

    yield from check_levels(
        100.0 * pool.used / size,
        levels_upper=params.get("used_percent_upper"),
        metric_name="mikrotik_pool_used_percent",
        render_func=render.percent,
        label="Used",
        boundaries=(0, 100),
    )
    yield Result(state=State.OK, summary=f"{pool.used} of {size} addresses")
    yield from check_levels(
        free,
        levels_lower=params.get("free_lower"),
        metric_name="mikrotik_pool_free",
        render_func=lambda v: f"{int(v)}",
        label="Free",
    )
    yield Metric("mikrotik_pool_used", pool.used, boundaries=(0, size))
    if pool.next_pool and pool.next_pool != "none":
        yield Result(state=State.OK, summary=f"Next pool: {pool.next_pool}")
    yield Result(state=State.OK, notice=f"Ranges: {pool.ranges}")


# Register agent section
agent_section_mikrotik_pool = AgentSection(
    name="mikrotik_pool",
    parse_function=parse_mikrotik_pool,
)

# Register check plugin
check_plugin_mikrotik_pool = CheckPlugin(
    name="mikrotik_pool",
    service_name="IP Pool %s",
    discovery_function=discover_mikrotik_pool,
    check_function=check_mikrotik_pool,
    check_default_parameters={"used_percent_upper": ("fixed", (80.0, 90.0))},
    check_ruleset_name="mikrotik_pool",
)
