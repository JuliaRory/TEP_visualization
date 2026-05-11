from dataclasses import dataclass, asdict
import json
import os

import h5py
import numpy as np
from scipy.signal import butter, find_peaks, iirnotch, sosfilt, tf2sos


@dataclass
class MovementDetectionSettings:
    baseline_from_ms: float = -75
    baseline_to_ms: float = -20
    art_from_ms: float = -1.5
    art_to_ms: float = 8
    mep_from_ms: float = 15
    mep_to_ms: float = 75
    threshold_k: float = 15
    baseline_percentile: float = 99.5
    prominence_k: float = 4
    smooth_ms: float = 3
    min_width_ms: float = 2
    min_distance_ms: float = 10
    confirmation_window_ms: float = 8
    required_fraction: float = 0.25
    min_peak_area: float = 1.5e-10
    better_candidate_area_ratio: float = 3.0
    better_candidate_min_separation_ms: float = 40
    pre_tms_ignore_after_ms: float = -8
    detect_pre_tms: bool = True
    early_delay_ms: float = -80
    late_delay_ms: float = 80
    plot_from_ms: float = -100
    plot_to_ms: float = 300
    plot_ymax_mV: float = 3
    notch_hz: float = 50
    notch_width_hz: float = 1
    bandpass_low_hz: float = 10
    bandpass_high_hz: float = 450

    def to_dict(self):
        return asdict(self)


def calculate_tkeo(x):
    x = np.asarray(x)
    tkeo = np.zeros_like(x)
    tkeo[1:-1] = x[1:-1] ** 2 - x[:-2] * x[2:]
    tkeo[0] = tkeo[1]
    tkeo[-1] = tkeo[-2]
    return tkeo


def make_online_filters(settings, fs):
    notch_width = max(settings.notch_width_hz, np.finfo(float).eps)
    notch_hz = min(max(settings.notch_hz, 0.1), fs / 2 - 1)
    q = notch_hz / notch_width
    b_notch, a_notch = iirnotch(notch_hz, q, fs=fs)
    sos_notch = tf2sos(b_notch, a_notch)
    low = max(settings.bandpass_low_hz, 0.1)
    high = min(settings.bandpass_high_hz, fs / 2 - 1)
    if high <= low:
        high = min(low + 1, fs / 2 - 1)
    sos_butter = butter(
        4,
        (low, high),
        btype="bandpass",
        output="sos",
        fs=fs,
    )
    return sos_notch, sos_butter


def robust_noise_level(x):
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    if x.size == 0:
        raise ValueError("Baseline interval is empty")

    median = np.median(x)
    mad = np.median(np.abs(x - median))
    sigma = 1.4826 * mad

    if sigma <= np.finfo(float).eps:
        sigma = max(
            np.std(x),
            np.percentile(x, 75) - np.percentile(x, 25),
            np.finfo(float).eps,
        )

    return float(median), float(sigma)


def smooth_boxcar(x, time, window_ms):
    dt = np.median(np.diff(time))
    n_samples = max(1, int(round(window_ms / dt)))
    if n_samples <= 1:
        return x.copy()
    kernel = np.ones(n_samples) / n_samples
    return np.convolve(x, kernel, mode="same")


def detect_movement_in_epoch(time, emg_tkeo, settings):
    time = np.asarray(time)
    emg_tkeo = np.asarray(emg_tkeo)

    baseline = (settings.baseline_from_ms, settings.baseline_to_ms)
    art_limits = (settings.art_from_ms, settings.art_to_ms)

    baseline_mask = (time >= baseline[0]) & (time <= baseline[1])
    base = emg_tkeo[baseline_mask]
    noise_median, noise_sigma = robust_noise_level(base)

    threshold = max(
        noise_median + settings.threshold_k * noise_sigma,
        np.percentile(base, settings.baseline_percentile),
    )
    min_prominence = max(
        settings.prominence_k * noise_sigma,
        0.5 * (threshold - noise_median),
    )

    valid_mask = time > settings.mep_to_ms
    if settings.detect_pre_tms:
        valid_mask |= time < min(art_limits[0], settings.pre_tms_ignore_after_ms)

    signal_smooth = smooth_boxcar(emg_tkeo, time, settings.smooth_ms)
    signal_for_peaks = signal_smooth.copy()
    signal_for_peaks[~valid_mask] = noise_median

    dt = np.median(np.diff(time))
    min_width_samples = max(1, int(round(settings.min_width_ms / dt)))
    min_distance_samples = max(1, int(round(settings.min_distance_ms / dt)))

    peaks, props = find_peaks(
        signal_for_peaks,
        height=threshold,
        prominence=min_prominence,
        width=min_width_samples,
        distance=min_distance_samples,
    )

    half_window = max(1, int(round((settings.confirmation_window_ms / 2) / dt)))
    accepted = []
    accepted_prop_idxs = []
    onset_by_peak = []
    area_by_peak = []
    fraction_by_peak = []

    for prop_idx, peak_idx in enumerate(peaks):
        lo = max(0, peak_idx - half_window)
        hi = min(len(signal_smooth), peak_idx + half_window + 1)
        local_idxs = np.arange(lo, hi)
        local_idxs = local_idxs[valid_mask[local_idxs]]

        if local_idxs.size == 0:
            continue

        fraction = np.mean(signal_smooth[local_idxs] > threshold)
        if fraction < settings.required_fraction:
            continue

        area_lo = max(0, peak_idx - 2 * half_window)
        area_hi = min(len(signal_smooth), peak_idx + 2 * half_window + 1)
        trapezoid = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
        peak_area = trapezoid(
            np.maximum(signal_smooth[area_lo:area_hi] - threshold, 0),
            time[area_lo:area_hi],
        )
        if peak_area < settings.min_peak_area:
            continue

        onset_idx = peak_idx
        while (
            onset_idx > 0
            and valid_mask[onset_idx - 1]
            and signal_smooth[onset_idx - 1] > threshold
        ):
            onset_idx -= 1

        accepted.append(peak_idx)
        accepted_prop_idxs.append(prop_idx)
        onset_by_peak.append(onset_idx)
        area_by_peak.append(float(peak_area))
        fraction_by_peak.append(float(fraction))

    result = {
        "movement_found": False,
        "delay_ms": np.nan,
        "onset_time": np.nan,
        "peak_time": np.nan,
        "peak_amp": np.nan,
        "peak_prominence": np.nan,
        "peak_area": np.nan,
        "peak_times": json.dumps([]),
        "peak_onsets": json.dumps([]),
        "peak_amps": json.dumps([]),
        "peak_areas": json.dumps([]),
        "threshold": float(threshold),
        "noise_median": float(noise_median),
        "noise_sigma": float(noise_sigma),
        "fraction_max": 0.0,
        "n_peaks": 0,
    }

    if not accepted:
        return result

    peak_times = time[accepted].astype(float).tolist()
    peak_onsets = time[onset_by_peak].astype(float).tolist()
    peak_amps = signal_smooth[accepted].astype(float).tolist()
    peak_areas = area_by_peak

    selected_pos = 0
    for candidate_pos in range(1, len(accepted)):
        separated_enough = (
            time[accepted[candidate_pos]] - time[accepted[selected_pos]]
            >= settings.better_candidate_min_separation_ms
        )
        much_stronger = (
            area_by_peak[candidate_pos]
            >= area_by_peak[selected_pos] * settings.better_candidate_area_ratio
        )
        if separated_enough and much_stronger:
            selected_pos = candidate_pos
            break

    peak_idx = accepted[selected_pos]
    prop_idx = accepted_prop_idxs[selected_pos]
    onset_idx = onset_by_peak[selected_pos]

    result.update({
        "movement_found": True,
        "delay_ms": float(time[onset_idx]),
        "onset_time": float(time[onset_idx]),
        "peak_time": float(time[peak_idx]),
        "peak_amp": float(signal_smooth[peak_idx]),
        "peak_prominence": float(props["prominences"][prop_idx]),
        "peak_area": float(area_by_peak[selected_pos]),
        "peak_times": json.dumps(peak_times),
        "peak_onsets": json.dumps(peak_onsets),
        "peak_amps": json.dumps(peak_amps),
        "peak_areas": json.dumps(peak_areas),
        "fraction_max": float(np.max(fraction_by_peak)),
        "n_peaks": int(len(accepted)),
    })
    return result


def load_saved_epoch_file(path, default_fs=5000, default_window=(-100, 300)):
    with h5py.File(path, "r") as h5f:
        data = h5f["epochs"][:]
        attrs = dict(h5f["epochs"].attrs)

    n_epochs = int(attrs.get("n_epochs", 0))
    n_samples = int(attrs.get("n_samples", 0))
    n_channels = int(attrs.get("n_channels", 66))
    fs = float(attrs.get("Fs", default_fs))
    window_start = float(attrs.get("window_start_ms", default_window[0]))
    window_end = float(attrs.get("window_end_ms", default_window[1]))

    if n_epochs <= 0 or n_samples <= 0:
        n_samples = int(round((window_end - window_start) * fs / 1000))
        n_epochs = data.shape[0] // n_samples if n_samples > 0 else 0

    epochs = data.reshape((n_epochs, n_samples, n_channels)).transpose(0, 2, 1)
    time = np.linspace(window_start, window_end, n_samples, endpoint=False)
    return time, epochs, fs


def prepare_emg_epochs(epochs, fs, settings):
    if epochs.shape[1] < 2:
        raise ValueError("Expected at least two EMG channels in saved epochs")

    emg = epochs[:, -2:, :] * 1e3
    emg = np.diff(emg, axis=1).squeeze(axis=1)
    sos_notch, sos_butter = make_online_filters(settings, fs)
    emg_filtered = sosfilt(sos_notch, emg, axis=1)
    emg_filtered = sosfilt(sos_butter, emg_filtered, axis=1)
    tkeo = np.asarray([calculate_tkeo(epoch * 1e-3) for epoch in emg_filtered])
    return emg_filtered, tkeo


def analyze_epoch_file(path, settings):
    time, epochs, fs = load_saved_epoch_file(path)
    emg_filtered, tkeo_epochs = prepare_emg_epochs(epochs, fs, settings)

    rows = []
    for idx, tkeo_epoch in enumerate(tkeo_epochs, start=1):
        result = detect_movement_in_epoch(time, tkeo_epoch, settings)
        result["n_epoch"] = idx
        rows.append(result)

    delays = np.asarray([row["delay_ms"] for row in rows], dtype=float)
    early_count = int(np.sum(np.isfinite(delays) & (delays < settings.early_delay_ms)))
    late_count = int(np.sum(np.isfinite(delays) & (delays > settings.late_delay_ms)))

    return {
        "record_path": path,
        "record_name": os.path.basename(path),
        "time": time,
        "emg_epochs": emg_filtered,
        "tkeo_epochs": tkeo_epochs,
        "rows": rows,
        "delays": delays,
        "early_count": early_count,
        "late_count": late_count,
        "settings": settings.to_dict(),
    }
