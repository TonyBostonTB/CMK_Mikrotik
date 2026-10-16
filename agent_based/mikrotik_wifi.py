"""CheckMK agent-based check plugin for MikroTik WiFi monitoring.

One service per SSID with the number of connected clients, their signal
strength and the state of the radios that broadcast the SSID. On a CAPsMAN
controller this covers all managed access points, and the HW/SW inventory
lists them (networking.wlan.controller.accesspoints).

Agent section (pipe separated, written by agent module "wifi"):
    iface|<driver>|<interface>|<ssid>|<up|down>
    client|<driver>|<interface>|<ssid>|<signal dBm>|<band>
    cap|<driver>|<identity>|<model>|<serial>|<version>|<base mac>|<state>
"""

from dataclasses import dataclass, field

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
)


@dataclass
class Ssid:
    """Radios and clients of one SSID."""

    interfaces: dict[str, str] = field(default_factory=dict)  # name -> up|down
    signals: list[int] = field(default_factory=list)
    clients: int = 0
    clients_per_band: dict[str, int] = field(default_factory=dict)
    clients_per_interface: dict[str, int] = field(default_factory=dict)


@dataclass
class Cap:
    """Access point managed by a CAPsMAN controller."""

    model: str
    serial: str
    version: str
    base_mac: str
    state: str


@dataclass
class Section:
    ssids: dict[str, Ssid] = field(default_factory=dict)
    caps: dict[str, Cap] = field(default_factory=dict)  # identity -> Cap


def parse_mikrotik_wifi(string_table: StringTable) -> Section:
    """Group interfaces and clients by SSID, collect managed access points."""
    section = Section()
    ssids = section.ssids
    ssid_of: dict[str, str] = {}

    for line in string_table:
        if len(line) >= 8 and line[0] == "cap" and line[2]:  # noqa: PLR2004
            _, _driver, identity, model, serial, version, base_mac, state = line[:8]
            section.caps[identity] = Cap(model, serial, version, base_mac, state)
        elif len(line) >= 5 and line[0] == "iface":  # noqa: PLR2004
            _, _driver, name, ssid, state = line[:5]
            if not ssid:
                continue
            ssid_of[name] = ssid
            ssids.setdefault(ssid, Ssid()).interfaces[name] = state

    for line in string_table:
        if len(line) >= 6 and line[0] == "client":  # noqa: PLR2004
            _, _driver, name, ssid, signal, band = line[:6]
            ssid = ssid or ssid_of.get(name, "")
            if not ssid:
                continue
            entry = ssids.setdefault(ssid, Ssid())
            entry.clients += 1
            if name:
                entry.clients_per_interface[name] = entry.clients_per_interface.get(name, 0) + 1
            if band:
                entry.clients_per_band[band] = entry.clients_per_band.get(band, 0) + 1
            try:
                entry.signals.append(int(signal))
            except ValueError:
                pass

    return section


def discover_mikrotik_wifi(section: Section) -> DiscoveryResult:
    """One service per SSID."""
    for ssid in section.ssids:
        yield Service(item=ssid)


def _counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in sorted(counts.items()))


def check_mikrotik_wifi(item: str, params: dict, section: Section) -> CheckResult:
    """Clients, signal strength and radio state of one SSID."""
    if (ssid := section.ssids.get(item)) is None:
        return

    yield from check_levels(
        ssid.clients,
        levels_upper=params.get("clients_upper"),
        levels_lower=params.get("clients_lower"),
        metric_name="mikrotik_wifi_clients",
        label="Clients",
        render_func=lambda v: f"{v:.0f}",
        boundaries=(0, None),
    )

    if ssid.signals:
        yield from check_levels(
            sum(ssid.signals) / len(ssid.signals),
            levels_lower=params.get("signal_avg_lower"),
            metric_name="mikrotik_wifi_signal_avg",
            label="Signal average",
            render_func=lambda v: f"{v:.0f} dBm",
        )
        yield from check_levels(
            min(ssid.signals),
            levels_lower=params.get("signal_min_lower"),
            metric_name="mikrotik_wifi_signal_min",
            label="Signal weakest client",
            render_func=lambda v: f"{v:.0f} dBm",
        )

    if ssid.interfaces:
        down = sorted(name for name, state in ssid.interfaces.items() if state != "up")
        total = len(ssid.interfaces)
        if down:
            yield Result(
                state=State(params.get("interface_down_state", 1)),
                summary=f"Radios down: {len(down)} of {total} ({', '.join(down)})",
            )
        else:
            yield Result(state=State.OK, summary=f"Radios up: {total}")

    if ssid.clients_per_band:
        yield Result(state=State.OK, notice=f"Clients per band: {_counts(ssid.clients_per_band)}")
    if ssid.clients_per_interface:
        yield Result(
            state=State.OK,
            notice=f"Clients per interface: {_counts(ssid.clients_per_interface)}",
        )


# Register agent section
agent_section_mikrotik_wifi = AgentSection(
    name="mikrotik_wifi",
    parse_function=parse_mikrotik_wifi,
)

# Register check plugin
check_plugin_mikrotik_wifi = CheckPlugin(
    name="mikrotik_wifi",
    service_name="WiFi %s",
    discovery_function=discover_mikrotik_wifi,
    check_function=check_mikrotik_wifi,
    check_default_parameters={"interface_down_state": 1},
    check_ruleset_name="mikrotik_wifi",
)


def inventory_mikrotik_wifi(section: Section) -> InventoryResult:
    """Access points managed by a CAPsMAN controller."""
    for identity, cap in section.caps.items():
        yield TableRow(
            path=["networking", "wlan", "controller", "accesspoints"],
            key_columns={"name": identity},
            inventory_columns={
                "model": cap.model,
                "serial": cap.serial,
                "version": cap.version,
                "base_mac": cap.base_mac,
            },
            status_columns={"state": cap.state},
        )


inventory_plugin_mikrotik_wifi = InventoryPlugin(
    name="mikrotik_wifi",
    inventory_function=inventory_mikrotik_wifi,
)
