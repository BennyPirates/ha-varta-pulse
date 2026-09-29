"""Rate-limited Modbus TCP client for VARTA pulse."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    DISCHARGE_LIMIT_REGISTER,
    MIN_REQUEST_INTERVAL,
    READ_BLOCKS,
    REGISTERS,
    SCALE_FACTOR_BLOCK,
)
from .registers import VartaValue, apply_scale_factor, decode, register_width, signed16


class VartaPulseError(Exception):
    """A VARTA Modbus request could not be completed safely."""


class VartaPulseClient:
    """Synchronous client with VARTA's request-rate limit.

    The optional discharge hold uses the community-tested FC06 register 1074.
    No other register can be written by this client.
    """

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
        self._control_lock = threading.Lock()
        self._last_request = 0.0
        self._discharge_hold = False
        self._original_discharge_limit: int | None = None

    @property
    def discharge_hold(self) -> bool:
        """Whether this client is maintaining a discharge hold."""
        return self._discharge_hold

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

        try:
            start, count = SCALE_FACTOR_BLOCK
            values = self._read_holding(start, count)
            raw.update(dict(zip(range(start, start + count), values, strict=True)))
        except VartaPulseError:
            # The documented factors are not implemented by older pulse models.
            # Their implicit scale factor is zero.
            pass

        decoded: dict[str, VartaValue] = {}
        for register in REGISTERS:
            values = [
                raw[register.address + index]
                for index in range(register_width(register.data_type))
            ]
            decoded[register.key] = decode(register, values)
            if register.scale_factor_address is not None:
                scale_factor = signed16(raw.get(register.scale_factor_address, 0))
                scaled = apply_scale_factor(decoded[register.key], scale_factor)
                if register.data_type == "energy_counter" and scaled.plausible:
                    scaled = VartaValue(
                        round(float(scaled.value) / 1000, 6),
                        scaled.raw_value,
                        True,
                    )
                decoded[register.key] = scaled
        return decoded

    def set_discharge_hold(self, enabled: bool) -> None:
        """Opt into, or release, the device's temporary discharge limit."""
        with self._control_lock:
            if enabled:
                if self._discharge_hold:
                    return
                original = self._read_holding(DISCHARGE_LIMIT_REGISTER, 1)[0]
                if original == 0:
                    raise VartaPulseError(
                        "Discharge limit is already zero; another controller may own it"
                    )
                self._write_discharge_limit(0)
                if self._read_holding(DISCHARGE_LIMIT_REGISTER, 1)[0] != 0:
                    raise VartaPulseError("VARTA did not accept the discharge hold")
                self._original_discharge_limit = original
                self._discharge_hold = True
            elif self._discharge_hold:
                assert self._original_discharge_limit is not None
                self._write_discharge_limit(self._original_discharge_limit)
                self._discharge_hold = False
                self._original_discharge_limit = None

    def refresh_discharge_hold(self) -> None:
        """Renew the hold before VARTA's 120-second watchdog expires."""
        with self._control_lock:
            if self._discharge_hold:
                self._write_discharge_limit(0)

    def _write_discharge_limit(self, value: int) -> None:
        """FC06 write restricted to the discharge-limit register."""
        with self._lock:
            delay = MIN_REQUEST_INTERVAL - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
            try:
                if not self._client.connected and not self._client.connect():
                    raise VartaPulseError("Could not connect to VARTA pulse")
                response = self._client.write_register(
                    address=DISCHARGE_LIMIT_REGISTER,
                    value=value,
                    device_id=self._unit_id,
                )
                self._last_request = time.monotonic()
            except (ModbusException, OSError) as error:
                raise VartaPulseError(str(error)) from error
            if response.isError():
                raise VartaPulseError(str(response))

    def _read_holding(self, address: int, count: int) -> list[int]:
        """Read one holding-register block using FC03."""
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
