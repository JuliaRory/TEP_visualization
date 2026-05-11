import json
import os

import numpy as np

from logic.mep_movement_detection import load_saved_epoch_file


def load_sequences(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_mep_epochs(path, baseline_from_ms=-20, baseline_to_ms=-5):
    time, epochs, _fs = load_saved_epoch_file(path)
    if epochs.shape[1] < 2:
        raise ValueError("Expected at least two EMG channels in saved epochs")

    emg = epochs[:, -2:, :] * 1e3
    emg = np.diff(emg, axis=1).squeeze(axis=1)

    baseline_mask = (time >= baseline_from_ms) & (time <= baseline_to_ms)
    if np.any(baseline_mask):
        baseline = np.nanmean(emg[:, baseline_mask], axis=1, keepdims=True)
        emg = emg - baseline

    return time, emg


def condition_options(sequence):
    options = []
    if not sequence:
        return options

    stimuli_set = sequence.get("set", {})
    order = np.asarray(sequence.get("order", []), dtype=int)
    for value in sorted(set(order.tolist())):
        key = str(value)
        stimulus = stimuli_set.get(key, "")
        label = f"{value}"
        if stimulus:
            label = f"{value}: {os.path.splitext(os.path.basename(stimulus))[0]}"
        options.append((value, label))
    return options


def labels_for_epochs(sequence, n_epochs):
    order = np.asarray(sequence.get("order", []), dtype=int)
    if order.size == 0:
        return np.arange(1, n_epochs + 1, dtype=int), []

    warnings = []
    if order.size == n_epochs + 1:
        order = order[1:]
        warnings.append("Sequence is one item longer than epochs; the first item was skipped.")
    elif order.size != n_epochs:
        n = min(order.size, n_epochs)
        warnings.append(
            f"Sequence length ({order.size}) does not match epochs ({n_epochs}); using first {n} pairs."
        )
        order = order[:n]

    if order.size < n_epochs:
        padded = np.full(n_epochs, fill_value=-1, dtype=int)
        padded[:order.size] = order
        order = padded

    return order, warnings


def epoch_amplitudes(epochs, time, from_ms=15, to_ms=40):
    mask = (time >= from_ms) & (time <= to_ms)
    if not np.any(mask):
        return np.full(epochs.shape[0], np.nan)

    data = epochs[:, mask]
    return np.nanmax(data, axis=1) - np.nanmin(data, axis=1)


def analyze_conditions(epoch_path, sequence, selected_values, amp_from_ms=15, amp_to_ms=40):
    time, emg_epochs = load_mep_epochs(epoch_path)
    labels, warnings = labels_for_epochs(sequence, emg_epochs.shape[0])
    amplitudes = epoch_amplitudes(emg_epochs, time, amp_from_ms, amp_to_ms)

    conditions = []
    options = dict(condition_options(sequence))
    for value in selected_values:
        idxs = np.where(labels == value)[0]
        condition_epochs = emg_epochs[idxs]
        condition_amps = amplitudes[idxs]
        label = options.get(value, str(value))
        conditions.append({
            "value": value,
            "label": label,
            "idxs": idxs,
            "epochs": condition_epochs,
            "amplitudes": condition_amps,
            "mean_amplitude": float(np.nanmean(condition_amps)) if condition_amps.size else np.nan,
            "median_amplitude": float(np.nanmedian(condition_amps)) if condition_amps.size else np.nan,
            "n_epochs": int(condition_epochs.shape[0]),
        })

    return {
        "time": time,
        "emg_epochs": emg_epochs,
        "labels": labels,
        "amplitudes": amplitudes,
        "conditions": conditions,
        "warnings": warnings,
    }
