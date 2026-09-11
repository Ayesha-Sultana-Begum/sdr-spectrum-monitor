"""
quick_scan.py
-------------
Connects to a USRP software-defined radio over the network and scans the
FM broadcast band (88-108 MHz), producing a plot of signal power vs.
frequency. This is a *receive-only* script -- it never transmits.

Run it with:
    python quick_scan.py
"""

import numpy as np
import matplotlib.pyplot as plt
import uhd

# --------------------------------------------------------------------------
# Configuration -- edit these values to change what gets scanned.
# --------------------------------------------------------------------------
DEVICE_ARGS = "addr=192.168.10.2"  # how to find the USRP on the network
FREQ_START = 88e6                  # start of FM broadcast band (Hz)
FREQ_STOP = 108e6                  # end of FM broadcast band (Hz)
SAMPLE_RATE = 2e6                  # width of spectrum captured per step (Hz)
GAIN_DB = 30                       # receive gain
FFT_SIZE = 4096                    # frequency resolution of each chunk
SAMPS_PER_STEP = 32768             # raw samples captured at each frequency
SETTLE_SAMPLES = 4096              # samples thrown away right after retuning
NUM_PEAKS = 5                      # how many strongest signals to report
MIN_PEAK_SPACING_HZ = 200e3        # don't report two peaks closer than this


def capture_chunk(usrp, center_freq):
    """Tune to center_freq and return a clean batch of IQ samples.

    recv_num_samps() opens a temporary receive stream, tunes to the given
    frequency and sample rate, grabs the requested number of samples, and
    closes the stream again. The first samples after retuning are often
    invalid (zeros or transients), so we throw away SETTLE_SAMPLES of them.
    """
    samples = usrp.recv_num_samps(
        SETTLE_SAMPLES + SAMPS_PER_STEP,  # how many samples to capture
        center_freq,                      # RX frequency (Hz)
        SAMPLE_RATE,                       # RX sample rate (Hz)
        [0],                                # channel list (just channel 0)
        GAIN_DB,                            # RX gain (dB)
    )
    return samples[0][SETTLE_SAMPLES:]  # samples has shape (1, num_samps)


def compute_spectrum(samples, center_freq):
    """Turn a batch of IQ samples into (frequencies_hz, power_db) arrays
    covering the slice of spectrum captured around center_freq."""
    # Use only as many samples as the FFT size, and apply a Hann window to
    # reduce "spectral leakage" (a smearing artifact at the edges of the FFT).
    windowed = samples[:FFT_SIZE] * np.hanning(FFT_SIZE)

    spectrum = np.fft.fftshift(np.fft.fft(windowed))
    power_db = 20 * np.log10(np.abs(spectrum) + 1e-12)  # +1e-12 avoids log(0)

    # fftfreq gives frequencies relative to 0 Hz; shift them to sit around
    # the actual center frequency we tuned to.
    freqs = np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, d=1 / SAMPLE_RATE))
    freqs_hz = freqs + center_freq

    return freqs_hz, power_db


def find_peaks(freqs_hz, power_db, num_peaks=NUM_PEAKS):
    """Return the (frequency, power) pairs for the strongest signals found,
    spaced at least MIN_PEAK_SPACING_HZ apart so the same station's peak
    isn't reported more than once."""
    order = np.argsort(power_db)[::-1]  # indices sorted strongest-first

    peaks = []
    for idx in order:
        f = freqs_hz[idx]
        if all(abs(f - pf) > MIN_PEAK_SPACING_HZ for pf, _ in peaks):
            peaks.append((f, power_db[idx]))
        if len(peaks) == num_peaks:
            break
    return peaks


def plot_spectrum(freqs_hz, power_db, peaks, filename="fm_spectrum.png"):
    """Draw frequency (MHz) vs. power (dB), mark the peaks, and save to file."""
    plt.figure(figsize=(10, 5))
    plt.plot(freqs_hz / 1e6, power_db, linewidth=0.8)

    for f, p in peaks:
        plt.plot(f / 1e6, p, "ro")
        plt.annotate(
            f"{f / 1e6:.1f} MHz",
            (f / 1e6, p),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
        )

    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Power (dB)")
    plt.title("FM Broadcast Band Spectrum (88-108 MHz)")
    plt.grid(True, linewidth=0.3)
    plt.tight_layout()
    plt.savefig(filename)
    print(f"Saved plot to {filename}")


def main():
    usrp = uhd.usrp.MultiUSRP(DEVICE_ARGS)

    # Cover 88-108 MHz in non-overlapping steps the width of SAMPLE_RATE:
    # with a 2 MHz sample rate that's centers at 89, 91, ..., 107 MHz.
    step = SAMPLE_RATE
    centers = np.arange(FREQ_START + step / 2, FREQ_STOP, step)

    # The very first receive right after opening the device tends to carry
    # an extra startup transient on top of the normal per-tune settling
    # period (we saw this in testing as a large fake spike at the first
    # frequency scanned). One throwaway capture warms the device up.
    capture_chunk(usrp, centers[0])

    all_freqs = []
    all_power = []

    for center_freq in centers:
        print(f"Scanning around {center_freq / 1e6:.1f} MHz...")
        samples = capture_chunk(usrp, center_freq)
        freqs_hz, power_db = compute_spectrum(samples, center_freq)
        all_freqs.append(freqs_hz)
        all_power.append(power_db)

    freqs_hz = np.concatenate(all_freqs)
    power_db = np.concatenate(all_power)

    # Sort by frequency so the stitched-together spectrum reads left-to-right.
    order = np.argsort(freqs_hz)
    freqs_hz = freqs_hz[order]
    power_db = power_db[order]

    peaks = find_peaks(freqs_hz, power_db)
    print("\nStrongest signals found:")
    for f, p in peaks:
        print(f"  {f / 1e6:.1f} MHz  ({p:.1f} dB)")

    plot_spectrum(freqs_hz, power_db, peaks)


if __name__ == "__main__":
    main()
