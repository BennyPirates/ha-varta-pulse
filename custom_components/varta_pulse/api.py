"""Strictly read-only Modbus TCP client for VARTA pulse."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import MIN_REQUEST_INTERVAL, READ_BLOCKS, REGISTERS
from .registers import VartaValue, decode, register_width


class VartaPulseError(Exception):
    """A VARTA Modbus request could not be completed safely."""


class VartaPulseClient:
    """Synchronous FC03-only client with VARTA's request-rate limit."""

    def __init__(
        self,
        host: str,
        port: int,
        unit_id: int,
        timeout: float,
        client_factory: Callable[..., ModbusTcpClient] = ModbusTcpClient,
    ) -> None:
        self._client = client_factory(host, port=port, timeout=timeout, retries=1)
        self._unit_id = unit_id
        self._lock = threading.Lock()
        self._last_request = 0.0

    def close(self) -> None:
        """Close the TCP client."""
        with self._lock:
            self._client.close()

    def read_identity(self) -> str:
        """Read EMS firmware for config-flow connection validation."""
        registers = self._read_holding(1000, 17)
        return decode(REGISTERS[0], registers).value  # type: ignore[return-value]

    def read_all(self) -> dict[str, VartaValue]:
        """Read only public VARTA blocks using FC03 with rate limiting."""
        raw: dict[int, int] = {}
        for start, count in READ_BLOCKS:
            values = self._read_holding(start, count)
            raw.update(dict(zip(range(start, start + count), values, strict=True)))

        decoded: dict[str, VartaValue] = {}
        for register in REGISTERS:
            values = [
                raw[register.address + index]
                for index in range(register_width(register.data_type))
            ]
            decoded[register.key] = decode(register, values)
        return decoded

    def _read_holding(self, address: int, count: int) -> list[int]:
        """Use FC03 exclusively. This class deliberately has no write method."""
        with self._lock:
            delay = MIN_REQUEST_INTERVAL - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
            try:
                if not self._client.connected and not self._client.connect():
                    raise VartaPulseError("Could not connect to VARTA pulse")
                response = self._client.read_holding_registers(
                    address=address, count=count, device_id=self._unit_id
                )
                self._last_request = time.monotonic()
            except ModbusException as error:
                raise VartaPulseError(str(error)) from error
            except OSError as error:
                raise VartaPulseError(str(error)) from error
            if response.isError():
                raise VartaPulseError(str(response))
            registers = getattr(response, "registers", None)
            if not registers or len(registers) != count:
                raise VartaPulseError("Unexpected Modbus register count")
            return [int(value) for value in registers]
