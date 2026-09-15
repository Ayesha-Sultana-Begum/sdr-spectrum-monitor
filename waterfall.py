"""
waterfall.py
------------
Connects to a USRP software-defined radio over the network and shows a
live, scrolling waterfall display (frequency vs. time, colored by power)
centered on a single fixed frequency. This is a *receive-only* script --
it never transmits.

Unlike quick_scan.py (which sweeps the whole FM band once and saves a
static plot), this script watches one slice of spectrum continuously.
Close the plot window to stop.

Run it with:
    python waterfall.py
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import uhd

# --------------------------------------------------------------------------
# Configuration -- edit these values to change what gets watched.
# --------------------------------------------------------------------------
DEVICE_ARGS = "addr=192.168.10.2"  # how to find the USRP on the network
CENTER_FREQ = 97.5e6                # fixed frequency to watch live (Hz)
SAMPLE_RATE = 2e6                   # width of spectrum captured (Hz)
GAIN_DB = 30                        # receive gain
FFT_SIZE = 4096                     # frequency resolution of each row
SAMPS_PER_STEP = 32768              # raw samples captured per frame
SETTLE_SAMPLES = 4096               # samples thrown away right after retuning
LO_LEAKAGE_MASK_HZ = 10e3           # width to null out on each side of the center-frequency (DC) bin
HISTORY_ROWS = 100                  # how many past rows the waterfall keeps on screen
FRAME_INTERVAL_MS = 100             # delay between animation updates (~10 updates/sec)


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


def compute_spectrum_row(samples):
    """Turn a batch of IQ samples into one row of power values (dB) for
    the waterfall. The frequency axis is fixed (CENTER_FREQ never
    changes), so unlike quick_scan.py's compute_spectrum() this only
    needs to return power, not frequencies."""
    # Use only as many samples as the FFT size, and apply a Hann window to
    # reduce "spectral leakage" (a smearing artifact at the edges of the FFT).
    windowed = samples[:FFT_SIZE] * np.hanning(FFT_SIZE)

    spectrum = np.fft.fftshift(np.fft.fft(windowed))
    power_db = 20 * np.log10(np.abs(spectrum) + 1e-12)  # +1e-12 avoids log(0)

    # Same LO-leakage mask as quick_scan.py: the USRP's zero-IF architecture
    # leaks its local oscillator into the DC bin, which always lands exactly
    # on CENTER_FREQ. Null out a fixed-width frequency window (rather than a
    # fixed bin count) so the mask stays correct if FFT_SIZE or SAMPLE_RATE
    # ever change.
    bin_width_hz = SAMPLE_RATE / FFT_SIZE
    mask_bins = int(np.ceil(LO_LEAKAGE_MASK_HZ / bin_width_hz))
    center_idx = FFT_SIZE // 2
    power_db[center_idx - mask_bins : center_idx + mask_bins + 1] = np.nan

    return power_db


def main():
    usrp = uhd.usrp.MultiUSRP(DEVICE_ARGS)

    # The very first receive right after opening the device tends to carry
    # an extra startup transient (same warm-up trick as quick_scan.py).
    capture_chunk(usrp, CENTER_FREQ)

    # Frequency axis is fixed since CENTER_FREQ never changes, so compute
    # it once instead of every frame.
    freqs = np.fft.fftshift(np.fft.fftfreq(FFT_SIZE, d=1 / SAMPLE_RATE))
    freqs_hz = freqs + CENTER_FREQ

    # Prime the waterfall buffer with one real spectrum row (instead of
    # zeros) so the window opens showing real data and a sensible color
    # scale right away. The buffer's shape never changes after this --
    # only its contents scroll.
    first_row = compute_spectrum_row(capture_chunk(usrp, CENTER_FREQ))
    waterfall_buffer = np.tile(first_row, (HISTORY_ROWS, 1))

    fig, ax = plt.subplots(figsize=(10, 6))
    image_artist = ax.imshow(
        waterfall_buffer,
        aspect="auto",
        extent=[freqs_hz[0] / 1e6, freqs_hz[-1] / 1e6, HISTORY_ROWS, 0],
        cmap="viridis",
    )
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Frames ago")
    ax.set_title(f"Live Waterfall around {CENTER_FREQ / 1e6:.1f} MHz")
    fig.colorbar(image_artist, ax=ax, label="Power (dB)")
    fig.tight_layout()

    def update(frame_num):
        """Called automatically by FuncAnimation every FRAME_INTERVAL_MS.
        Captures one new chunk, computes its spectrum row, scrolls the
        waterfall buffer, and redraws the image."""
        samples = capture_chunk(usrp, CENTER_FREQ)
        power_row = compute_spectrum_row(samples)

        # Scroll every row up one slot (discarding the oldest row at index 0)
        # and write the newest row into the slot this frees at the bottom.
        waterfall_buffer[:-1] = waterfall_buffer[1:]
        waterfall_buffer[-1] = power_row

        image_artist.set_data(waterfall_buffer)
        return (image_artist,)

    # FuncAnimation is the "loop": it calls update() on a repeating timer
    # instead of us writing an explicit for/while loop. cache_frame_data
    # must be off since this animation has no fixed end -- caching every
    # past frame would leak memory the longer the window stays open.
    anim = animation.FuncAnimation(
        fig,
        update,
        interval=FRAME_INTERVAL_MS,
        blit=True,
        cache_frame_data=False,
    )

    plt.show()


if __name__ == "__main__":
    main()
