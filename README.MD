## MikroTik RouterOS Plugin for CheckMK

This plugin provides comprehensive monitoring of MikroTik RouterOS devices
using the RouterOS API (v2, for RouterOS 7.x+) or the RESTful API.

It includes checks for:

- BGP and OSPF neighbors
- VRRP status
- PSU, fan, and temperature sensors
- IPsec tunnels
- License expiration (CHR) and file age
- Firewall rules based on comment filters
- System health and crashfile detection

### Requirements

- CheckMK 2.4 or later
- MikroTik RouterOS 7.x or later (RouterOS API v2)

### Installation

Install the `.mkp` file via **Setup → Extension packages** or via the CLI:

```
mkp install mikrotik-4.0.0.mkp
```

After installation, configure the special agent under
**Setup → Other integrations → MikroTik RouterOS** and assign it to your
MikroTik hosts.

### Migration from v3.x

Stored rules (special agent configuration and check parameters) are migrated
automatically when the MKP is installed — no manual reconfiguration is needed.

**Power services only**: the old single `Power Usage` service is incompatible
with the new per-PSU check introduced in v4.0.0. After installing the MKP,
run **Update service configuration** on any MikroTik host that had health
monitoring enabled. The old service will be replaced by `Power PSU1` /
`Power PSU2` (or however many PSUs the device reports).

### Reporting issues

Please open an issue on the GitHub repository:
https://github.com/devilofhell87/CMK_Mikrotik/
