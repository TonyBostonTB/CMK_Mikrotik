# Changelog - Mikrotik Monitoring Plugin for Checkmk

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
