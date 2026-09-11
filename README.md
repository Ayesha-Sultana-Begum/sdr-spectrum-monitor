# SDR Spectrum Monitor

A small beginner project that scans the FM broadcast band (**88–108 MHz**)
using a USRP software-defined radio, UHD, and Python — and plots the
result as a spectrum graph (power vs. frequency).

This project only **receives** (listens). It never transmits.

## Hardware

- **SDR:** a USRP, connected over Ethernet at `addr=192.168.10.2`
- **Driver stack:** UHD (`UHD_4.9.0.1`), GNU Radio 3.10.12

## Prerequisites

Installed system-wide (not through pip — see "Why no `gnuradio`/`uhd` in
requirements.txt?" below):

- GNU Radio 3.10.12 (`gnuradio-companion`)
- UHD (USRP Hardware Driver), including its Python bindings
- Python 3

## Setup

From the project folder:

```bash
# 1. Create a virtual environment that can still see the system-installed
#    GNU Radio / UHD Python packages:
python3 -m venv --system-site-packages .venv

# 2. Activate it (do this every time you open a new terminal for this project):
source .venv/bin/activate

# 3. Install this project's own Python dependencies:
pip install -r requirements.txt
```

### Why no `gnuradio`/`uhd` in requirements.txt?

Neither is distributed as a pip package — they're installed at the system
level. The `--system-site-packages` flag above lets the virtual environment
"see" them anyway, alongside the packages we do install with pip.

## Usage

With the virtual environment active:

```bash
python quick_scan.py
```

The script will:

1. Connect to the USRP.
2. Retune across several steps to cover 88–108 MHz (a single capture can't
   see the whole band at once).
3. Compute a power spectrum (via FFT) for each step and stitch them together.
4. Print the strongest frequencies found (likely local FM stations) to the
   terminal.
5. Save a plot to `fm_spectrum.png` in this folder.

## Project structure

```
sdr-spectrum-monitor/
├── README.md          # this file
├── .gitignore         # files Git should not track
├── requirements.txt   # pip-installable dependencies
└── quick_scan.py       # connects to the USRP and scans the FM band
```

## Known limitation: LO leakage ("DC spike")

You may notice a small, suspiciously precise "peak" at exactly 89.0, 91.0,
93.0 MHz, etc. — i.e. exactly at the center of each scanned chunk. That's
almost certainly not a broadcast station; it's **LO leakage**, a common
receiver artifact where the radio's internal local oscillator leaks a
little energy at whatever frequency it's currently tuned to. Real SDR
tools deal with this by, e.g., offsetting the tuned frequency slightly
from the frequency of interest, or by masking out the center bin before
peak-detection. This script doesn't do that yet — a good next improvement.

## A note on legality

Passively listening to the public FM broadcast band is legal in virtually
every jurisdiction — it's the same signal any car radio receives. This
project never transmits. If you extend it to other frequency ranges or add
transmission features later, check your local regulations first.
