"""Tests for pure VARTA pulse public-register decoding."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
PACKAGE = "varta_pulse"

package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "custom_components" / PACKAGE)]
sys.modules[PACKAGE] = package


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{name}", ROOT / "custom_components" / PACKAGE / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


const = load_module("const")
registers = load_module("registers")


class VartaRegisterTests(unittest.TestCase):
    """Validate documented conversion rules without requiring Home Assistant."""

    def definition(self, key: str):
        return next(register for register in const.REGISTERS if register.key == key)

    def test_signed_power(self) -> None:
        value = registers.decode(self.definition("battery_power"), [0xFFFE])
        self.assertEqual(value.value, -2)
        self.assertTrue(value.plausible)

    def test_capacity_is_ten_wh_units(self) -> None:
        value = registers.decode(self.definition("installed_capacity"), [586])
        self.assertEqual(value.value, 5860)
        self.assertEqual(value.raw_value, 586)

    def test_state_of_charge_bounds(self) -> None:
        valid = registers.decode(self.definition("state_of_charge"), [59])
        invalid = registers.decode(self.definition("state_of_charge"), [101])
        self.assertTrue(valid.plausible)
        self.assertFalse(invalid.plausible)

    def test_ascii_string_low_bytes(self) -> None:
        value = registers.decode(
            self.definition("ems_firmware"), [ord("2"), ord("."), ord("6")]
        )
        self.assertEqual(value.value, "2.6")

    def test_unknown_state_is_not_available(self) -> None:
        value = registers.decode(self.definition("state"), [99])
        self.assertEqual(value.value, "Unknown (99)")
        self.assertFalse(value.plausible)


if __name__ == "__main__":
    unittest.main()
