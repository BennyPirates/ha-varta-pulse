"""Constants and public VARTA pulse Modbus register definitions."""

from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "varta_pulse"
DEFAULT_NAME = "VARTA pulse"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 255
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 5.0
MIN_REQUEST_INTERVAL = 1.05
PLATFORMS = ["sensor"]
CONF_UNIT_ID = "unit_id"


@dataclass(frozen=True, slots=True)
class RegisterDefinition:
    """One publicly documented, read-only VARTA Modbus data point."""

    key: str
    address: int
    name: str
    data_type: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = "measurement"
    icon: str | None = None


# All addresses are holding registers and are read using Modbus FC03 only.
# Source: VARTA Modbus TCP register table, version 13.1.
REGISTERS: tuple[RegisterDefinition, ...] = (
    RegisterDefinition("ems_firmware", 1000, "EMS firmware", "string17"),
    RegisterDefinition("ens_firmware", 1017, "ENS firmware", "string17"),
    RegisterDefinition(
        "inverter_firmware", 1034, "Internal inverter firmware", "string17"
    ),
    RegisterDefinition("modbus_table_version", 1051, "Modbus table version", "uint"),
    RegisterDefinition("serial_number", 1054, "Serial number", "string10"),
    RegisterDefinition(
        "installed_modules",
        1064,
        "Installed battery modules",
        "uint",
        icon="mdi:battery",
    ),
    RegisterDefinition("state", 1065, "State", "state", icon="mdi:battery-sync"),
    RegisterDefinition(
        "battery_power",
        1066,
        "Battery power",
        "int",
        "W",
        "power",
        "measurement",
    ),
    RegisterDefinition(
        "apparent_battery_power",
        1067,
        "Apparent battery power",
        "int",
        "VA",
        "apparent_power",
        "measurement",
    ),
    RegisterDefinition(
        "state_of_charge",
        1068,
        "State of charge",
        "uint",
        "%",
        "battery",
        "measurement",
    ),
    RegisterDefinition(
        "installed_capacity",
        1071,
        "Installed capacity",
        "capacity_10wh",
        "Wh",
        "energy_storage",
        "measurement",
    ),
    RegisterDefinition("grid_power", 1078, "Grid power", "int", "W", "power"),
    RegisterDefinition(
        "grid_frequency", 1082, "Grid frequency", "centihertz", "Hz", "frequency"
    ),
    RegisterDefinition(
        "available_charging_power",
        1083,
        "Available charging power",
        "uint",
        "W",
        "power",
    ),
    RegisterDefinition(
        "available_discharging_power",
        1084,
        "Available discharging power",
        "uint",
        "W",
        "power",
    ),
    RegisterDefinition(
        "usable_energy_for_charging",
        1085,
        "Usable energy for charging",
        "uint",
        "Wh",
        "energy_storage",
    ),
    RegisterDefinition(
        "usable_energy_for_discharging",
        1086,
        "Usable energy for discharging",
        "uint",
        "Wh",
        "energy_storage",
    ),
    RegisterDefinition(
        "reactive_power", 1087, "Reactive power", "int", "var", "reactive_power"
    ),
    RegisterDefinition(
        "pv_sensor_power", 1102, "PV sensor power", "uint", "W", "power"
    ),
)

STATE_NAMES = {
    0: "Busy",
    1: "Ready",
    2: "Charging",
    3: "Discharging",
    4: "Standby",
    5: "Error",
    6: "Passive service",
    7: "Islanding",
}

# Consecutive documented blocks. A block is read in one FC03 request to avoid
# needless traffic, with a hard ≥1.05 s gap between all requests.
READ_BLOCKS: tuple[tuple[int, int], ...] = ((1000, 88), (1102, 1))
