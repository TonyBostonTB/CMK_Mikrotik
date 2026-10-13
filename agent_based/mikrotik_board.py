"""CheckMK agent-based check plugin for MikroTik board monitoring."""


from cmk.agent_based.v2 import (
    AgentSection,
    Attributes,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    InventoryPlugin,
    InventoryResult,
    Result,
    Service,
    State,
    StringTable,
)
from packaging import version  # Sostituisce distutils.version che è deprecato


def parse_mikrotik_board(string_table: StringTable) -> dict[str, str]:
    """Parse MikroTik board information from agent output.

    Keys prefixed with ``rb-`` come from /system/routerboard (agent >= 4.1.0),
    the others from /system/resource.
    """
    relevant_keys = {
        "board-name",
        "version",
        "rb-routerboard",
        "rb-model",
        "rb-serial-number",
        "rb-current-firmware",
        "rb-upgrade-firmware",
    }
    return {
        line[0]: " ".join(line[1:])
        for line in string_table
        if line and line[0] in relevant_keys
    }

def discover_mikrotik_board(section: dict[str, str]) -> DiscoveryResult:
    """Discover service if version information is present."""
    if section.get("version"):
        yield Service()

def check_mikrotik_board(
    params: dict,
    section: dict[str, str],
) -> CheckResult:
    """Check MikroTik board information and version compliance."""
    if not section:
        yield Result(state=State.UNKNOWN, summary="No board information found")
        return

    # Check version compliance if required
    min_version = params.get("min_version", "0.0")
    current_state = State.OK
    summary_parts = []

    if "board-name" in section:
        summary_parts.append(f"Model: {section['board-name']}")

    if "version" in section:
        current_version = section["version"].split(" ")[0]
        summary_parts.append(f"Version: {section['version']}")

        if min_version != "0.0":
            try:
                if version.parse(current_version) < version.parse(min_version):
                    current_state = State.WARN
                    summary_parts.append(
                        f"(below minimum required: {min_version})",
                    )
            except version.InvalidVersion:
                summary_parts.append("(version parsing failed)")
                current_state = State.WARN

    if section.get("rb-serial-number"):
        summary_parts.append(f"Serial: {section['rb-serial-number']}")

    yield Result(
        state=current_state,
        summary=", ".join(summary_parts),
    )

    # RouterBOOT firmware. MikroTik documents: "If upgrade-firmware shows a
    # higher version than current-firmware, a newer version is ready to be
    # applied" (/system/routerboard upgrade, then /system/reboot).
    current_fw = section.get("rb-current-firmware")
    upgrade_fw = section.get("rb-upgrade-firmware")
    if not current_fw:
        return
    if not upgrade_fw:
        yield Result(state=State.OK, summary=f"Firmware: {current_fw}")
        return
    try:
        pending = version.parse(current_fw) < version.parse(upgrade_fw)
    except version.InvalidVersion:
        yield Result(
            state=State.OK,
            summary=f"Firmware: {current_fw} (upgrade firmware {upgrade_fw} not comparable)",
        )
        return
    if pending:
        yield Result(
            state=State(params.get("firmware_upgrade_pending", 1)),
            summary=(
                f"Firmware: {current_fw}, upgrade to {upgrade_fw} pending "
                "(/system/routerboard upgrade + reboot)"
            ),
        )
    else:
        yield Result(state=State.OK, summary=f"Firmware: {current_fw}")

def inventory_mikrotik_board(section: dict[str, str]) -> InventoryResult:
    """HW/SW inventory: model, serial, RouterOS version, RouterBOOT firmware."""
    hardware = {"manufacturer": "MikroTik"}
    model = section.get("rb-model") or section.get("board-name")
    if model:
        hardware["model"] = model
    if section.get("rb-serial-number"):
        hardware["serial"] = section["rb-serial-number"]
    yield Attributes(path=["hardware", "system"], inventory_attributes=hardware)

    if section.get("version"):
        yield Attributes(
            path=["software", "os"],
            inventory_attributes={
                "vendor": "MikroTik",
                "name": "RouterOS",
                "version": section["version"].split(" ")[0],
            },
        )

    if section.get("rb-current-firmware"):
        yield Attributes(
            path=["software", "firmware"],
            inventory_attributes={
                "vendor": "MikroTik",
                "version": section["rb-current-firmware"],
            },
        )

# Register agent section
agent_section_mikrotik_board = AgentSection(
    name="mikrotik_board",
    parse_function=parse_mikrotik_board,
)

# Register check plugin
check_plugin_mikrotik_board = CheckPlugin(
    name="mikrotik_board",
    service_name="RouterOS Info",
    discovery_function=discover_mikrotik_board,
    check_function=check_mikrotik_board,
    check_default_parameters={"min_version": "0.0", "firmware_upgrade_pending": 1},
    check_ruleset_name="mikrotik_board",
)

# Register inventory plugin (needs the "Do HW/SW Inventory" rule on the host)
inventory_plugin_mikrotik_board = InventoryPlugin(
    name="mikrotik_board",
    inventory_function=inventory_mikrotik_board,
)
