from .base import DataSource
import numpy as np
import h5py
import os


SUPPORTED_RECORD_EXTENSIONS = (".h5", ".hdf5", ".hdf")


def list_record_files(folder=os.path.join("data", "records")):
    if not os.path.isdir(folder):
        return []
    return sorted(
        filename for filename in os.listdir(folder)
        if filename.lower().endswith(SUPPORTED_RECORD_EXTENSIONS)
    )


def load_record_epochs(path, expected_channels=66, eeg_channels=64):
    with h5py.File(path, "r") as h5f:
        if "epochs" in h5f:
            epochs = _load_epochs_dataset(h5f["epochs"], expected_channels, eeg_channels)
            timestamps = _load_timestamps(h5f, epochs.shape[0])
            return epochs, timestamps

        if "mep" in h5f and "epochs_mV" in h5f["mep"]:
            epochs_mV = np.asarray(h5f["mep"]["epochs_mV"][:], dtype=np.float32)
            epochs = _mep_epochs_to_processor_epochs(epochs_mV, expected_channels)
            timestamps = _load_mep_timestamps(h5f["mep"], epochs.shape[0])
            return epochs, timestamps

    raise ValueError(f"No supported epochs dataset found in {path}")


def _load_epochs_dataset(dataset, expected_channels, eeg_channels):
    data = np.asarray(dataset[:], dtype=np.float32)
    attrs = dict(dataset.attrs)

    if data.ndim == 3:
        if data.shape[1] in (expected_channels, eeg_channels):
            epochs = data
        elif data.shape[2] in (expected_channels, eeg_channels):
            epochs = data.transpose(0, 2, 1)
        else:
            raise ValueError(f"Unsupported 3D epochs shape: {data.shape}")
        return _fit_epoch_channels(epochs, expected_channels)

    if data.ndim == 2:
        n_epochs = int(attrs.get("n_epochs", 0))
        n_samples = int(attrs.get("n_samples", 0))
        n_channels = int(attrs.get("n_channels", data.shape[1]))

        if n_epochs > 0 and n_samples > 0 and data.shape[0] == n_epochs * n_samples:
            epochs = data.reshape((n_epochs, n_samples, n_channels)).transpose(0, 2, 1)
            return _fit_epoch_channels(epochs, expected_channels)

        epochs = _mep_epochs_to_processor_epochs(data, expected_channels)
        return epochs

    raise ValueError(f"Unsupported epochs shape: {data.shape}")


def _fit_epoch_channels(epochs, expected_channels):
    if epochs.shape[1] == expected_channels:
        return epochs
    if epochs.shape[1] > expected_channels:
        return epochs[:, :expected_channels, :]

    pad_shape = (epochs.shape[0], expected_channels - epochs.shape[1], epochs.shape[2])
    padding = np.zeros(pad_shape, dtype=epochs.dtype)
    return np.concatenate([epochs, padding], axis=1)


def _mep_epochs_to_processor_epochs(epochs_mV, expected_channels):
    if epochs_mV.ndim != 2:
        raise ValueError(f"Unsupported MEP epochs shape: {epochs_mV.shape}")

    epochs = np.zeros((epochs_mV.shape[0], expected_channels, epochs_mV.shape[1]), dtype=np.float32)
    epochs[:, -1, :] = epochs_mV * 1e-3
    return epochs


def _load_timestamps(h5f, n_epochs):
    if "timestamps" not in h5f:
        return np.arange(n_epochs, dtype=float)
    timestamps = np.asarray(h5f["timestamps"][:], dtype=float)
    if timestamps.size < n_epochs:
        return np.arange(n_epochs, dtype=float)
    return timestamps[:n_epochs]


def _load_mep_timestamps(mep_group, n_epochs):
    if "trigger_times_ms" in mep_group:
        timestamps = np.asarray(mep_group["trigger_times_ms"][:], dtype=float)
        if timestamps.size >= n_epochs:
            return timestamps[:n_epochs]
    return np.arange(n_epochs, dtype=float)

class FileSource(DataSource):
    def load_file(self, path):
        epochs, timestamps = load_record_epochs(path)
        for epoch, timestamp in zip(epochs, timestamps):
            self.dataReady.emit(epoch, float(timestamp))
