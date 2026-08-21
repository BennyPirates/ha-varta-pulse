"""Tests for read-only VARTA pulse probe decoding."""

import unittest

from src.varta_pulse_probe import (
    REGISTERS,
    candidate_registers,
    decode,
    plausible,
    signed16,
)


def register(address: int):
    return next(item for item in REGISTERS if item.address == address)


class VartaPulseProbeTests(unittest.TestCase):
    def test_signed16_and_power_decode(self) -> None:
        self.assertEqual(signed16(0xFE69), -407)
        self.assertEqual(decode(register(1066), [0xFE69]), -407)

    def test_storage_state_decode(self) -> None:
        self.assertEqual(decode(register(1065), [3]), "discharging")

    def test_varta_string_decode(self) -> None:
        self.assertEqual(
            decode(register(1000), [ord("2"), ord("."), ord("6"), 0]), "2.6"
        )

    def test_soc_plausibility(self) -> None:
        self.assertTrue(plausible(register(1068), 52))
        self.assertFalse(plausible(register(1068), 101))

    def test_candidate_registers_are_not_documented(self) -> None:
        candidates = candidate_registers()
        self.assertIn(1088, {candidate.address for candidate in candidates})
        self.assertTrue(all(not candidate.documented for candidate in candidates))
        self.assertNotIn(2066, {candidate.address for candidate in candidates})
