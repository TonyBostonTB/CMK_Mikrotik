# Changelog - Mikrotik Monitoring Plugin for Checkmk

## [4.7.0] - 2026-11-11
### Added
- **System resources** (new opt-in agent module system, rule option
  "System resources", RouterOS 6 and 7, one /system/resource request,
  contributed by Klaus Paulitsch): CPU utilization on hosts without
  SNMP (rule "CPU utilization for simple devices", default WARN 80, CRIT
  90 percent),
  memory through the Checkmk memory check (rule "Memory levels"),
  Filesystem system disk through the standard filesystem check (rule
  "File systems") and uptime through the Checkmk uptime check. Same
  service names and items as via SNMP. New service NAND bad blocks
  (default WARN 2, CRIT 5 percent, new check rule "MikroTik NAND bad
  blocks") with metric and Perf-O-Meter. Works with the RouterOS API and
  the REST API.

### Upgrade notes
- System resources: the module is off in existing rules and not part of
  the agent default "all". Enable "System resources" in the special
  agent rule and run a service discovery. If the host is also polled via
  SNMP, the module replaces the SNMP services for memory, system disk
  and uptime (same service names, so the history stays), but only while
  it delivers data. CPU utilization stays with SNMP on such hosts, because
  the short-term cpu-load of RouterOS is measured during the SNMP query;
  the module's CPU service is only discovered on hosts without SNMP.

## [4.6.0] - 2026-11-10
### Added
- **Network interfaces** (new opt-in agent module interfaces, rule option
  "Network interfaces", RouterOS 6 and 7, /interface and
  /interface/ethernet/monitor, contributed by Klaus Paulitsch): one
  service Interface per interface through the standard Checkmk interface
  check, so the rules "Network interface and switch port discovery" and
  "Network interfaces and switch ports" apply. Index, description, alias
  and port type are the same as via SNMP (ifIndex is the RouterOS id,
  ifDescr the name, ifAlias the comment), so the items stay the same when a host is
  switched from SNMP. Negotiated speed of ethernet and SFP ports, admin
  down for disabled interfaces, not present for an SFP cage without
  module. Interface graphs, bandwidth Perf-O-Meter and HW/SW inventory.
  Works with the RouterOS API and the REST API.

### Upgrade notes
- Network interfaces: the module is off in existing rules and not part
  of the agent default "all". Enable "Network interfaces" in the special
  agent rule and run a service discovery. If the host is also polled via
  SNMP, the module replaces the SNMP interface services (same items, so
  the history stays), but only while it delivers data.

## [4.5.0] - 2026-11-04
### Added
- **UPS** (new opt-in agent module ups, rule option "UPS", RouterOS 6
  and 7, /system/ups with package ups.npk, contributed by Klaus
  Paulitsch): one service UPS per UPS with power source (CRIT on
  battery), battery low (CRIT), replace battery and overload (WARN),
  battery charge (default WARN 50, CRIT 25 percent), runtime left
  (default WARN 10, CRIT 5 minutes), load (default WARN 80, CRIT 90
  percent) and optionally temperature; voltages and frequency as
  metrics. CRIT if the UPS delivers no monitor data. New check rule
  "MikroTik UPS". Model, serial and firmware in the HW/SW inventory.
  Works with the RouterOS API and the REST API.

### Upgrade notes
- UPS: the module is off in existing rules and not part of the agent
  default "all". Enable "UPS" in the special agent rule and run a
  service discovery.

## [4.4.0] - 2026-11-04
### Added
- **IP pools** (new opt-in agent module pools, rule option "IP pools",
  RouterOS 6 and 7, /ip/pool, contributed by Klaus Paulitsch): one service
  IP Pool per pool with used and free addresses; levels for used
  addresses in percent (default WARN 80, CRIT 90) and optionally for free
  addresses, new check rule "MikroTik IP Pools". Uses the total, used and
  available counts of newer RouterOS 7 versions; otherwise the agent
  counts /ip/pool/used and only transfers the number, not the leases.
  UNKNOWN if the used addresses cannot be read. Metrics, Perf-O-Meter and
  graphs. Works with the RouterOS API and the REST API.
- **NTP client** (new opt-in agent module ntp, rule option "NTP client",
  RouterOS 7, /system/ntp/client, contributed by Klaus Paulitsch): service
  NTP Time with synchronisation status, synced server, absolute time
  offset (default WARN 200 ms, CRIT 500 ms) and stratum (default WARN 10,
  CRIT 15); a disabled client is WARN. New check rule "MikroTik NTP
  Client". Works with the RouterOS API and the REST API.
- **Metric definitions, graphs and Perf-O-Meters** (new file
  graphing/mikrotik.py, contributed by Klaus Paulitsch):
  - File age and PoE Consumption now use the Checkmk metrics age and
    power, so the standard graphs and Perf-O-Meters appear.
  - Firewall Filter: packets metric with title and unit, graph.
  - BGP: titles and units for the update counters, graph BGP updates.
  - WiFi: metrics for clients and signal, Perf-O-Meter for connected
    clients, graph WiFi client signal.
  - WireGuard: metric for the handshake age, graph with levels.
- Translations only apply to the check plugins of this package; generic
  metric names (firewall packets, BGP counters) are renamed to
  names with the prefix mikrotik so they cannot clash with other
  extensions.

### Upgrade notes
- IP pools: the module is off in existing rules and not part of the agent
  default "all". Enable "IP pools" in the special agent rule and run a
  service discovery.
- NTP client: the module is off in existing rules and not part of the
  agent default "all". Enable "NTP client" in the special agent rule and
  run a service discovery.
- Metrics: no rediscovery needed. Graphs of the renamed metrics (file age, PoE,
  firewall packets, BGP counters) start anew, the old values stay
  in the old RRD files.

## [4.3.3] - 2026-11-02
### Fixed
- **REST API always used HTTP**: with the RESTful API the agent connected
  via plain HTTP, even with SSL enabled in the rule, and sent the
  credentials unencrypted. It now uses HTTPS unless SSL mode is "no SSL".
- **Rule sets that did not exist**: the BGP, VRRP and Firewall Filter
  checks referenced check rules that the package does not provide. These
  checks have no parameters and no longer reference a rule.
- **License header**: the agent header said GPL version 2, the package is
  licensed under GPL version 3 only (see LICENSE).

### Upgrade notes
- REST API on port 80 only worked because of the HTTP bug. Such rules
  need SSL mode "no SSL", or the device needs the www-ssl service and
  port 443.
- No rediscovery needed.

## [4.3.2] - 2026-10-28
### Fixed
- **Firewall Rules double checkboxes**: "Enable firewall monitoring" and
  "Show disabled rules" showed two checkboxes each (one to set the option,
  one for its value). Both options are now always present with a single
  checkbox, like the WiFi and WireGuard options.
- **Legacy rules with firewall enabled**: rules stored with the old list of
  modules turned "firewall" into a plain flag instead of the Firewall Rules
  options. They now migrate to "Enable firewall monitoring" on.

### Upgrade notes
- Existing rules without these options are read as off (same behavior as
  before). No rediscovery needed.

## [4.3.1] - 2026-10-27
### Added
- New check rule "MikroTik OSPF Neighbor" for the adjacency states that
  count as OK (the check referenced the rule, but it did not exist).

### Fixed
- **OSPF Neighbor crash**: the check crashed with a TypeError (State values
  compared with max) as soon as one adjacency was not in an OK state (for
  example Init). Each adjacency now yields its own result, the service
  state is the worst of them.
- **OSPF adjacencies lost**: a router-id that appears more than once
  (several interfaces, on RouterOS 7 also OSPFv2 and OSPFv3) kept only its
  last address. All adjacencies of a neighbor are now monitored.
- **OSPF state on the wrong address**: a state reported without an address
  was stored on the address of the previous neighbor.

### Changed
- OSPF adjacency states: Full and 2-Way (TwoWay) are OK, Down is CRIT,
  Attempt, Init, ExStart, Exchange and Loading are WARN, any other state
  is UNKNOWN (was WARN).
- The OSPF agent module also reports the interface and the OSPF instance
  of each adjacency, shown in the service details and in the summary of
  adjacencies that are not OK.

### Upgrade notes
- No rediscovery needed, the service item is still the
  neighbor router-id. Interface and instance appear once the special agent
  of version 4.3.1 runs; older agent output is still parsed.

## [4.3.0] - 2026-10-27
### Added
- **WireGuard per peer**: new agent module `wireguard` (rule option
  "WireGuard peers", RouterOS 7). One service per peer with the age
  of the latest handshake (WARN 5 min, CRIT 15 min by default), endpoint
  and inbound/outbound traffic. The item is the peer comment, else its
  name. Disabled peers are not discovered.
- New check rule "MikroTik WireGuard": levels for the handshake age,
  state for a peer without handshake (default CRIT) and for a disabled
  peer (default WARN).

### Changed
- **CHR License** reworked: a paid CHR license is perpetual, so the service
  no longer counts down to deadline-at as an expiry. It is OK with a paid
  level (p1, p10, p-unlimited), CRIT without a license (level free) and
  WARN if the renewal failed and upgrades are blocked (limited-upgrades).
  Next renewal and renewal deadline are shown as details. Also discovered
  on CHRs with level free.
- New check rule "MikroTik CHR License" for both states (the check had no
  rule before).
- Special agent rule: "WiFi clients and radios" and "WireGuard peers" are
  single checkboxes now like the other modules. Before, the optional outer
  checkbox only added the option and an empty inner one stored it as off.
  Rules without the keys are migrated to off.
- Agent version string updated to 4.3.0

### Fixed
- Agent: RouterOS API values that contain `=` (base64 keys, comments with
  `=`) were dropped from every module.

### Upgrade notes
- `wireguard` is opt-in like `wifi`: the agent default "all" does not
  include it. Enable "WireGuard peers" in the special agent rule and run
  a service discovery.
- An idle tunnel only handshakes if one side sets persistent-keepalive.
  Without it, an idle but healthy tunnel goes CRIT.
- CHR License: the time remaining metric is gone. Run a service
  discovery on CHRs with level free to get the License service.

## [4.2.0] - 2026-10-16
### Added
- **WiFi service per SSID**: new agent module `wifi` (rule option "WiFi
  clients and radios"). Reports connected clients, average and weakest
  client signal (dBm) and the radios that broadcast the SSID. Works with
  the new `wifi` driver (RouterOS 7.13+), the legacy `wireless` driver and
  the legacy CAPsMAN. On a CAPsMAN controller one host covers all managed
  access points; a radio that is not running (access point lost the
  controller) makes the service WARN by default.
- New check rule "MikroTik WiFi": levels for clients and signal, state for
  radios that are down.
- **HW/SW inventory of managed access points**: on a CAPsMAN controller
  the `wifi` module also lists every managed access point (new CAPsMAN
  and legacy `/caps-man`) under `networking.wlan.controller.accesspoints`
  (same table as Aruba/Cisco WLC): identity, model, serial, RouterOS
  version, base MAC, state.

### Changed
- Agent version string updated to 4.2.0

### Upgrade notes
- The module is off in existing rules. Enable "WiFi clients and radios"
  in the special agent rule of the CAPsMAN controller (or standalone access
  point) and run a service discovery.
- `wifi` is opt-in: the agent default "all" (a rule with no module ticked)
  does not include it, it only runs when selected explicitly.
- The new `wifi` driver does not report clients via SNMP, so this is the
  only way to monitor clients of WiFi 6 (ax) MikroTik access points.

## [4.1.0] - 2026-10-13
### Added
- **RouterOS Info**: the agent module `board` now also queries
  `/system/routerboard` and reports serial number and RouterBOOT firmware
  (`current-firmware`, `upgrade-firmware`). Keys are emitted with an `rb-`
  prefix in the board agent section.
- **Firmware upgrade pending**: if `upgrade-firmware` is higher than
  `current-firmware`, RouterOS Info reports the pending RouterBOOT upgrade.
  New rule parameter "State if RouterBOOT firmware upgrade is pending"
  (default WARN).
- **HW/SW inventory plugin**: `hardware.system`
  (manufacturer, model, serial), `software.os` (vendor, name, version),
  `software.firmware` (vendor, version). Needs the "Do HW/SW Inventory" rule.

### Changed
- Agent version string updated to 4.1.0

### Upgrade notes
- No rule changes needed. Serial and firmware appear in `RouterOS Info` once
  the special agent runs with the module "RouterOS Board Info" enabled.
- The inventory data needs the "Do HW/SW Inventory" rule on the MikroTik hosts.

## [4.0.3] - 2026-05-26
### Fixed
- Agent version string updated to `4.0.3-mikrotik_agent`
- Removed inaccurate V×I power calculation from `Power PSU` services;
  power is now exclusively reported by the dedicated `PoE Consumption` service

## [4.0.2] - 2026-05-26
### Added
- **PoE Consumption service**: RouterOS health field `poe-out-consumption` is now
  emitted as a dedicated `<<<mikrotik_poe>>>` section and monitored as a separate
  "PoE Consumption" service showing output watts and a `poe_consumption` metric.
- **FAN Status service**: the `fan-state` field (overall fan health reported by RouterOS)
  was previously silently dropped by the fan parser. It is now discovered as a
  "FAN Status" service item alongside the per-fan speed services.

## [4.0.1] - 2026-05-26
### Fixed
- **Power calculation**: currents of exactly 100 mA were not converted to amps
  because the boundary check used `>` instead of `>=`. This caused a current of
  100 mA to be treated as 100 A, producing absurd wattage readings (e.g. 5430 W
  instead of 5.4 W) on switches whose PSU current sits at that exact threshold.
- **Agent version string**: the `<<<check_mk>>>` header still reported
  `3.3.x-mikrotik_agent`; updated to `4.0.1-mikrotik_agent`.

## [4.0.0] - 2026-05-13
### Changed
- **Requires CheckMK 2.4 or later.** The `cmk.gui.plugins.wato` API was
  removed in CheckMK 2.5. The plugin now uses the `cmk.rulesets.v1` and
  `cmk.server_side_calls.v1` APIs, replacing the `wato/` directory with
  `rulesets/` and `server_side_calls/`.
- The two separate SSL/TLS dropdowns (`Use SSL` and `Validate certificate`)
  have been replaced by a single **Connection security** dropdown with three
  mutually exclusive options: SSL (verify certificate), SSL (skip certificate
  verification), and Plain TCP.
- Power monitoring redesigned: one service per PSU (`Power PSU1`,
  `Power PSU2`, …) instead of a single aggregated `Power Usage` service,
  fixing doubled readings on dual-PSU devices. RouterOS's own
  `power-consumption` field is now captured directly.
- Fan check: the `output_metrics` toggle has been removed; performance
  metrics are always emitted.
- Password store lookup now uses `cmk.utils.password_store.lookup()`,
  correctly handling CheckMK's binary password store format. Previously,
  using the CheckMK password store caused login failures.
- Stored rules are automatically migrated on MKP install — no manual
  reconfiguration needed. Hyphenated keys (`no-ssl`, `skip-cert-check`,
  `show-disabled`) are renamed transparently, and obsolete keys
  (`output_metrics`, `psu_count`) are stripped silently.

### Migration notes (v3.x → v4.0.0)
- **Special agent and check parameter rules**: migrated automatically on
  MKP install. No action required.
- **Power services**: the old `Power Usage` service is incompatible with
  the new per-PSU check. After installing the MKP, run **Update service
  configuration** on any MikroTik host that had health monitoring enabled.
  The old service will be removed and replaced by `Power PSU1` / `Power PSU2`
  (or however many PSUs the device reports).

## [3.3.0] - 2026-02-18
### Changed
- Add the option to show the disabled firewall rules that is discovery by the plugin (Thanks to Marcel Eckert for the suggestion)
- Completely rewritten the configuration section on WATO
- ⚠️ You must remove any previous rules based on this plugin and reconfigure from scratch

## [3.2.2] - 2025-08-06
### Fixed
- Resolved an issue that not correctly load the enabled firewall rules (Thanks to Marcel Eckert for the suggestion)

## [3.2.2] - 2025-08-06
### Fixed
- Resolved an issue that not show section "Mikrotik RouterOS" on WATO to set plugin (Thanks to Hugo for the suggestion)

## [3.2.1] - 2025-08-04
### Changed
- Set state to CRITICAL from UNKNOWN when BGP neighbor peer or OSPF neighbor peer is not found

## [3.2.0] - 2025-08-01
### Changed
- Complete rewrite of the plugin to support new version of CheckMK API v2.
- Incompatible with previous versions of Checkmk: use version 3.0.5 or earlier.
- ⚠️ You must remove any previous version of this plugin before installing.

### Added
- Compatibility with CheckMK 2.4

## [3.0.5] - 2025-06-05
### Fixed
- Changed shebang to use `/usr/bin/env python3` in all scripts and agents. (Thanks to Bernhard Petschowitsch for the suggestion)

## [3.0.4] - 2025-05-27
### Fixed
- Python3 environment issues in agent-based scripts.

## [3.0.3] - 2024-04-30
### Fixed
- Resolved regex warning during Checkmk updates.

## [3.0.2] - 2025-04-22
### Changed
- Reworked agent that connects to MikroTik.
- SSL connection is now enabled by default.
- Option added to skip certificate validation.
- Rewritten WATO configuration plugin.
- ⚠️ You must reconfigure the datasource rule in Checkmk after installing.

## [2.6.5] - 2025-04-07
### Fixed
- Documentation updated.

## [2.6.4] - 2025-04-07
### Fixed
- Fixed MikroTik API connection issue when result is empty.

## [2.6.3] - 2025-03-30
### Fixed
- Fixed a bug introduced in previous bugfix.

## [2.6.2] - 2025-03-30
### Fixed
- Bug in watchdog file detection via RESTful API.
- Minor improvements in `mikrotik_file`.

## [2.6.1] - 2025-03-24
### Fixed
- Crash when running `cmk -R` after upgrading from 2.5.x.
- Added check for `requests` module on import.
- Improved IPsec failure detection logic.

## [2.6.0] - 2025-03-24
### Added
- Option to use RESTful API for data collection.
- ⚠️ Requires rule reconfiguration.

## [2.5.7] - 2024-12-23
### Added
- License checking on CHR.

## [2.5.6] - 2024-10-21
### Fixed
- `mikrotik_file` works with RouterOS 7.16.1.

## [2.5.5] - 2024-04-04
### Fixed
- Bug in non-established BGP sessions (RouterOS v7).

## [2.5.4] - 2024-02-16
### Changed
- Reworked power section.

## [2.5.3] - 2024-02-16
### Added
- OSPF support for RouterOS v7 and IPv6.
- BGP support for recent v7 builds.
- Reworked special agent.

## [2.5.2] - 2024-02-01
### Fixed
- Bug with multibyte characters in API call.

## [2.5.1] - 2024-02-01
### Fixed
- Crash in power consumption calculation on new OS.
- Added handling of `autosupout.rif`.

## [2.5.0] - 2024-01-19
### Fixed
- Crash on CHR.
- Adjusted board section (requires `cmk -R`).

## [2.4.1] - 2023-11-03
### Fixed
- Crash in BGP when information is missing.

## [2.4.0] - 2023-09-26
### Changed
- BGP and file age support for RouterOS v7.

## [2.3.4] - 2023-08-09
### Added
- Compatibility with Checkmk 2.1 and 2.2.

## [2.3.3] - 2023-04-04
### Fixed
- Crash on multiple IPsec connections.

## [2.3.2] - 2023-03-08
### Added
- GPL headers.

## [2.3.1] - 2023-03-06
### Fixed
- PSU discovery issue.

## [2.3.0] - 2023-03-06
### Changed
- Complete rewrite for Checkmk 2.x.
- Changed versioning scheme.
- Switched to `os-python3` and modern SSL ciphers.
- Multiple improvements in summaries and plugin logic.

## [2.2] - 2022-05-11
### Fixed
- Handled orphaned IPsec SAs.
- Increased SA count now gives WARN instead of CRIT.

## [2.1] - 2021-01-19
### Added
- File age check.
- Minor firewall bugfix.

## [2.0a] - 2020-10-28
### Fixed
- PSU bugfix.

## [2.0] - 2020-10-28
### Changed
- Major rewrite of special agent to Python 3.
- Added firewall filter rule checks.

## [1.2a] - 2020-09-21
### Fixed
- Wrong header info.

## [1.2] / [1.1] - 2020-09
### Changed
- Major rewrite for Checkmk 1.6.

## [1.0] - 2020-01-20
### Added
- Major rewrite for RouterOS switches.
- Added PSU and IPsec info.
- Inventory ignores disabled VRRP.

## [0.4a] - 2019-07-23
### Fixed
- Bug in electrical current calculation.

## [0.4] - 2019-04-23
### Added
- Power info on dual-PSU devices.
- Power-loss detection.
### Fixed
- Board info bug for AP devices.

## [0.3] - 2019-04-23

## [0.2] - 2018-10-17

## [0.1] - 2018-10-12
### Initial release by ttr
