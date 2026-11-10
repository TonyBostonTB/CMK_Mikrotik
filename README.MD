## MikroTik RouterOS Plugin for CheckMK

This plugin provides comprehensive monitoring of MikroTik RouterOS devices
using the RouterOS API (v2, for RouterOS 7.x+) or the RESTful API.

It includes checks for:

- BGP and OSPF neighbors
- VRRP status
- PSU, fan, and temperature sensors
- IPsec tunnels
- CHR license (valid, no license, renewal failed) and file age
- Firewall rules based on comment filters
- System health and crashfile detection
- RouterOS Info: model, serial, RouterOS version, RouterBOOT firmware
  (state if a firmware upgrade is pending) and HW/SW inventory
- WiFi per SSID: clients, signal strength and radio state, for the new
  `wifi` driver, the legacy `wireless` driver and CAPsMAN (one controller
  covers all its access points) and HW/SW inventory of the access points
  managed by a CAPsMAN controller (model, serial, version)
- WireGuard per peer: age of the latest handshake, endpoint and traffic
- NTP client: synchronisation status, time offset and stratum
- IP pools: used and free addresses per pool (DHCP, PPP, hotspot)
- Network interfaces: traffic, errors, state and speed through the standard
  Checkmk interface check, items the same as via SNMP
- UPS (package ups.npk): power source, battery charge, runtime left, load,
  voltages; model and serial in the HW/SW inventory
- Metric graphs and Perf-O-Meters for file age, PoE, firewall, BGP, WiFi,
  WireGuard, NTP, IP pools, UPS and network interfaces

### Requirements

- CheckMK 2.4 or later
- MikroTik RouterOS 7.x or later (RouterOS API v2)

### Installation

Install the `.mkp` file via **Setup → Maintenance → Extension packages**
(commercial editions only) or on the command line as the site user:

```
mkp add mikrotik-<version>.mkp
mkp enable mikrotik <version>
cmk -R
```

`mkp add` only makes the package available, `mkp enable` activates it
(`mkp install` is deprecated). In a distributed setup the package reaches
the remote sites with the next activation of changes. See
[Checkmk extension packages (MKPs)](https://docs.checkmk.com/2.5.0/en/mkps.html#commandline).

After installation, configure the special agent under
**Setup → Agents → Other integrations → MikroTik RouterOS** and assign it
to your MikroTik hosts.

### Opt-in modules

The agent default "all" covers every module except WiFi, WireGuard, NTP
client, IP pools, UPS and network interfaces. Tick these in the special agent rule, activate the
changes and run a service discovery on the hosts.

### Migration from v3.x

Stored rules (special agent configuration and check parameters) are migrated
automatically when the MKP is installed - no manual reconfiguration is needed.

**Power services only**: the old single `Power Usage` service is incompatible
with the new per-PSU check introduced in v4.0.0. After installing the MKP,
run **Update service configuration** on any MikroTik host that had health
monitoring enabled. The old service will be replaced by `Power PSU1` /
`Power PSU2` (or however many PSUs the device reports).
