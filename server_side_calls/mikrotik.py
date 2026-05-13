"""CheckMK server-side call definition for the MikroTik special agent.

Translates the rule parameters (set via the Setup UI) into the CLI arguments
passed to special_agents/mikrotik.py when CheckMK runs a host check.

Passwords are handled via CheckMK's Secret type so they are never written
to disk or passed through environment variables in plaintext.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from cmk.server_side_calls.v1 import (
    HostConfig,
    Secret,
    SpecialAgentCommand,
    SpecialAgentConfig,
)

# ---------------------------------------------------------------------------
# Parameter models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _FirewallConfig:
    """Parsed firewall sub-section of the agent rule."""

    enabled: bool = False
    show_disabled: bool = False


def _parse_firewall(raw: dict[str, Any]) -> _FirewallConfig:
    """Parse the firewall dict from the form, normalising hyphenated keys.

    The form spec now uses "show_disabled" (underscore); legacy WATO rules
    stored "show-disabled" (hyphen). Both are accepted here.
    """
    return _FirewallConfig(
        enabled=bool(raw.get("enabled", False)),
        show_disabled=bool(
            raw.get("show-disabled", raw.get("show_disabled", False)),
        ),
    )


@dataclass(frozen=True)
class _Params:
    """Fully-parsed parameters passed to _mikrotik_commands.

    The infos booleans are flattened out of the nested "infos" dict at parse
    time to make the command-building logic below straightforward.
    """

    user: str
    password: Secret
    rest: bool = False
    ssl_mode: str = "ssl"  # "ssl" | "ssl_skip" | "no_ssl"
    connect: int = 8729
    # Module flags (correspond 1-to-1 with --modules arguments)
    bgp: bool = False
    ospf: bool = False
    vrrp: bool = False
    health: bool = False
    board: bool = False
    ipsec: bool = False
    file: bool = False
    license: bool = False
    firewall: _FirewallConfig = field(default_factory=_FirewallConfig)

    @classmethod
    def from_raw(cls, obj: Any) -> "_Params":  # noqa: ANN401
        """Parse the raw dict produced by CheckMK's form spec machinery.

        ANN401 is suppressed because CheckMK's SpecialAgentConfig types
        parameter_parser as Callable[[object], T]; we accept Any here to avoid
        a runtime isinstance guard that would add no real safety.
        """
        infos: dict[str, Any] = obj.get("infos", {})
        fw_raw: dict[str, Any] = infos.get("firewall", {})

        # Resolve ssl_mode: new rules store a string; legacy rules stored
        # separate no_ssl / skip_cert_check booleans (possibly hyphenated).
        ssl_mode: str = obj.get("ssl_mode", "")
        if not ssl_mode:
            if obj.get("no-ssl", obj.get("no_ssl", False)):
                ssl_mode = "no_ssl"
            elif obj.get("skip-cert-check", obj.get("skip_cert_check", False)):
                ssl_mode = "ssl_skip"
            else:
                ssl_mode = "ssl"

        return cls(
            user=obj["user"],
            password=obj["password"],
            rest=bool(obj.get("rest", False)),
            ssl_mode=ssl_mode,
            connect=int(obj.get("connect", 8729)),
            bgp=bool(infos.get("bgp", False)),
            ospf=bool(infos.get("ospf", False)),
            vrrp=bool(infos.get("vrrp", False)),
            health=bool(infos.get("health", False)),
            board=bool(infos.get("board", False)),
            ipsec=bool(infos.get("ipsec", False)),
            file=bool(infos.get("file", False)),
            license=bool(infos.get("license", False)),
            firewall=_parse_firewall(fw_raw) if fw_raw else _FirewallConfig(),
        )


# ---------------------------------------------------------------------------
# Command builder
# ---------------------------------------------------------------------------

# Modules that map directly to a single boolean flag in the params model.
_SIMPLE_MODULES = ("bgp", "ospf", "vrrp", "health", "board", "ipsec", "file", "license")


def _mikrotik_commands(
    params: _Params,
    host_config: HostConfig,
) -> Iterable[SpecialAgentCommand]:
    """Yield the SpecialAgentCommand that CheckMK will execute for this host."""
    args: list[str | Secret] = [
        "--user", params.user,
        # Secret is expanded to the actual password by SpecialAgentCommand
        # without it ever appearing in plain text in the process arguments.
        "--pass", params.password,
    ]

    if params.ssl_mode == "no_ssl":
        args.append("--no-ssl")
    elif params.ssl_mode == "ssl_skip":
        args.append("--skip-cert-check")
    if params.rest:
        args.append("--rest")

    args += ["--connect", str(params.connect)]

    # Build the comma-separated module list from the enabled flags.
    modules: list[str] = [
        name for name in _SIMPLE_MODULES if getattr(params, name)
    ]
    if params.firewall.enabled:
        # The agent accepts "firewall:show-disabled" as a compound token.
        modules.append(
            "firewall:show-disabled" if params.firewall.show_disabled else "firewall",
        )

    if modules:
        args += ["--modules", ",".join(modules)]

    # Prefer IPv4; fall back to IPv6, then hostname.
    if host_config.ipv4_config and host_config.ipv4_config.address:
        ipaddress: str = host_config.ipv4_config.address
    elif host_config.ipv6_config and host_config.ipv6_config.address:
        ipaddress = host_config.ipv6_config.address
    else:
        ipaddress = host_config.name

    args.append(ipaddress)

    yield SpecialAgentCommand(command_arguments=args)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

special_agent_mikrotik = SpecialAgentConfig(
    name="mikrotik",
    # from_raw is the parameter_parser: receives the raw form dict and returns
    # a typed _Params instance that _mikrotik_commands can use safely.
    parameter_parser=_Params.from_raw,
    commands_function=_mikrotik_commands,
)
