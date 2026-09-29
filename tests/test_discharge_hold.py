"""Contract tests for the single opt-in Modbus write path."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
PACKAGE = "varta_pulse"

if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components" / PACKAGE)]
    sys.modules[PACKAGE] = package


def load_module(name: str):
    module_name = f"{PACKAGE}.{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(
        module_name, ROOT / "custom_components" / PACKAGE / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


load_module("const")
load_module("registers")
api = load_module("api")


class Response:
    def __init__(self, registers: list[int] | None = None) -> None:
        self.registers = registers

    def isError(self) -> bool:
        return False


class FakeModbusClient:
    def __init__(self, host: str, **kwargs: object) -> None:
        self.connected = True
        self.limit = 32768
        self.writes: list[tuple[int, int, int]] = []

    def connect(self) -> bool:
        return True

    def close(self) -> None:
        pass

    def read_holding_registers(
        self, address: int, count: int, device_id: int
    ) -> Response:
        assert address == 1074 and count == 1 and device_id == 255
        return Response([self.limit])

    def write_register(self, address: int, value: int, device_id: int) -> Response:
        self.writes.append((address, value, device_id))
        self.limit = value
        return Response()


class DischargeHoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = api.VartaPulseClient(
            "example.local", 502, 255, 5, client_factory=FakeModbusClient
        )
        self.interval = patch.object(api, "MIN_REQUEST_INTERVAL", 0)
        self.interval.start()

    def tearDown(self) -> None:
        self.interval.stop()

    def test_hold_refresh_and_restore_exact_raw_limit(self) -> None:
        self.client.set_discharge_hold(True)
        self.assertTrue(self.client.discharge_hold)
        self.client.refresh_discharge_hold()
        self.client.set_discharge_hold(False)
        self.assertFalse(self.client.discharge_hold)
        self.assertEqual(
            self.client._client.writes,
            [(1074, 0, 255), (1074, 0, 255), (1074, 32768, 255)],
        )

    def test_refuses_to_take_over_existing_zero_limit(self) -> None:
        self.client._client.limit = 0
        with self.assertRaises(api.VartaPulseError):
            self.client.set_discharge_hold(True)
        self.assertEqual(self.client._client.writes, [])


if __name__ == "__main__":
    unittest.main()
