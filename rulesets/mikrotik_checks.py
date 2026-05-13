"""CheckMK check parameter rule specs for MikroTik checks.

Replaces the legacy wato/mikrotik.py using the cmk.rulesets.v1 API, which is
required for CheckMK 2.4+ (the legacy cmk.gui.plugins.wato API was removed in
2.5).

Each rule_spec_* variable is auto-discovered by CheckMK via entry_point_prefixes().
"""

# DefaultValue(False/True) are positional arguments required by CheckMK's
# form spec API — suppressing FBT003 (boolean positional value) project-wide.

from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    Integer,
    LevelDirection,
    List,
    SimpleLevels,
    String,
    TimeMagnitude,
    TimeSpan,
    migrate_to_integer_simple_levels,
    migrate_to_upper_integer_levels,
)
from cmk.rulesets.v1.rule_specs import (
    CheckParameters,
    HostAndItemCondition,
    HostCondition,
    Topic,
)

# ---------------------------------------------------------------------------
# Migration helpers — strip keys removed in v4.0.0
# ---------------------------------------------------------------------------

def _migrate_fan_params(value: object) -> dict[str, object]:
    """Remove 'output_metrics' stored by the legacy WATO fan rule."""
    if not isinstance(value, dict):
        return {}
    result = dict(value)
    result.pop("output_metrics", None)
    return result


def _migrate_power_params(value: object) -> dict[str, object]:
    """Remove 'psu_count' stored by the legacy WATO power rule.

    Power monitoring was redesigned in v4.0.0 to create one service per PSU,
    so the expected-PSU-count check no longer makes sense.
    """
    if not isinstance(value, dict):
        return {}
    result = dict(value)
    result.pop("psu_count", None)
    return result


# ---------------------------------------------------------------------------
# Fan speed
# ---------------------------------------------------------------------------

rule_spec_mikrotik_fan = CheckParameters(
    name="mikrotik_fan",
    title=Title("MikroTik Fan"),
    topic=Topic.ENVIRONMENTAL,
    # One service per fan — the item is the fan name reported by the agent.
    condition=HostAndItemCondition(item_title=Title("Fan name")),
    parameter_form=lambda: Dictionary(
        migrate=_migrate_fan_params,
        help_text=Help("Activate special agent mikrotik to use this."),
        elements={
            "lower": DictElement(
                required=False,
                parameter_form=SimpleLevels(
                    title=Title("Lower fan speed thresholds"),
                    level_direction=LevelDirection.LOWER,
                    form_spec_template=Integer(unit_symbol="rpm"),
                    prefill_fixed_levels=DefaultValue((2000, 1000)),
                    # Converts data stored by the legacy Tuple valuespec so
                    # existing rules survive the upgrade to 2.5.
                    migrate=migrate_to_integer_simple_levels,
                ),
            ),
        },
    ),
)

# ---------------------------------------------------------------------------
# RouterOS board / version
# ---------------------------------------------------------------------------

rule_spec_mikrotik_board = CheckParameters(
    name="mikrotik_board",
    title=Title("MikroTik RouterOS"),
    topic=Topic.NETWORKING,
    # Single service per host — no item.
    condition=HostCondition(),
    parameter_form=lambda: Dictionary(
        help_text=Help("Activate special agent mikrotik to use this."),
        elements={
            "min_version": DictElement(
                required=False,
                parameter_form=String(
                    title=Title("Minimum version"),
                    help_text=Help(
                        "Check goes WARN if the installed RouterOS version is "
                        "lower than this value. Format: Major.Minor or "
                        "Major.Minor.Patch (e.g. 7.14).",
                    ),
                    prefill=DefaultValue("0.0"),
                ),
            ),
        },
    ),
)

# ---------------------------------------------------------------------------
# File age
# ---------------------------------------------------------------------------

rule_spec_mikrotik_file = CheckParameters(
    name="mikrotik_file",
    title=Title("MikroTik File Age"),
    topic=Topic.NETWORKING,
    # One service per monitored file — the item is the file name.
    condition=HostAndItemCondition(item_title=Title("File name")),
    parameter_form=lambda: Dictionary(
        help_text=Help("Activate special agent mikrotik to use this."),
        elements={
            "file_age": DictElement(
                required=False,
                parameter_form=SimpleLevels(
                    title=Title("Maximum age of file"),
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=TimeSpan(
                        displayed_magnitudes=[
                            TimeMagnitude.DAY,
                            TimeMagnitude.HOUR,
                            TimeMagnitude.MINUTE,
                        ],
                    ),
                    # Defaults: warn after 25 h (90000 s), crit after 49 h (176400 s).
                    prefill_fixed_levels=DefaultValue((90000.0, 176400.0)),
                    # Converts data stored by the legacy Age Tuple valuespec.
                    migrate=migrate_to_upper_integer_levels,
                ),
            ),
            "pattern": DictElement(
                required=False,
                parameter_form=String(
                    title=Title("Time pattern for creation-time field"),
                    help_text=Help(
                        "strptime format code matching the creation-time string "
                        "returned by the API. "
                        "RouterOS v7: %%b/%%d/%%Y %%H:%%M:%%S  "
                        "RouterOS v8: %%Y-%%m-%%d %%H:%%M:%%S  "
                        "Leave empty for autodetection.",
                    ),
                    prefill=DefaultValue(""),
                ),
            ),
        },
    ),
)

# ---------------------------------------------------------------------------
# Power supply metrics (per PSU)
# ---------------------------------------------------------------------------

rule_spec_mikrotik_power = CheckParameters(
    name="mikrotik_power",
    title=Title("MikroTik Power Supply Metrics"),
    topic=Topic.ENVIRONMENTAL,
    # One service per PSU — the item is the PSU name (e.g. PSU1, PSU2).
    condition=HostAndItemCondition(item_title=Title("PSU name")),
    parameter_form=lambda: Dictionary(
        migrate=_migrate_power_params,
        help_text=Help("Activate special agent mikrotik to use this."),
        elements={
            "crit_voltage": DictElement(
                required=False,
                parameter_form=Integer(
                    title=Title("Critical voltage threshold"),
                    help_text=Help(
                        "Go CRIT if measured voltage drops below this value. "
                        "Typical MikroTik supply voltages are 12V, 24V, or 48V.",
                    ),
                    unit_symbol="V",
                    prefill=DefaultValue(10),
                ),
            ),
        },
    ),
)

# ---------------------------------------------------------------------------
# PSU state (presence / ok / fail)
# ---------------------------------------------------------------------------

rule_spec_mikrotik_psu = CheckParameters(
    name="mikrotik_psu",
    title=Title("MikroTik PSU State"),
    topic=Topic.ENVIRONMENTAL,
    # One service per PSU — the item is the PSU name reported by the agent.
    condition=HostAndItemCondition(item_title=Title("PSU name")),
    parameter_form=lambda: Dictionary(
        help_text=Help("Activate special agent mikrotik to use this."),
        elements={
            "ok_states": DictElement(
                required=False,
                parameter_form=List(
                    title=Title("States considered OK"),
                    help_text=Help(
                        "RouterOS reports PSU state as a string such as 'ok'. "
                        "Any state not in this list results in CRIT.",
                    ),
                    element_template=String(),
                ),
            ),
        },
    ),
)

# ---------------------------------------------------------------------------
# IPsec tunnels
# ---------------------------------------------------------------------------

rule_spec_mikrotik_ipsec = CheckParameters(
    name="mikrotik_ipsec",
    title=Title("MikroTik IPsec"),
    topic=Topic.NETWORKING,
    # One service per IPsec peer — the item is the tunnel identifier.
    condition=HostAndItemCondition(item_title=Title("IPsec tunnel")),
    parameter_form=lambda: Dictionary(
        help_text=Help("Activate special agent mikrotik to use this."),
        elements={
            "ok_states": DictElement(
                required=False,
                parameter_form=List(
                    title=Title("Security Association states considered OK"),
                    help_text=Help(
                        "Any SA state not in this list will result in a WARN. "
                        "RouterOS reports states such as: mature, dying, dead, larval.",
                    ),
                    element_template=String(),
                ),
            ),
        },
    ),
)
