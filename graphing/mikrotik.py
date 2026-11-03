"""Metric definitions, translations, graphs and Perf-O-Meters for the MikroTik checks.

Several checks report metrics that Checkmk does not know, so they had no
title, unit, graph template or Perf-O-Meter. This module

- translates metrics to existing Checkmk metrics where one fits
  (file_age -> age, poe_consumption -> power), so the standard graphs and
  Perf-O-Meters appear,
- translates generic names to package-prefixed ones (firewall packets,
  BGP counters), so they cannot clash with other extensions, and
- defines the package metrics (WiFi, WireGuard, firewall, BGP).

Translations only apply to the check plugins of this package.

Contributed by Klaus Paulitsch <kp@workitout.at>.

SPDX-License-Identifier: GPL-3.0-only
"""

from cmk.graphing.v1 import Title, graphs, metrics, perfometers, translations

UNIT_COUNT = metrics.Unit(metrics.DecimalNotation(""), metrics.StrictPrecision(0))
UNIT_PER_SECOND = metrics.Unit(metrics.DecimalNotation("/s"))
UNIT_TIME = metrics.Unit(metrics.TimeNotation())
UNIT_DBM = metrics.Unit(metrics.DecimalNotation("dBm"))

# ---------------------------------------------------------------------------
# Translations (per check plugin)
# ---------------------------------------------------------------------------

translation_mikrotik_file = translations.Translation(
    name="mikrotik_file",
    check_commands=[translations.PassiveCheck("mikrotik_file")],
    translations={"file_age": translations.RenameTo("age")},
)

translation_mikrotik_poe = translations.Translation(
    name="mikrotik_poe",
    check_commands=[translations.PassiveCheck("mikrotik_poe")],
    translations={"poe_consumption": translations.RenameTo("power")},
)

translation_mikrotik_firewall = translations.Translation(
    name="mikrotik_firewall",
    check_commands=[translations.PassiveCheck("mikrotik_firewall")],
    translations={
        "packets_per_second": translations.RenameTo("mikrotik_firewall_packets_per_second"),
    },
)

translation_mikrotik_bgp = translations.Translation(
    name="mikrotik_bgp",
    check_commands=[translations.PassiveCheck("mikrotik_bgp")],
    translations={
        "bgp_updates_received": translations.RenameTo("mikrotik_bgp_updates_received"),
        "bgp_updates_sent": translations.RenameTo("mikrotik_bgp_updates_sent"),
        "bgp_withdrawn_received": translations.RenameTo("mikrotik_bgp_withdrawn_received"),
    },
)

# ---------------------------------------------------------------------------
# Firewall filter rules
# ---------------------------------------------------------------------------

metric_mikrotik_firewall_packets_per_second = metrics.Metric(
    name="mikrotik_firewall_packets_per_second",
    title=Title("Packets matched by the rule"),
    unit=UNIT_PER_SECOND,
    color=metrics.Color.ORANGE,
)

graph_mikrotik_firewall_packets = graphs.Graph(
    name="mikrotik_firewall_packets",
    title=Title("Firewall rule packets"),
    compound_lines=["mikrotik_firewall_packets_per_second"],
)

# ---------------------------------------------------------------------------
# BGP (counters since the session was established)
# ---------------------------------------------------------------------------

metric_mikrotik_bgp_updates_received = metrics.Metric(
    name="mikrotik_bgp_updates_received",
    title=Title("BGP updates received"),
    unit=UNIT_COUNT,
    color=metrics.Color.GREEN,
)
metric_mikrotik_bgp_updates_sent = metrics.Metric(
    name="mikrotik_bgp_updates_sent",
    title=Title("BGP updates sent"),
    unit=UNIT_COUNT,
    color=metrics.Color.BLUE,
)
metric_mikrotik_bgp_withdrawn_received = metrics.Metric(
    name="mikrotik_bgp_withdrawn_received",
    title=Title("BGP withdrawn received"),
    unit=UNIT_COUNT,
    color=metrics.Color.RED,
)

graph_mikrotik_bgp_updates = graphs.Graph(
    name="mikrotik_bgp_updates",
    title=Title("BGP updates"),
    simple_lines=[
        "mikrotik_bgp_updates_received",
        "mikrotik_bgp_updates_sent",
        "mikrotik_bgp_withdrawn_received",
    ],
    optional=["mikrotik_bgp_updates_sent", "mikrotik_bgp_withdrawn_received"],
)

# ---------------------------------------------------------------------------
# WiFi
# ---------------------------------------------------------------------------

metric_mikrotik_wifi_clients = metrics.Metric(
    name="mikrotik_wifi_clients",
    title=Title("Connected clients"),
    unit=UNIT_COUNT,
    color=metrics.Color.BLUE,
)
metric_mikrotik_wifi_signal_avg = metrics.Metric(
    name="mikrotik_wifi_signal_avg",
    title=Title("Average client signal"),
    unit=UNIT_DBM,
    color=metrics.Color.GREEN,
)
metric_mikrotik_wifi_signal_min = metrics.Metric(
    name="mikrotik_wifi_signal_min",
    title=Title("Weakest client signal"),
    unit=UNIT_DBM,
    color=metrics.Color.RED,
)

perfometer_mikrotik_wifi_clients = perfometers.Perfometer(
    name="mikrotik_wifi_clients",
    focus_range=perfometers.FocusRange(perfometers.Closed(0), perfometers.Open(50)),
    segments=["mikrotik_wifi_clients"],
)

graph_mikrotik_wifi_signal = graphs.Graph(
    name="mikrotik_wifi_signal",
    title=Title("WiFi client signal"),
    simple_lines=["mikrotik_wifi_signal_avg", "mikrotik_wifi_signal_min"],
    optional=["mikrotik_wifi_signal_min"],
)

# ---------------------------------------------------------------------------
# WireGuard
# ---------------------------------------------------------------------------

metric_mikrotik_wireguard_handshake_age = metrics.Metric(
    name="mikrotik_wireguard_handshake_age",
    title=Title("Time since last handshake"),
    unit=UNIT_TIME,
    color=metrics.Color.PURPLE,
)

graph_mikrotik_wireguard_handshake_age = graphs.Graph(
    name="mikrotik_wireguard_handshake_age",
    title=Title("WireGuard handshake age"),
    simple_lines=[
        "mikrotik_wireguard_handshake_age",
        metrics.WarningOf("mikrotik_wireguard_handshake_age"),
        metrics.CriticalOf("mikrotik_wireguard_handshake_age"),
    ],
)
