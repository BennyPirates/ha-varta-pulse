"""Pure decoding helpers for VARTA pulse public Modbus registers."""

from __future__ import annotations

from dataclasses import dataclass

from .const import STATE_NAMES, RegisterDefinition


@dataclass(frozen=True, slots=True)
class VartaValue:
    """Decoded value plus raw evidence from one read-only register."""

    value: int | float | str
    raw_value: int
    plausible: bool


def signed16(value: int) -> int:
    """Decode a two's-complement 16-bit Modbus register."""
    return value - 0x10000 if value >= 0x8000 else value


def decode_string(values: list[int]) -> str:
    """VARTA encodes one ASCII character in the low byte per register."""
    return "".join(chr(value & 0xFF) for value in values).rstrip("\x00 ")


def register_width(data_type: str) -> int:
    """Return the number of 16-bit registers required by a data type."""
    return 17 if data_type == "string17" else 10 if data_type == "string10" else 1


def decode(register: RegisterDefinition, values: list[int]) -> VartaValue:
    """Decode a public VARTA register without inferring undocumented data."""
    raw = values[0]
    if register.data_type.startswith("string"):
        value: int | float | str = decode_string(values)
    elif register.data_type == "int":
        value = signed16(raw)
    elif register.data_type == "state":
        value = STATE_NAMES.get(raw, f"Unknown ({raw})")
    elif register.data_type == "centihertz":
        value = round(raw / 100, 2)
    elif register.data_type == "capacity_10wh":
        value = raw * 10
    else:
        value = raw
    return VartaValue(
        value=value, raw_value=raw, plausible=is_plausible(register, value)
    )


def is_plausible(register: RegisterDefinition, value: int | float | str) -> bool:
    """Apply conservative bounds only where the public semantics are clear."""
    if register.data_type.startswith("string"):
        return bool(value) and isinstance(value, str) and value.isprintable()
    if register.key == "state":
        return isinstance(value, str) and not value.startswith("Unknown")
    if register.key == "state_of_charge":
        return isinstance(value, int | float) and 0 <= value <= 100
    if register.key == "grid_frequency":
        return isinstance(value, int | float) and 45 <= value <= 55
    if register.key == "installed_modules":
        return isinstance(value, int | float) and 1 <= value <= 12
    return True
