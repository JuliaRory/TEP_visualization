import os

import h5py
import numpy as np


class EpochRecordBuffer:
    """Collect epochs during an NVX recording and save them to a separate HDF5 file."""

    def __init__(self, speed_settings):
        self.speed_settings = speed_settings
        self.record_path = None
        self.is_recording = False
        self._epochs = []
        self._timestamps = []

    def start(self, record_path):
        self.record_path = record_path
        self._epochs = []
        self._timestamps = []
        self.is_recording = True

    def add_epoch(self, epoch, timestamp):
        if not self.is_recording:
            return

        self._epochs.append(np.asarray(epoch, dtype=np.float32))
        self._timestamps.append(timestamp)

    def stop_and_save(self):
        self.is_recording = False
        return self.save()

    def save(self):
        if not self.record_path or not self._epochs:
            self._epochs = []
            self._timestamps = []
            return None

        epoch_path = self._epoch_record_path()
        os.makedirs(os.path.dirname(epoch_path), exist_ok=True)

        epochs = np.asarray(self._epochs, dtype=np.float32)
        if epochs.ndim != 3:
            raise ValueError(f"Expected epochs with shape [n_epochs, n_channels, n_samples], got {epochs.shape}")

        n_epochs, n_channels, n_samples = epochs.shape
        data = epochs.transpose(0, 2, 1).reshape(-1, n_channels)
        timestamps = np.asarray(self._timestamps, dtype=np.int64)

        with h5py.File(epoch_path, "w") as h5f:
            data_set = h5f.create_dataset("epochs", data=data, dtype="float32")
            self._write_attrs(data_set, n_epochs, n_samples, n_channels)

            ts_set = h5f.create_dataset("timestamps", data=timestamps, dtype="int64")
            ts_set.attrs["units"] = "ns"

        self._epochs = []
        self._timestamps = []
        return epoch_path

    def _epoch_record_path(self):
        filename = os.path.basename(self.record_path)
        stem = os.path.splitext(filename)[0]
        return os.path.join("data", "records", f"{stem}.h5")

    def _write_attrs(self, dataset, n_epochs, n_samples, n_channels):
        dataset.attrs["source"] = "TEP_visual"
        dataset.attrs["Fs"] = self.speed_settings.Fs
        dataset.attrs["n_epochs"] = n_epochs
        dataset.attrs["n_samples"] = n_samples
        dataset.attrs["n_channels"] = n_channels
        dataset.attrs["shape_original"] = "[n_epochs, n_channels, n_samples]"
        dataset.attrs["shape_saved"] = "[n_epochs * n_samples, n_channels]"
