# VARTA pulse for Home Assistant

Local, strictly read-only Home Assistant custom integration for VARTA pulse
energy storage systems via Modbus TCP.

## Safety boundary

- Only Modbus Function Code 03 (read holding registers) is implemented.
- No service, entity, method, dependency, or configuration path writes a
  Modbus register.
- It reads only VARTA's publicly documented register table.
- Requests are serialized and separated by at least 1.05 seconds, in line
  with VARTA's published request-rate guidance.

This integration is intentionally a monitoring integration. Battery dispatch,
grid charging, reserve policies, and inverter control are **not** implemented.

## Read-only diagnostic probe

The repository also contains a standalone probe for troubleshooting the
documented Modbus table without loading Home Assistant:

```shell
python varta_pulse_probe.py varta.local
python varta_pulse_probe.py varta.local --candidate-scan
```

The probe uses only FC03 reads, keeps the documented Unit ID 255 default, and
writes JSON/CSV results below the ignored `results/` directory. Candidate
registers are reported as raw values only; the probe assigns them no semantic
meaning or write capability.

## What it exposes

- battery status and state of charge
- battery, grid, PV-sensor, apparent and reactive power
- available charge/discharge power and usable energy
- VARTA's cumulative AC-to-DC charged-energy counter, suitable for the
  Energy dashboard
- installed capacity, module count, firmware and Modbus table version

For pulse neo systems, the integration automatically applies the documented
scale factors to active/apparent power, grid power, installed capacity, and
the cumulative charge counter. On older pulse models these factors are not
advertised by the VARTA table, so an unavailable factor is treated as zero.

Positive/negative power direction is preserved as documented by VARTA. Check
the physical system's readings before using a value in an automation.

## Installation via HACS

[![Open your Home Assistant instance and open the add repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=BennyPirates&repository=ha-varta-pulse&category=integration)

1. Open HACS → Integrations → three-dot menu → Custom repositories.
2. Add `BennyPirates/ha-varta-pulse` as category **Integration**, or use the
   button above.
3. Download the integration, then restart Home Assistant.
4. Add **VARTA pulse** from Settings → Devices & services.

The VARTA documentation recommends Unit ID `255`; installations that already
use a different working Unit ID can select it during setup.

## Migration from a YAML Modbus setup

Keep the existing YAML integration active initially. Add this integration
alongside it, compare values over at least one complete charge/discharge cycle,
then migrate dashboards and automations. Remove the old YAML configuration only
after the new sensors are verified.

`Total charged energy` supersedes a power-derived charging counter with the
storage system's own cumulative AC-to-DC counter. VARTA's public table does not
provide a corresponding cumulative discharge counter; keep an existing
power-derived discharge total until you intentionally replace it.

## Technical documentation

- [VARTA Modbus TCP register table v13.1](https://community-openhab-org.s3.dualstack.eu-central-1.amazonaws.com/original/3X/b/9/b90607e891488d8ab920361161e73f454bc808a1.pdf)
- [VARTA pulse product data](https://www.varta-ag.com/fileadmin/varta/consumer/downloads/energy-storage/varta-pulse/Datasheet_VARTA_pulse_dach_de_4.pdf)

## Development

```shell
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install pymodbus==3.13.1
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy
```
