#!/usr/bin/env python3
"""CLI entry point for the strictly read-only VARTA pulse probe."""

from src.varta_pulse_probe import main

if __name__ == "__main__":
    raise SystemExit(main())
