"""CheckMK rule spec for the MikroTik RouterOS special agent.

Replaces the legacy wato/mikrotik_register.py using the cmk.rulesets.v1 API,
which is required for CheckMK 2.4+ (the legacy cmk.gui.plugins.wato API was
removed in 2.5).
"""

# DefaultValue(False/True) are positional arguments required by CheckMK's
# form spec API — suppressing FBT003 (boolean positional value) project-wide.
# ruff: noqa: FBT003

from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictElement,
    Dictionary,
    Integer,
    Password,
    SingleChoice,
    SingleChoiceElement,
    String,
    migrate_to_password,
    validators,
)
from cmk.rulesets.v1.rule_specs import SpecialAgent, Topic

# Keys that the legacy WATO form stored with hyphens; the new form uses underscores.
_KEY_RENAMES = {"no-ssl": "no_ssl", "skip-cert-check": "skip_cert_check"}


def _migrate_password(value: object) -> object:
    """Extend migrate_to_password to handle plain string passwords from legacy WATO.

    The old WATO Password valuespec stored explicit passwords as bare strings.
    migrate_to_password only accepts structured tuples/dicts, so we wrap the
    string in the ("password", value) tuple it expects before delegating.
    """
    if isinstance(value, str):
        return migrate_to_password(("password", value))
    return migrate_to_password(value)


def _migrate_params(value: object) -> dict[str, object]:
    """Normalise legacy WATO rule dicts for the new form spec.

    Handles three classes of old data:
    - Hyphenated top-level keys (no-ssl → no_ssl, etc.)
    - Separate no_ssl / skip_cert_check booleans → unified ssl_mode choice
    - infos stored as a list of module names → dict with True values
    """
    if not isinstance(value, dict):
        return {}
    # Rename hyphenated keys first.
    result = {_KEY_RENAMES.get(k, k): v for k, v in value.items()}

    # Fold the two old boolean SSL flags into a single ssl_mode choice.
    if "ssl_mode" not in result:
        no_ssl = bool(result.pop("no_ssl", False))
        skip_cert_check = bool(result.pop("skip_cert_check", False))
        if no_ssl:
            result["ssl_mode"] = "no_ssl"
        elif skip_cert_check:
            result["ssl_mode"] = "ssl_skip"
        else:
            result["ssl_mode"] = "ssl"
    else:
        result.pop("no_ssl", None)
        result.pop("skip_cert_check", None)

    # Convert infos from legacy list-of-names to dict.
    if isinstance(result.get("infos"), list):
        result["infos"] = {k: True for k in result["infos"] if isinstance(k, str)}
    elif isinstance(result.get("infos"), dict):
        infos = dict(result["infos"])
        if isinstance(infos.get("firewall"), dict):
            fw = dict(infos["firewall"])
            if "show-disabled" in fw:
                fw["show_disabled"] = fw.pop("show-disabled")
            infos["firewall"] = fw
        result["infos"] = infos

    return result


def _parameter_form() -> Dictionary:
    """Build the configuration form shown in CheckMK's Setup UI for this agent."""
    return Dictionary(
        migrate=_migrate_params,
        help_text=Help(
            "Activates an agent that collects data from a MikroTik RouterOS "
            "device via the RouterOS API (port 8729/SSL) or RESTful API.",
        ),
        elements={
            # ------------------------------------------------------------------
            # Credentials
            # ------------------------------------------------------------------
            "user": DictElement(
                required=True,
                parameter_form=String(
                    title=Title("Username"),
                    custom_validate=(validators.LengthInRange(min_value=1),),
                ),
            ),
            "password": DictElement(
                required=True,
                parameter_form=Password(
                    title=Title("Password"),
                    migrate=_migrate_password,
                ),
            ),
            # ------------------------------------------------------------------
            # Connection options
            # ------------------------------------------------------------------
            "rest": DictElement(
                required=True,
                parameter_form=BooleanChoice(
                    title=Title("Use RESTful API instead of RouterOS API"),
                    prefill=DefaultValue(False),
                ),
            ),
            "ssl_mode": DictElement(
                required=True,
                parameter_form=SingleChoice(
                    title=Title("Connection security"),
                    prefill=DefaultValue("ssl"),
                    elements=[
                        SingleChoiceElement(
                            name="ssl",
                            title=Title("SSL — verify server certificate"),
                        ),
                        SingleChoiceElement(
                            name="ssl_skip",
                            title=Title("SSL — do not validate certificate"),
                        ),
                        SingleChoiceElement(
                            name="no_ssl",
                            title=Title("Plain TCP — no SSL"),
                        ),
                    ],
                ),
            ),
            "connect": DictElement(
                required=True,
                parameter_form=Integer(
                    title=Title("TCP port"),
                    help_text=Help(
                        "Port to connect to. Default is 8729 (SSL) or 8728 (no SSL).",
                    ),
                    prefill=DefaultValue(8728),
                    custom_validate=(
                        validators.NumberInRange(min_value=1, max_value=65535),
                    ),
                ),
            ),
            # ------------------------------------------------------------------
            # Modules — each bool maps to a --modules argument in the agent
            # ------------------------------------------------------------------
            "infos": DictElement(
                required=False,
                parameter_form=Dictionary(
                    title=Title("Retrieve information about"),
                    elements={
                        "bgp": DictElement(
                            required=True,
                            parameter_form=BooleanChoice(
                                title=Title("BGP Sessions"),
                                prefill=DefaultValue(False),
                            ),
                        ),
                        "ospf": DictElement(
                            required=True,
                            parameter_form=BooleanChoice(
                                title=Title("OSPF Neighbors"),
                                prefill=DefaultValue(False),
                            ),
                        ),
                        "vrrp": DictElement(
                            required=True,
                            parameter_form=BooleanChoice(
                                title=Title("VRRP Info"),
                                prefill=DefaultValue(False),
                            ),
                        ),
                        "health": DictElement(
                            required=True,
                            parameter_form=BooleanChoice(
                                title=Title("RouterOS Health"),
                                prefill=DefaultValue(False),
                            ),
                        ),
                        "board": DictElement(
                            required=True,
                            parameter_form=BooleanChoice(
                                title=Title("RouterOS Board Info"),
                                prefill=DefaultValue(False),
                            ),
                        ),
                        "ipsec": DictElement(
                            required=True,
                            parameter_form=BooleanChoice(
                                title=Title("IPsec"),
                                prefill=DefaultValue(False),
                            ),
                        ),
                        "file": DictElement(
                            required=True,
                            parameter_form=BooleanChoice(
                                title=Title("Local File Age"),
                                prefill=DefaultValue(False),
                            ),
                        ),
                        "license": DictElement(
                            required=True,
                            parameter_form=BooleanChoice(
                                title=Title("License Key (CHR)"),
                                prefill=DefaultValue(False),
                            ),
                        ),
                        # Firewall is a nested dict because it has a sub-option
                        # (show-disabled) beyond a simple enabled/disabled flag.
                        "firewall": DictElement(
                            required=False,
                            parameter_form=Dictionary(
                                title=Title("Firewall Rules"),
                                elements={
                                    "enabled": DictElement(
                                        required=False,
                                        parameter_form=BooleanChoice(
                                            title=Title("Enable firewall monitoring"),
                                            prefill=DefaultValue(False),
                                        ),
                                    ),
                                    "show_disabled": DictElement(
                                        required=False,
                                        parameter_form=BooleanChoice(
                                            title=Title("Show disabled rules"),
                                            prefill=DefaultValue(False),
                                        ),
                                    ),
                                },
                            ),
                        ),
                    },
                ),
            ),
        },
    )


# Prefix rule_spec_ is required so CheckMK auto-discovers this via
# entry_point_prefixes() at package load time.
rule_spec_special_agent_mikrotik = SpecialAgent(
    name="mikrotik",
    title=Title("MikroTik RouterOS"),
    topic=Topic.NETWORKING,
    parameter_form=_parameter_form,
)
