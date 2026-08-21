#!/usr/bin/env python3
"""Strictly read-only VARTA pulse Modbus TCP diagnostic probe.

Only Modbus function code 03 is used.  The implementation deliberately has
no write methods and is intended to document the public VARTA Modbus map plus
a small, opt-in candidate range for further read-only investigation.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

DOCUMENTATION_URL = (
    "https://community-openhab-org.s3.dualstack.eu-central-1.amazonaws.com/"
    "original/3X/b/9/b90607e891488d8ab920361161e73f454bc808a1.pdf"
)
DEFAULT_UNIT_ID = 255
MIN_DELAY_SECONDS = 1.05


@dataclass(frozen=True)
class Register:
    address: int
    name: str
    data_type: str
    unit: str = ""
    documented: bool = True


@dataclass
class Result:
    address: int
    pdu_address: int
    name: str
    documented: bool
    raw_value: int | None
    raw_hex: str | None
    data_type: str
    decoded_value: int | float | str | None
    unit: str
    plausibility: str
    error: str | None = None


REGISTERS = [
    Register(1000, "EMS firmware", "string17"),
    Register(1017, "ENS firmware", "string17"),
    Register(1034, "Internal inverter firmware", "string17"),
    Register(1051, "Modbus table version", "uint16"),
    Register(1052, "Timestamp low word", "uint16"),
    Register(1053, "Timestamp high word", "uint16"),
    Register(1054, "Storage serial number", "string10"),
    Register(1064, "Installed battery modules", "uint16"),
    Register(1065, "Storage state", "state"),
    Register(1066, "Active battery power", "int16", "W"),
    Register(1067, "Apparent battery power", "int16", "VA"),
    Register(1068, "State of charge", "uint16", "%"),
    Register(1069, "Energy charged low word", "uint16", "Wh"),
    Register(1070, "Energy charged high word", "uint16", "Wh"),
    Register(1071, "Installed capacity", "capacity_10wh", "Wh"),
    Register(1078, "Grid power", "int16", "W"),
    Register(1082, "Grid frequency", "centihertz", "Hz"),
    Register(1083, "Available AC charging power", "uint16", "W"),
    Register(1084, "Available AC discharging power", "uint16", "W"),
    Register(1085, "Usable energy for charging", "uint16", "Wh"),
    Register(1086, "Usable energy for discharging", "uint16", "Wh"),
    Register(1087, "Reactive power", "int16", "var"),
    Register(1102, "PV sensor power", "uint16", "W"),
    Register(2066, "Active power scale factor", "int16"),
    Register(2067, "Apparent power scale factor", "int16"),
    Register(2069, "Energy counter scale factor", "int16"),
    Register(2071, "Capacity scale factor", "int16"),
    Register(2078, "Grid power scale factor", "int16"),
]


def candidate_registers() -> list[Register]:
    """Return tightly bounded, undocumented neighbours of public VARTA blocks.

    These addresses are retained as raw candidates only. A response does not
    establish a semantic meaning or write capability.
    """
    documented_addresses = {register.address for register in REGISTERS}
    ranges = ((1088, 1101), (1103, 1115), (2058, 2085))
    return [
        Register(
            address=address,
            name="Undocumented candidate register",
            data_type="raw_uint16",
            documented=False,
        )
        for start, end in ranges
        for address in range(start, end + 1)
        if address not in documented_addresses
    ]


STATE_NAMES = {
    0: "busy",
    1: "ready",
    2: "charging",
    3: "discharging",
    4: "standby",
    5: "error",
    6: "passive_service",
    7: "islanding",
}


def signed16(value: int) -> int:
    """Decode one two's-complement Modbus register."""
    return value - 0x10000 if value >= 0x8000 else value


def decode_string(values: list[int]) -> str:
    """VARTA stores one ASCII character in each 16-bit register."""
    return "".join(chr(value & 0xFF) for value in values).rstrip("\x00 ")


def register_count(register: Register) -> int:
    return (
        17
        if register.data_type == "string17"
        else 10
        if register.data_type == "string10"
        else 1
    )


def decode(register: Register, values: list[int]) -> int | float | str:
    raw = values[0]
    if register.data_type.startswith("string"):
        return decode_string(values)
    if register.data_type == "int16":
        return signed16(raw)
    if register.data_type == "state":
        return STATE_NAMES.get(raw, f"unknown_state_{raw}")
    if register.data_type == "centihertz":
        return round(raw / 100, 2)
    if register.data_type == "capacity_10wh":
        return raw * 10
    return raw


def plausible(register: Register, value: int | float | str) -> bool:
    if register.data_type.startswith("string"):
        return bool(value) and all(character.isprintable() for character in value)
    if register.data_type == "state":
        return isinstance(value, str) and not value.startswith("unknown_state_")
    if register.address == 1068:
        return isinstance(value, int | float) and 0 <= value <= 100
    if register.address == 1064:
        return isinstance(value, int | float) and 1 <= value <= 12
    if register.address in {1082}:
        return isinstance(value, int | float) and 45 <= value <= 55
    return True


class ReadOnlyVartaClient:
    """Modbus TCP client exposing FC03 reads only."""

    def __init__(
        self, host: str, port: int, unit_id: int, timeout: float, delay: float
    ) -> None:
        self._client = ModbusTcpClient(host, port=port, timeout=timeout, retries=1)
        self._unit_id = unit_id
        self._delay = max(delay, MIN_DELAY_SECONDS)

    def connect(self) -> bool:
        return self._client.connect()

    def close(self) -> None:
        self._client.close()

    def read_holding(self, pdu_address: int, count: int) -> list[int]:
        """Read holding registers through FC03; no write operation exists here."""
        response = self._client.read_holding_registers(
            pdu_address, count=count, device_id=self._unit_id
        )
        time.sleep(self._delay)
        if response.isError():
            raise ModbusException(str(response))
        registers = getattr(response, "registers", None)
        if not registers or len(registers) != count:
            raise ModbusException("response has an unexpected register count")
        return [int(value) for value in registers]


def choose_offset(client: ReadOnlyVartaClient) -> tuple[int, list[str]]:
    """Determine document-address to PDU-address offset without writes."""
    scores: dict[int, int] = {-1: 0, 0: 0}
    notes: list[str] = []
    probes = [
        next(register for register in REGISTERS if register.address == address)
        for address in (1000, 1065, 1068)
    ]
    for offset in scores:
        for register in probes:
            try:
                values = client.read_holding(
                    register.address + offset, register_count(register)
                )
                value = decode(register, values)
                ok = plausible(register, value)
                scores[offset] += 3 if ok else -2
                notes.append(
                    f"offset {offset:+}: {register.address} = {value!r} "
                    f"({'plausible' if ok else 'implausible'})"
                )
            except ModbusException as exc:
                scores[offset] -= 3
                notes.append(f"offset {offset:+}: {register.address} error: {exc}")
    offset = max(scores, key=scores.get)
    notes.append(f"selected offset {offset:+} (scores: {scores})")
    return offset, notes


def probe_register(
    client: ReadOnlyVartaClient, register: Register, offset: int
) -> Result:
    pdu_address = register.address + offset
    try:
        values = client.read_holding(pdu_address, register_count(register))
        value = decode(register, values)
        return Result(
            address=register.address,
            pdu_address=pdu_address,
            name=register.name,
            documented=register.documented,
            raw_value=values[0],
            raw_hex=" ".join(f"0x{value:04X}" for value in values),
            data_type=register.data_type,
            decoded_value=value,
            unit=register.unit,
            plausibility="plausible" if plausible(register, value) else "implausible",
        )
    except ModbusException as exc:
        return Result(
            address=register.address,
            pdu_address=pdu_address,
            name=register.name,
            documented=register.documented,
            raw_value=None,
            raw_hex=None,
            data_type=register.data_type,
            decoded_value=None,
            unit=register.unit,
            plausibility="error",
            error=str(exc),
        )


def write_results(
    results: list[Result], output_dir: Path, stamp: str
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"varta_pulse_probe_{stamp}.json"
    csv_path = output_dir / f"varta_pulse_probe_{stamp}.csv"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "documentation": DOCUMENTATION_URL,
        "safety": "FC03 reads only; no write functions are implemented or invoked.",
        "results": [asdict(result) for result in results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(results[0])))
        writer.writeheader()
        writer.writerows(asdict(result) for result in results)
    return json_path, csv_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="VARTA storage IP address or hostname")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--unit-id", type=int, default=DEFAULT_UNIT_ID)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--delay", type=float, default=MIN_DELAY_SECONDS)
    parser.add_argument("--output-dir", type=Path, default=Path("results/varta"))
    parser.add_argument(
        "--candidate-scan",
        action="store_true",
        help="Read only small, undocumented ranges near public VARTA registers.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = ReadOnlyVartaClient(
        args.host, args.port, args.unit_id, args.timeout, args.delay
    )
    if not client.connect():
        print(f"Unable to connect to {args.host}:{args.port}", file=sys.stderr)
        return 2
    try:
        offset, notes = choose_offset(client)
        for note in notes:
            print(note)
        registers = [*REGISTERS]
        if args.candidate_scan:
            registers.extend(candidate_registers())
        results = [probe_register(client, register, offset) for register in registers]
    finally:
        client.close()

    for result in results:
        value = result.decoded_value if result.error is None else result.error
        print(f"{result.address:4} {result.name:32} {value} {result.unit}".rstrip())
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    json_path, csv_path = write_results(results, args.output_dir, stamp)
    print(f"JSON: {json_path}")
    print(f"CSV:  {csv_path}")
    return (
        0
        if all(result.error is None or not result.documented for result in results)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
