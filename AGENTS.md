# AGENTS.md

## Project Purpose
This project runs a Waveshare 2.13" Touch e-paper monitor UI on Raspberry Pi hardware, with an optional simulator mode for local development without GPIO/SPI/I2C.

## Core Behavior
- Main app: `monitor.py`
- Hardware backend: `lib/TP_lib/*`
- Simulator backend: `simulator_backend.py`
- Startup scripts: `run.sh`, `setup.sh`

Current UI pages:
1. `IP Addresses`
2. `Wi-Fi`
3. `Clock`
4. `Admin` (reboot/shutdown with explicit confirmation flow)

## Runtime Modes
- Hardware mode: default (`./run.sh`)
- Simulator mode: `./run.sh --simulator`
  - Serves HTTP UI on `127.0.0.1:8765` by default
  - Uses mocked EPD + touch driver classes in `simulator_backend.py`

Important: Keep one app loop in `monitor.py`. Do not fork a second app implementation for simulator behavior.

## Safety-Critical Admin Flow
Admin actions are intentionally guarded:
- First tap arms an action (`reboot` or `shutdown`)
- Second tap must happen in the right-side confirm zone within timeout
- Timeout auto-disarms

If modifying this flow, preserve deliberate multi-step confirmation.

## Touch/Input Notes
- Touch coordinates are transformed in `raw_touch_to_landscape(...)` to match display orientation.
- Debounce/edge behavior is implemented with:
  - `touch_latched`
  - `TOUCH_DEBOUNCE_SECONDS`
  - INT pin state transitions

Do not reintroduce noisy touch logging in drivers.

## Performance Constraints (Pi 3)
Keep CPU usage low:
- Avoid busy-loop polling
- Keep/extend touch poll sleep intervals
- Keep network query caching (`NETWORK_CACHE_TTL_SECONDS`)
- Avoid frequent shell subprocess calls in tight loops

## File Editing Expectations
- Prefer small, focused changes.
- Keep simulator-specific code in `simulator_backend.py`.
- Keep project scripts runnable from any working directory.
- Preserve graceful shutdown behavior (clear display, sleep, exit).

