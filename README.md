# infoink

`infoink` is a Raspberry Pi monitor UI for the Waveshare 2.13" touch e-paper display.

It shows a simple touch-driven menu with:
- IPv4 addresses on non-loopback interfaces
- Connected Wi-Fi networks
- Clock/date
- Admin actions (reboot/shutdown) with confirmation protection

It also supports a simulator mode so you can develop without connected e-paper hardware.

## Requirements
- Raspberry Pi (for hardware mode)
- Python 3
- Dependencies in `requirements.txt`
- Waveshare 2.13 touch e-paper connected and supported by `lib/TP_lib/*`

## Setup
```bash
./setup.sh
```

## Run
Hardware mode:
```bash
./run.sh
```

Simulator mode:
```bash
./run.sh --simulator
```

Then open:
`http://127.0.0.1:8765`

## Notes
- `run.sh` and `setup.sh` automatically `cd` to the project directory, so they can be launched from any working directory.
- Simulator mode uses mocked display/touch backends in `simulator_backend.py` but runs the same app logic from `monitor.py`.
- On `Ctrl+C`, the app clears the display and exits cleanly.

