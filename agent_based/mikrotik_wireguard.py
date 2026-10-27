"""CheckMK agent-based check plugin for MikroTik WireGuard monitoring.

One service per WireGuard peer with the age of the latest handshake and the
traffic of the peer. WireGuard has no connection state: a handshake happens
at least every two minutes while traffic flows, so the handshake age shows
whether the tunnel is up. An idle tunnel only keeps handshaking if one side
sets persistent-keepalive.

Agent section (pipe separated, written by agent module "wireguard"):
    peer|<interface>|<name>|<comment>|<public key>|<disabled>|<endpoint>|<last handshake>|<rx bytes>|<tx bytes>
"""

import re
import time
from dataclasses import dataclass

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    GetRateError,
    Metric,
    Result,
    Service,
    State,
    StringTable,
    check_levels,
    get_rate,
    get_value_store,
    render,
)

_UNIT_SECONDS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1,
                 "ms": 0.001, "us": 0.000001, "ns": 0.000000001}
_DURATION_PART = re.compile(r"(\d+)(ms|us|ns|w|d|h|m|s)")
_CLOCK = re.compile(r"(\d+):(\d+):(\d+)(?:\.\d+)?$")


@dataclass
class Peer:
    """One WireGuard peer as reported by /interface/wireguard/peers."""

    interface: str
    name: str
    comment: str
    public_key: str
    disabled: bool
    endpoint: str
    last_handshake: float | None  # seconds ago, None if never
    rx_bytes: int | None
    tx_bytes: int | None


Section = dict[str, Peer]


def parse_duration(text: str) -> float | None:
    """Seconds of a RouterOS duration such as 1m9s, 1w2d3h or 1d02:03:04."""
    text = text.strip()
    if not text:
        return None
    seconds = 0.0
    if clock := _CLOCK.search(text):
        hours, minutes, secs = (int(group) for group in clock.groups())
        seconds += hours * 3600 + minutes * 60 + secs
        text = text[: clock.start()]
    rest = _DURATION_PART.sub("", text)
    if rest:
        return None
    for value, unit in _DURATION_PART.findall(text):
        seconds += int(value) * _UNIT_SECONDS[unit]
    return seconds


def _int_or_none(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


def peer_item(name: str, comment: str, public_key: str) -> str:
    """Service item: the comment, else the peer name, else the key prefix."""
    return comment or name or public_key[:8]


def parse_mikrotik_wireguard(string_table: StringTable) -> Section:
    """One Peer per item, the first one wins on duplicate items."""
    section: Section = {}
    for line in string_table:
        if len(line) < 10 or line[0] != "peer":  # noqa: PLR2004
            continue
        _, interface, name, comment, public_key, disabled, endpoint, handshake, rx, tx = line[:10]
        item = peer_item(name, comment, public_key)
        if not item or item in section:
            continue
        section[item] = Peer(
            interface=interface,
            name=name,
            comment=comment,
            public_key=public_key,
            disabled=disabled == "true",
            endpoint=endpoint,
            last_handshake=parse_duration(handshake),
            rx_bytes=_int_or_none(rx),
            tx_bytes=_int_or_none(tx),
        )
    return section


def discover_mikrotik_wireguard(section: Section) -> DiscoveryResult:
    """One service per peer that is not disabled."""
    for item, peer in section.items():
        if not peer.disabled:
            yield Service(item=item)


def check_mikrotik_wireguard(item: str, params: dict, section: Section) -> CheckResult:
    """Handshake age and traffic of one WireGuard peer."""
    if (peer := section.get(item)) is None:
        return

    if peer.disabled:
        yield Result(state=State(params.get("disabled_state", 1)), summary="Peer is disabled")
        return

    if peer.last_handshake is None:
        yield Result(state=State(params.get("no_handshake_state", 2)), summary="No handshake yet")
    else:
        yield from check_levels(
            peer.last_handshake,
            levels_upper=params.get("handshake_age"),
            metric_name="mikrotik_wireguard_handshake_age",
            label="Last handshake",
            render_func=render.timespan,
            boundaries=(0, None),
        )

    if peer.endpoint:
        yield Result(state=State.OK, summary=f"Endpoint: {peer.endpoint}")
    yield Result(state=State.OK, notice=f"Interface: {peer.interface}")
    if peer.name and peer.name != item:
        yield Result(state=State.OK, notice=f"Peer name: {peer.name}")

    value_store = get_value_store()
    now = time.time()
    for direction, value, metric in (
        ("In", peer.rx_bytes, "if_in_bps"),
        ("Out", peer.tx_bytes, "if_out_bps"),
    ):
        if value is None:
            continue
        try:
            rate = get_rate(value_store, f"mikrotik_wireguard.{item}.{metric}", now, value)
        except GetRateError:
            continue
        yield Metric(metric, rate * 8)
        yield Result(state=State.OK, notice=f"{direction}: {render.networkbandwidth(rate)}")


# Register agent section
agent_section_mikrotik_wireguard = AgentSection(
    name="mikrotik_wireguard",
    parse_function=parse_mikrotik_wireguard,
)

# Register check plugin
check_plugin_mikrotik_wireguard = CheckPlugin(
    name="mikrotik_wireguard",
    service_name="WireGuard %s",
    discovery_function=discover_mikrotik_wireguard,
    check_function=check_mikrotik_wireguard,
    check_default_parameters={
        "handshake_age": ("fixed", (300.0, 900.0)),
        "no_handshake_state": 2,
        "disabled_state": 1,
    },
    check_ruleset_name="mikrotik_wireguard",
)
