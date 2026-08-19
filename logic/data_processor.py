from PyQt5.QtCore import pyqtSignal, QObject, pyqtSlot
import numpy as np
from scipy import signal
import warnings

from settings.settings import Settings

from utils.averaging_math import RollingMean, RollingMedian, RollingTrimMean


LABEL_ALL = "all"
LABEL_NOT_LABELED = "not labeled"
LABEL_SOURCE_STIMULUS = "stimulus"
LABEL_SOURCE_EXTERNAL = "epoch_labels"


class DataProcessor(QObject):
    """
    Базовый класс для источника данных.

    Args:
        settings(Settings): класс для хранения настроек для обработки данных.

    Attributes: 

    Private Attributes: 
        _n_epoch (int): счётчик сохранённого количества эпох
        _epochs (list): signle-trial TEPs [n_epoch x n_samples x n_channels]
        _timestamps (list): время прихода пакета (от резонанса) --> для сохранения эпох only [n_epoch]

    Signals:
        newDataProcessed: обработка данных завершена.
        
    """
    newDataProcessed = pyqtSignal()
    updateCounter = pyqtSignal(int)
    labelWarning = pyqtSignal(str)
    labelsChanged = pyqtSignal()
 
    def __init__(self, settings):
        super().__init__()
        self.settings = settings    # settings

        # для хранения данных
        self._raw_epochs = []
        self._raw_timestamps = []
        self._raw_epoch_labels = []
        self._eeg_epochs = []
        self._eeg_timestamps = []
        self._other_epochs = []
        self._other_timestamps = []
        self._epochs = []
        self._timestamps = []
        self.epoch_labels = []
        self.epoch_label_source = LABEL_SOURCE_STIMULUS
        self.epoch_label_filter = LABEL_ALL
        self.epoch_label_filters = [LABEL_ALL]
        self._pending_epoch_labels = {
            LABEL_SOURCE_STIMULUS: [],
            LABEL_SOURCE_EXTERNAL: [],
        }
        self._known_epoch_labels = set()
        self._label_warnings_seen = set()
        self._n_epoch = 0


        # self._n_samples = n_samples

        # флаги режимов
        self.average_data = False
        self.process_new_data = True
        self.use_eeg = bool(getattr(settings.processing_settings, "use_eeg", True))

        # функции-трансформации
        self._baseline = lambda x: x
        self._highpass_filter = lambda x: x
        self._lowpass_filter = lambda x: x
        self._referef = lambda x: x
        self._car = lambda x: x
        self._transform = lambda x: x
        self._emg_highpass_filter = lambda x: x
        self._emg_lowpass_filter = lambda x: x
        self._emg_baseline = lambda x: x
        self._emg_transform = lambda x: x
        self._warnings_seen = set()

        self._source_sampling_rate_Hz = float(getattr(settings.processing_settings, "current_sampling_rate_Hz", 5000))
        self._sampling_rate_Hz = self._source_sampling_rate_Hz
        self._other_sampling_rate_Hz = self._source_sampling_rate_Hz
        self._emg_resampling_enabled = bool(getattr(settings.processing_settings, "do_emg_resampling", True))
        self._emg_resample_freq_Hz = float(getattr(settings.processing_settings, "emg_resample_freq_Hz", 2000))
        self._resampling_enabled = bool(getattr(settings.processing_settings, "do_resampling", False))
        self._resample_freq_Hz = float(getattr(settings.processing_settings, "resample_freq_Hz", 2000))

        # данные для усреднения
        self.average_functions = None
        self.average_functions_mep = None
        self.average_mep_data = False       # overview panel
        self.average_tep_data = False       # overview panel

        # параметры усреднения
        self._n_aver_max = settings.n_aver if hasattr(settings, "n_aver") else 100
        self._aver_all = getattr(settings, "aver_all", True)
        self.aver_method = "mean"  # default, можно менять

        self._ms_to_sample = lambda x: int(x / 1000 * self._sampling_rate_Hz)                              # функция для пересчёта мс в сэмплы
        self._n_samples = self._ms_to_sample(self._epoch_window_duration_ms())                             # длина эпохи в сэмплах
        self._time_shift = self._ms_to_sample(0 - self._epoch_window_start_ms())                           # смещение относительно нуля для графиков в сэпмлах
        self._other_ms_to_sample = lambda x: int(x / 1000 * self._other_sampling_rate_Hz)
        self._other_n_samples = self._other_ms_to_sample(self._epoch_window_duration_ms())
        self._other_time_shift = self._other_ms_to_sample(0 - self._epoch_window_start_ms())

        self.aver_empty_func = {                                        # dict с функциями для усреднения
            "mean": lambda x, y, z: RollingMean(x, y, z), 
            "median": lambda x, y, z: RollingMedian(x, y, z), 
            "trimmean": lambda x, y, z: RollingTrimMean(x, y, save_all=z)
        }
        self.configure_sampling()


    @pyqtSlot(object, float)
    def add_epoch(self, epoch, ts):
        """
        
        :param self: Description
        :param epoch: Description       ndarray [n_channels, n_samples]
        :param ts: Description

        Signals:
            newDataProcessed: новая эпоха добавлена.
        """

        if self.process_new_data:
            raw_epoch = self._validate_epoch(epoch)
            if raw_epoch is None:
                return
            eeg_epoch, other_epoch = self._split_epoch(raw_epoch)
            other_epoch = self._prepare_emg_epoch(other_epoch)
            self._sync_other_epoch_shape(other_epoch)
            if self.use_eeg:
                eeg_epoch = self._prepare_eeg_epoch(eeg_epoch)
                if eeg_epoch is None:
                    return
                self._sync_epoch_shape(eeg_epoch)
                display_epoch = eeg_epoch
            else:
                display_epoch = other_epoch
            if display_epoch is None:
                return

            epoch_label = self._consume_epoch_label()
            self._raw_epochs.append(raw_epoch)
            self._raw_timestamps.append(ts)
            self._raw_epoch_labels.append(epoch_label)
            if self.use_eeg:
                self._eeg_epochs.append(eeg_epoch)
                self._eeg_timestamps.append(ts)
            self._other_epochs.append(other_epoch)
            self._other_timestamps.append(ts)
            self._epochs.append(display_epoch)
            self._timestamps.append(ts)
            self.epoch_labels.append(epoch_label)
            self.average_functions = None
            self.average_functions_mep = None
            self._n_epoch += 1
            self.updateCounter.emit(self._n_epoch)
            self.labelsChanged.emit()
            self._emit_label_count_warning_if_needed()

            if self.use_eeg and (self.average_data or self.average_tep_data):
                recreated = self._ensure_average_functions(which="TEPs")
                TEPs2plot = self.transform_eeg_epoch(eeg_epoch)
                if not recreated:
                    self.update_average_functions(TEPs2plot)
            
            if self.average_mep_data:
                recreated = self._ensure_average_functions(which="MEPs")
                emg = self._emg_from_other_epoch(other_epoch)
                if not recreated:
                    self.update_average_functions(emg, which="MEPs")

            self.newDataProcessed.emit()        # --> plot_updater

    def delete_epoch(self, n_delete):
        """
        n_delete - номер эпохи для удаления
        """
        if n_delete < 1 or n_delete > len(self._epochs):
            return

        self._n_epoch -= 1
        self.updateCounter.emit(self._n_epoch)

        del self._epochs[n_delete-1]                     # минус один для учёта нумерации с нуля
        del self._timestamps[n_delete-1]
        del self._raw_epochs[n_delete-1]
        del self._raw_timestamps[n_delete-1]
        del self._raw_epoch_labels[n_delete-1]
        del self.epoch_labels[n_delete-1]
        if self.use_eeg and n_delete <= len(self._eeg_epochs):
            del self._eeg_epochs[n_delete-1]
            del self._eeg_timestamps[n_delete-1]
        if n_delete <= len(self._other_epochs):
            del self._other_epochs[n_delete-1]
            del self._other_timestamps[n_delete-1]

        if self.use_eeg and (self.average_data or self.average_tep_data):
            self.create_average_functions(which="TEPs")
        if self.average_mep_data:
            self.create_average_functions(which="MEPs")
        
        self.newDataProcessed.emit()        # --> plot_updater

    def add_epoch_label(self, label, source=LABEL_SOURCE_EXTERNAL):
        source = self._normalize_label_source(source)
        label = self._normalize_epoch_label(label)
        if not label:
            self._emit_label_warning("empty_label", "Empty epoch label ignored")
            return
        self._known_epoch_labels.add(label)
        self._pending_epoch_labels[source].append(label)
        self.labelsChanged.emit()

    def set_epoch_label_source(self, source):
        source = self._normalize_label_source(source)
        if self.epoch_label_source == source:
            return
        self.epoch_label_source = source
        self.average_functions = None
        self.average_functions_mep = None

    def set_epoch_label_filter(self, label):
        labels = label if isinstance(label, (list, tuple, set)) else [label]
        labels = [self._normalize_epoch_label(item) for item in labels]
        labels = [item for item in labels if item]
        if not labels or LABEL_ALL in labels:
            labels = [LABEL_ALL]

        if self.epoch_label_filters == labels:
            return
        self.epoch_label_filters = labels
        self.epoch_label_filter = LABEL_ALL if labels == [LABEL_ALL] else labels[0]
        self.average_functions = None
        self.average_functions_mep = None

    def available_epoch_labels(self):
        labels = sorted({label for label in self.epoch_labels if label} | self._known_epoch_labels)
        if LABEL_NOT_LABELED in labels:
            labels.remove(LABEL_NOT_LABELED)
            labels.append(LABEL_NOT_LABELED)
        return labels

    def selected_epoch_labels(self):
        if self.epoch_label_filters == [LABEL_ALL]:
            return self.available_epoch_labels()
        return list(self.epoch_label_filters)

    def displayed_epoch_count(self):
        return sum(1 for i in range(self._n_epoch) if self._label_matches_filter(i))

    def epoch_label_counts(self):
        counts = {}
        for label in self.epoch_labels:
            counts[label] = counts.get(label, 0) + 1
        return counts

    def _consume_epoch_label(self):
        queue = self._pending_epoch_labels.get(self.epoch_label_source, [])
        if queue:
            return queue.pop(0)
        return LABEL_NOT_LABELED

    def _normalize_label_source(self, source):
        source = str(source or "").strip()
        if source in (LABEL_SOURCE_STIMULUS, LABEL_SOURCE_EXTERNAL):
            return source
        self._emit_label_warning(f"unknown_label_source_{source}", f"Unknown epoch label source '{source}', using stimulus")
        return LABEL_SOURCE_STIMULUS

    @staticmethod
    def _normalize_epoch_label(label):
        if label is None:
            return ""
        return str(label).strip()

    def _label_matches_filter(self, index, labels=None):
        labels = self.epoch_label_filters if labels is None else labels
        labels = list(labels) if isinstance(labels, (list, tuple, set)) else [labels]
        if LABEL_ALL in labels:
            return True
        if index < 0 or index >= len(self.epoch_labels):
            return False
        return self.epoch_labels[index] in labels

    def _emit_label_count_warning_if_needed(self):
        if len(self.epoch_labels) == self._n_epoch:
            return
        self._emit_label_warning(
            f"label_count_{len(self.epoch_labels)}_{self._n_epoch}",
            f"Epoch labels count ({len(self.epoch_labels)}) does not match epochs count ({self._n_epoch})",
        )

    def _emit_label_warning(self, key, message):
        if key in self._label_warnings_seen:
            return
        self._label_warnings_seen.add(key)
        self.labelWarning.emit(message)
        warnings.warn(message, RuntimeWarning, stacklevel=2)

    def update_average_functions(self, TEPs, which="TEPs"):
        """add new epoch"""
        if which == "TEPs":
            for i, ch_data in enumerate(TEPs):
                avg_funcs = self.average_functions[i]
                for j in range(min(len(avg_funcs), len(ch_data))):
                    avg_funcs[j].add(ch_data[j])
        else:   # MEPs
            avg_funcs = self.average_functions_mep
            for j in range(min(len(avg_funcs), len(TEPs))):
                avg_funcs[j].add(TEPs[j])

    def calculate_avg_TEP(self):
        """calculate averaged value based on current data"""
        self._ensure_average_functions(which="TEPs")
        data_aver = []
        for avg_funcs in self.average_functions:
            average_TEPs = [self._nan_if_empty(f.calculate()) for f in avg_funcs]
            data_aver.append(average_TEPs)
        return np.array(data_aver)
    
    def calculate_avg_MEP(self):
        """calculate averaged value based on current data"""
        self._ensure_average_functions(which="MEPs")
        data_aver = [self._nan_if_empty(f.calculate()) for f in self.average_functions_mep]
        return np.array(data_aver)

    def calculate_avg_MEP_stats(self):
        emg_epochs = self._mep_average_window(self.get_emg_epochs())
        if emg_epochs.size == 0:
            return np.array([]), np.array([])
        ddof = 1 if emg_epochs.shape[0] > 1 else 0
        return np.mean(emg_epochs, axis=0), np.std(emg_epochs, axis=0, ddof=ddof)

    # --- Конфигурация фильтров ---

    def configure_sampling(self):
        processing = self.settings.processing_settings
        source_fs = float(getattr(processing, "current_sampling_rate_Hz", 0) or 0)
        if source_fs <= 0:
            self._warn_once("sampling_source", f"Invalid current sampling rate {source_fs}; using 1 Hz")
            source_fs = 1.0

        self._source_sampling_rate_Hz = source_fs
        self._resampling_enabled = bool(getattr(processing, "do_resampling", False))
        resample_fs = float(getattr(processing, "resample_freq_Hz", 0) or 0)
        if self._resampling_enabled and resample_fs <= 0:
            self._warn_once("sampling_target", f"Invalid resampling rate {resample_fs}; resampling disabled")
            self._resampling_enabled = False

        self._resample_freq_Hz = resample_fs if resample_fs > 0 else source_fs
        self._sampling_rate_Hz = self._resample_freq_Hz if self._resampling_enabled else self._source_sampling_rate_Hz
        self._ms_to_sample = lambda x: int(x / 1000 * self._sampling_rate_Hz)
        self._n_samples = self._ms_to_sample(self._epoch_window_duration_ms())
        self._time_shift = self._ms_to_sample(0 - self._epoch_window_start_ms())

        self.configure_emg_processing(rebuild=False)
        self._rebuild_processed_epochs_from_raw()
        self.average_functions = None
        self.average_functions_mep = None

    def configure_baseline(self, enabled=True, t_from=-75, t_to=-20, method="mean"):
        self._baseline_enabled = enabled
        if enabled:
            ind_from = self._time_shift + self._ms_to_sample(t_from)
            ind_to = self._time_shift + self._ms_to_sample(t_to)
            ind_from = max(0, min(self._n_samples, ind_from))
            ind_to = max(0, min(self._n_samples, ind_to))
            if ind_from >= ind_to:
                self._warn_once(
                    f"baseline_{t_from}_{t_to}_{self._n_samples}",
                    f"Baseline interval [{t_from}, {t_to}] ms is outside the current epoch; baseline disabled",
                )
                self._baseline = lambda x: x
                return
            func = np.mean if method == "mean" else np.median
            self._baseline = lambda x: x - func(x[:, ind_from:ind_to], axis=1, keepdims=True)
        else:
            self._baseline = lambda x: x

    def configure_highpass(self, enabled=False, freq=1, Fs=None):
        self._highpass_filter = self._make_filter(
            enabled=enabled,
            freq=freq,
            Fs=Fs,
            btype="highpass",
            warning_key="highpass",
        )

    def configure_lowpass(self, enabled=True, freq=250, Fs=None):
        self._lowpass_filter = self._make_filter(
            enabled=enabled,
            freq=freq,
            Fs=Fs,
            btype="lowpass",
            warning_key="lowpass",
        )

    def configure_emg_processing(self, rebuild=True):
        processing = self.settings.processing_settings
        source_fs = float(self._source_sampling_rate_Hz or 0)
        if source_fs <= 0:
            self._warn_once("emg_sampling_source", f"Invalid EMG source sampling rate {source_fs}; using 1 Hz")
            source_fs = 1.0

        self._emg_resampling_enabled = bool(getattr(processing, "do_emg_resampling", True))
        emg_resample_fs = float(getattr(processing, "emg_resample_freq_Hz", 2000) or 0)
        if self._emg_resampling_enabled and emg_resample_fs <= 0:
            self._warn_once("emg_sampling_target", f"Invalid EMG resampling rate {emg_resample_fs}; resampling disabled")
            self._emg_resampling_enabled = False

        self._emg_resample_freq_Hz = emg_resample_fs if emg_resample_fs > 0 else source_fs
        self._other_sampling_rate_Hz = self._emg_resample_freq_Hz if self._emg_resampling_enabled else source_fs
        self._other_ms_to_sample = lambda x: int(x / 1000 * self._other_sampling_rate_Hz)
        self._other_n_samples = self._other_ms_to_sample(self._epoch_window_duration_ms())
        self._other_time_shift = self._other_ms_to_sample(0 - self._epoch_window_start_ms())

        self._emg_highpass_filter = self._make_filter(
            enabled=bool(getattr(processing, "do_emg_highpass_filtering", True)),
            freq=float(getattr(processing, "emg_highpass_freq_Hz", 10)),
            Fs=self._other_sampling_rate_Hz,
            btype="highpass",
            warning_key="emg_highpass",
        )
        self._emg_lowpass_filter = self._make_filter(
            enabled=bool(getattr(processing, "do_emg_lowpass_filtering", True)),
            freq=float(getattr(processing, "emg_lowpass_freq_Hz", 1000)),
            Fs=self._other_sampling_rate_Hz,
            btype="lowpass",
            warning_key="emg_lowpass",
        )
        self._emg_baseline = self._make_baseline(
            enabled=bool(getattr(processing, "do_emg_baseline_correction", True)),
            t_from=float(getattr(processing, "emg_baseline_from_ms", -75)),
            t_to=float(getattr(processing, "emg_baseline_to_ms", -20)),
            Fs=self._other_sampling_rate_Hz,
            n_samples=self._other_n_samples,
            time_shift=self._other_time_shift,
            method="mean",
            warning_key="emg_baseline",
        )
        self._emg_transform = lambda x: self._emg_baseline(
            self._emg_lowpass_filter(
                self._emg_highpass_filter(x)
            )
        )

        self.average_functions_mep = None
        if rebuild:
            self._rebuild_processed_epochs_from_raw()

    def _make_filter(self, enabled=True, freq=250, Fs=None, btype="lowpass", warning_key="filter"):
        if not enabled:
            return lambda x: x

        Fs = float(Fs or self._sampling_rate_Hz or 0)
        freq = float(freq or 0)
        nyquist = Fs / 2
        if Fs <= 0 or freq <= 0:
            self._warn_once(
                f"{warning_key}_{Fs}_{freq}",
                f"{btype} filter disabled: frequency {freq:g} Hz is invalid for Fs={Fs:g} Hz",
            )
            return lambda x: x

        if freq >= nyquist:
            if btype == "lowpass":
                if freq > nyquist:
                    self._warn_once(
                        f"{warning_key}_clamped_{Fs}_{freq}",
                        f"{btype} filter frequency {freq:g} Hz is above Nyquist for Fs={Fs:g} Hz; clamped below Nyquist",
                    )
                normalized_freq = np.nextafter(1.0, 0.0)
            else:
                self._warn_once(
                    f"{warning_key}_{Fs}_{freq}",
                    f"{btype} filter disabled: frequency {freq:g} Hz is invalid for Fs={Fs:g} Hz",
                )
                return lambda x: x
        else:
            normalized_freq = freq / nyquist
        sos = signal.butter(2, normalized_freq, btype=btype, output='sos')
        return lambda x: signal.sosfilt(sos, x, axis=1)

    def _make_baseline(self, enabled=True, t_from=-75, t_to=-20, Fs=None, n_samples=None, time_shift=None, method="mean", warning_key="baseline"):
        if not enabled:
            return lambda x: x

        Fs = float(Fs or self._sampling_rate_Hz or 0)
        n_samples = int(n_samples if n_samples is not None else self._n_samples)
        time_shift = int(time_shift if time_shift is not None else self._time_shift)
        ms_to_sample = lambda x: int(x / 1000 * Fs)
        ind_from = time_shift + ms_to_sample(t_from)
        ind_to = time_shift + ms_to_sample(t_to)
        ind_from = max(0, min(n_samples, ind_from))
        ind_to = max(0, min(n_samples, ind_to))
        if Fs <= 0 or ind_from >= ind_to:
            self._warn_once(
                f"{warning_key}_{t_from}_{t_to}_{n_samples}_{Fs}",
                f"Baseline interval [{t_from}, {t_to}] ms is outside the current epoch; baseline disabled",
            )
            return lambda x: x

        func = np.mean if method == "mean" else np.median
        return lambda x: x - func(x[:, ind_from:ind_to], axis=1, keepdims=True)

    def configure_rereference(self, enabled=False, channels=None):
        if enabled and channels:
            missing = [ch for ch in channels if ch not in self.settings.channels]
            if missing:
                self._warn_once(
                    f"reref_missing_{tuple(missing)}",
                    f"Rereference disabled: unknown channels {missing}",
                )
                self._referef = lambda x: x
                return
            idx = [self.settings.channels.index(ch) for ch in channels]
            self._referef = lambda x: x - np.mean(x[idx, :], axis=0, keepdims=True)
        else:
            self._referef = lambda x: x

    def configure_car(self, enabled=False, channels=None):
        if not enabled:
            self._car = lambda x: x
            return

        except_channels = set(channels or [])
        missing = [ch for ch in except_channels if ch not in self.settings.channels]
        if missing:
            self._warn_once(
                f"car_except_missing_{tuple(missing)}",
                f"CAR ignored unknown excluded channels {missing}",
            )

        include_mask = np.array([ch not in except_channels for ch in self.settings.channels])
        n_included = int(include_mask.sum())
        if n_included == 0:
            self._warn_once("car_empty", "CAR disabled: no channels left after exclusions")
            self._car = lambda x: x
            return

        self._car = lambda x: x - np.mean(x[include_mask, :], axis=0, keepdims=True)

    # --- Создание полного пайплайна ---

    def create_full_transform(self):
        self._transform = lambda x: self._referef(
            self._car(
                self._baseline(
                    self._lowpass_filter(
                        self._highpass_filter(x)
                    )
                )
            )
        )
    
    
    # --- Усреднение ---
    def get_eeg_epochs(self, filter_by_label=True, labels=None):
        if not self.use_eeg:
            return np.empty((0, len(self.settings.channels), self._n_samples))
        epochs = self._current_length_eeg_epochs(filter_by_label=filter_by_label, labels=labels)
        if len(epochs) == 0:
            return np.empty((0, len(self.settings.channels), self._n_samples))
        return np.stack([
            self.transform_eeg_epoch(TEPs)
            for TEPs in epochs
        ], axis=0)

    def get_eeg_epoch(self, epoch):
        """Return the EEG part of an epoch in volts: the first configured EEG channels."""
        if epoch is None:
            raise ValueError("Expected EEG epoch, got None")
        epoch = np.asarray(epoch, dtype=float)
        if epoch.ndim != 2:
            raise ValueError(f"Expected epoch with shape [n_channels, n_samples], got {epoch.shape}")

        n_eeg = len(self.settings.channels)
        if epoch.shape[0] < n_eeg:
            raise ValueError(f"Expected at least {n_eeg} EEG channels, got {epoch.shape[0]}")

        return epoch[:n_eeg, :]

    def transform_eeg_epoch(self, epoch):
        """Extract configured EEG channels and apply the TEP processing pipeline."""
        return self._transform(self.get_eeg_epoch(epoch) * 1e6)
    
    def get_emg_epochs(self, filter_by_label=True, labels=None):
        epochs = self._current_length_other_epochs(filter_by_label=filter_by_label, labels=labels)
        if len(epochs) == 0:
            return np.empty((0, self._other_n_samples))
        emg_epochs = np.stack([
            self._emg_from_other_epoch(epoch)
            for epoch in epochs
        ], axis=0)
        return emg_epochs

    def get_processed_emg_channel_epochs(self, filter_by_label=True, labels=None):
        epochs = self._current_length_other_epochs(filter_by_label=filter_by_label, labels=labels)
        if len(epochs) == 0:
            n_channels = self._expected_other_channels()
            return np.empty((0, n_channels, self._other_n_samples))
        return np.stack([
            np.asarray(epoch, dtype=float)
            for epoch in epochs
        ], axis=0)

    def _mep_average_window(self, data):
        if self._aver_all:
            return data
        return data[-self._n_aver_max:]

    def create_average_functions(self, which="TEPs"):
        """Создать функции для усреднения TEPs"""
        function = self.aver_empty_func[self.aver_method]   # пустой трафарет
        
        if which == 'TEPs' and not self.use_eeg:
            self.average_functions = None
            return

        if self._n_epoch != 0:
            if which == 'TEPs':
                data = self.get_eeg_epochs()
                n_samples = data.shape[-1] if data.ndim == 3 else self._n_samples
                self._sync_n_samples(n_samples)
                self.average_functions = [
                    [function(data[:, i, j], self._n_aver_max, self._aver_all)
                    for j in range(self._n_samples)]
                    for i in range(len(self.settings.channels))
                ]
            else:
                data = self.get_emg_epochs()
                n_samples = data.shape[1] if data.ndim == 2 else self._n_samples
                self.average_functions_mep = [
                    function(data[:, j], self._n_aver_max, self._aver_all)
                    for j in range(n_samples)
                ]
        else:
            if which == 'TEPs':
                self.average_functions = [
                    [function([], self._n_aver_max, self._aver_all)
                    for _ in range(self._n_samples)]
                    for _ in range(len(self.settings.channels))
                ]
            else:
                n_samples = self._expected_mep_samples()
                self.average_functions_mep = [
                        function([], self._n_aver_max, self._aver_all)
                        for j in range(n_samples)
                    ]

    def _ensure_average_functions(self, which="TEPs"):
        if which == "TEPs":
            if not self.use_eeg:
                self.average_functions = None
                return False
            needs_create = (
                not self.average_functions
                or len(self.average_functions) != len(self.settings.channels)
                or any(len(avg_funcs) != self._n_samples for avg_funcs in self.average_functions)
            )
        else:
            n_samples = self._expected_mep_samples()
            needs_create = (
                not self.average_functions_mep
                or len(self.average_functions_mep) != n_samples
            )

        if needs_create:
            self.create_average_functions(which=which)
        return needs_create

    def _expected_mep_samples(self):
        if len(self._other_epochs) == 0:
            return self._other_n_samples
        return int(np.asarray(self._other_epochs[-1]).shape[-1])

    def _expected_other_channels(self):
        if self._other_epochs:
            return int(np.asarray(self._other_epochs[-1]).shape[0])
        if self._raw_epochs:
            n_raw = int(np.asarray(self._raw_epochs[-1]).shape[0])
            if self.use_eeg:
                return max(0, n_raw - len(self.settings.channels))
            return n_raw
        return 0

    def _sync_epoch_shape(self, epoch):
        self._sync_n_samples(int(np.asarray(epoch).shape[-1]))

    def _sync_other_epoch_shape(self, epoch):
        if epoch is None:
            return
        self._sync_other_n_samples(int(np.asarray(epoch).shape[-1]))

    def _prepare_epoch(self, epoch):
        return self._prepare_eeg_epoch(epoch)

    def _prepare_eeg_epoch(self, epoch):
        if epoch is None:
            return None
        epoch = np.asarray(epoch, dtype=float)
        if self._resampling_enabled and self._source_sampling_rate_Hz != self._sampling_rate_Hz:
            epoch = self._resample_epoch(epoch)

        return epoch

    def _prepare_emg_epoch(self, epoch):
        if epoch is None:
            return None
        epoch = np.asarray(epoch, dtype=float)
        if self._emg_resampling_enabled and self._source_sampling_rate_Hz != self._other_sampling_rate_Hz:
            epoch = self._resample_epoch_to(epoch, self._source_sampling_rate_Hz, self._other_sampling_rate_Hz, "emg_resample")
        return self._emg_transform(epoch)

    def _split_epoch(self, epoch):
        epoch = np.asarray(epoch, dtype=float)
        n_eeg = len(self.settings.channels)
        if self.use_eeg:
            eeg_epoch = epoch[:n_eeg, :]
            other_epoch = epoch[n_eeg:, :]
        else:
            eeg_epoch = None
            other_epoch = epoch
        return eeg_epoch, other_epoch

    def _validate_epoch(self, epoch):
        try:
            epoch = np.asarray(epoch, dtype=float)
        except (TypeError, ValueError) as exc:
            self._warn_once("epoch_convert", f"Epoch skipped: cannot convert to numeric array ({exc})")
            return None

        if epoch.ndim != 2:
            self._warn_once(f"epoch_ndim_{epoch.ndim}", f"Epoch skipped: expected 2D [channels, samples], got {epoch.shape}")
            return None

        n_channels, n_samples = epoch.shape
        if n_channels < 2:
            self._warn_once(f"epoch_channels_{n_channels}", f"Epoch skipped: expected at least 2 channels, got {n_channels}")
            return None

        n_eeg = len(self.settings.channels)
        if self.use_eeg and n_channels < n_eeg:
            self._warn_once(
                f"epoch_eeg_channels_{n_channels}_{n_eeg}",
                f"Epoch skipped: EEG processing expects at least {n_eeg} channels, got {n_channels}",
            )
            return None

        expected_source_samples = self._expected_samples(self._source_sampling_rate_Hz)
        if expected_source_samples > 0 and n_samples != expected_source_samples:
            self._warn_once(
                f"epoch_source_samples_{n_samples}_{expected_source_samples}",
                f"Epoch sample count {n_samples} does not match window/Fs expectation {expected_source_samples}",
            )

        return epoch

    def _resample_epoch(self, epoch):
        return self._resample_epoch_to(epoch, self._source_sampling_rate_Hz, self._sampling_rate_Hz, "resample")

    def _resample_epoch_to(self, epoch, source_fs, target_fs, warning_key):
        source_fs = float(source_fs)
        target_fs = float(target_fs)
        if source_fs <= 0 or target_fs <= 0:
            self._warn_once(f"{warning_key}_invalid_fs", f"Resampling skipped: source Fs={source_fs}, target Fs={target_fs}")
            return epoch

        n_samples = int(epoch.shape[1])
        target_samples = int(round(n_samples * target_fs / source_fs))
        if target_samples <= 0:
            self._warn_once(f"{warning_key}_empty", f"Resampling skipped: computed {target_samples} output samples")
            return epoch

        return signal.resample(epoch, target_samples, axis=1)

    def _expected_samples(self, fs):
        fs = float(fs or 0)
        if fs <= 0:
            return 0
        return int(self._epoch_window_duration_ms() / 1000 * fs)

    def _epoch_window_start_ms(self):
        return float(getattr(self.settings.processing_settings, "epoch_window_start_ms", -100))

    def _epoch_window_end_ms(self):
        return float(getattr(self.settings.processing_settings, "epoch_window_end_ms", 500))

    def _epoch_window_duration_ms(self):
        duration = self._epoch_window_end_ms() - self._epoch_window_start_ms()
        if duration <= 0:
            self._warn_once("epoch_window_invalid", f"Invalid processing epoch window duration {duration} ms; using 1 ms")
            return 1.0
        return duration

    def _sync_n_samples(self, n_samples):
        if n_samples <= 0:
            self._warn_once(f"epoch_empty_{n_samples}", f"Epoch has invalid sample count {n_samples}")
            return
        expected_samples = self._expected_samples(self._sampling_rate_Hz)
        if expected_samples > 0 and n_samples != expected_samples:
            self._warn_once(
                f"epoch_effective_samples_{n_samples}_{expected_samples}",
                f"Effective epoch sample count {n_samples} does not match current processing expectation {expected_samples}",
            )
        if n_samples == self._n_samples:
            return
        self._n_samples = n_samples
        self.average_functions = None
        self.average_functions_mep = None

    def _sync_other_n_samples(self, n_samples):
        if n_samples <= 0:
            self._warn_once(f"other_epoch_empty_{n_samples}", f"Non-EEG epoch has invalid sample count {n_samples}")
            return
        expected_samples = self._expected_samples(self._other_sampling_rate_Hz)
        if expected_samples > 0 and n_samples != expected_samples:
            self._warn_once(
                f"other_epoch_samples_{n_samples}_{expected_samples}",
                f"Non-EEG epoch sample count {n_samples} does not match source window/Fs expectation {expected_samples}",
            )
        if n_samples == self._other_n_samples:
            return
        self._other_n_samples = n_samples
        self.average_functions_mep = None

    def _warn_once(self, key, message):
        if key in self._warnings_seen:
            return
        self._warnings_seen.add(key)
        warnings.warn(message, RuntimeWarning, stacklevel=2)

    @staticmethod
    def _nan_if_empty(value):
        return np.nan if value is None else value

    @property
    def effective_sampling_rate_Hz(self):
        return self._sampling_rate_Hz

    @property
    def mep_sampling_rate_Hz(self):
        return self._other_sampling_rate_Hz

    def configure_use_eeg(self, enabled=True):
        self.use_eeg = bool(enabled)
        if not self.use_eeg:
            self.average_functions = None
            self.average_tep_data = False
        self._rebuild_processed_epochs_from_raw()

    def _current_length_epochs(self):
        return [epoch for epoch, _ in self._current_length_epoch_records()]

    def _current_length_epoch_records(self):
        expected = self._n_samples if self.use_eeg else self._other_n_samples
        return [
            (epoch, ts)
            for epoch, ts in zip(self._epochs, self._timestamps)
            if int(np.asarray(epoch).shape[-1]) == expected
        ]

    def _current_length_eeg_epochs(self, filter_by_label=True, labels=None):
        return [
            epoch
            for i, epoch in enumerate(self._eeg_epochs)
            if int(np.asarray(epoch).shape[-1]) == self._n_samples
            and (not filter_by_label or self._label_matches_filter(i, labels=labels))
        ]

    def _current_length_other_epochs(self, filter_by_label=True, labels=None):
        return [
            epoch
            for i, epoch in enumerate(self._other_epochs)
            if int(np.asarray(epoch).shape[-1]) == self._other_n_samples
            and (not filter_by_label or self._label_matches_filter(i, labels=labels))
        ]

    def get_other_epoch(self, index=-1, filter_by_label=False):
        epochs = self._filtered_other_epochs() if filter_by_label else self._other_epochs
        if not epochs:
            return None
        return epochs[index]

    def get_eeg_epoch_by_index(self, index=-1, filter_by_label=False):
        epochs = self._filtered_eeg_epochs() if filter_by_label else self._eeg_epochs
        if not self.use_eeg or not epochs:
            return None
        return epochs[index]

    def _filtered_eeg_epochs(self):
        return [
            epoch
            for i, epoch in enumerate(self._eeg_epochs)
            if self._label_matches_filter(i)
        ]

    def _filtered_other_epochs(self):
        return [
            epoch
            for i, epoch in enumerate(self._other_epochs)
            if self._label_matches_filter(i)
        ]

    def _emg_from_other_epoch(self, epoch, ch_a=-2, ch_b=-1):
        epoch = np.asarray(epoch, dtype=float)
        if epoch.ndim != 2 or epoch.shape[0] < 2:
            self._warn_once(
                f"mep_channels_{getattr(epoch, 'shape', None)}",
                "MEP signal is empty: at least 2 non-EEG channels are required",
            )
            n_samples = int(epoch.shape[-1]) if epoch.ndim == 2 else self._other_n_samples
            return np.full(max(0, n_samples), np.nan, dtype=float)

        n_channels = epoch.shape[0]
        ch_a = self._resolve_channel_index(ch_a, n_channels)
        ch_b = self._resolve_channel_index(ch_b, n_channels)
        if ch_a is None or ch_b is None:
            return np.full(int(epoch.shape[-1]), np.nan, dtype=float)
        return np.diff(epoch[[ch_a, ch_b], :] * 1e3, axis=0).flatten()

    @staticmethod
    def _resolve_channel_index(index, n_channels):
        index = int(index)
        if index < 0:
            index = n_channels + index
        if index < 0 or index >= n_channels:
            return None
        return index

    def raw_epoch_records(self):
        return list(zip(self._raw_epochs, self._raw_timestamps))

    def raw_epoch_label_records(self):
        return list(zip(self._raw_epochs, self._raw_timestamps, self._raw_epoch_labels))

    def processed_epoch_records(self):
            return list(zip(self.calculate_avg_TEP(), self._raw_timestamps))

    def _rebuild_processed_epochs_from_raw(self):
        self._eeg_epochs = []
        self._eeg_timestamps = []
        self._other_epochs = []
        self._other_timestamps = []
        processed_epochs = []
        processed_timestamps = []
        processed_labels = []

        if not self._raw_epochs:
            self._epochs = []
            self._timestamps = []
            self.epoch_labels = []
            self._n_epoch = 0
            self.updateCounter.emit(self._n_epoch)
            self.labelsChanged.emit()
            return

        if len(self._raw_epoch_labels) < len(self._raw_epochs):
            self._raw_epoch_labels.extend([LABEL_NOT_LABELED] * (len(self._raw_epochs) - len(self._raw_epoch_labels)))
        elif len(self._raw_epoch_labels) > len(self._raw_epochs):
            self._raw_epoch_labels = self._raw_epoch_labels[:len(self._raw_epochs)]

        for raw_epoch, ts, label in zip(self._raw_epochs, self._raw_timestamps, self._raw_epoch_labels):
            if self.use_eeg and np.asarray(raw_epoch).shape[0] < len(self.settings.channels):
                self._warn_once(
                    f"rebuild_eeg_channels_{np.asarray(raw_epoch).shape[0]}",
                    f"Stored epoch skipped for EEG processing: expected at least {len(self.settings.channels)} channels, got {np.asarray(raw_epoch).shape[0]}",
                )
                continue
            eeg_epoch, other_epoch = self._split_epoch(raw_epoch)
            other_epoch = self._prepare_emg_epoch(other_epoch)
            self._sync_other_epoch_shape(other_epoch)
            if self.use_eeg:
                eeg_epoch = self._prepare_eeg_epoch(eeg_epoch)
                if eeg_epoch is None:
                    continue
                self._sync_epoch_shape(eeg_epoch)
                self._eeg_epochs.append(eeg_epoch)
                self._eeg_timestamps.append(ts)
                display_epoch = eeg_epoch
            else:
                display_epoch = other_epoch
            self._other_epochs.append(other_epoch)
            self._other_timestamps.append(ts)
            processed_epochs.append(display_epoch)
            processed_timestamps.append(ts)
            processed_labels.append(label)

        self._epochs = processed_epochs
        self._timestamps = processed_timestamps
        self.epoch_labels = processed_labels
        self._n_epoch = len(processed_epochs)
        self.updateCounter.emit(self._n_epoch)
        self.labelsChanged.emit()
        self._emit_label_count_warning_if_needed()
    
    def update_avg_mep(self, do_average):
        self.average_mep_data = do_average
        self.create_average_functions(which="MEPs")
    
    def update_avg_tep(self, do_average):
        self.average_tep_data = bool(do_average) and self.use_eeg
        if not self.average_data:
            self.create_average_functions(which="TEPs")
    

    def cut_mep_epoch(self, mep_epoch, xmin_ms, xmax_ms):
        x_min = self._other_time_shift + self._other_ms_to_sample(xmin_ms)
        x_max = self._other_time_shift + self._other_ms_to_sample(xmax_ms)
        x_min = max(0, int(x_min))
        x_max = max(x_min, int(x_max))
        return mep_epoch[x_min:x_max]

    # --- Применение трансформации к данным ---

    def apply_transform(self, data):
        """Применить весь пайплайн к данным"""
        return self._transform(data)

    # --- Сброс сессий ---

    def reset_sessions(self):
        self._raw_epochs = []
        self._raw_timestamps = []
        self._raw_epoch_labels = []
        self._eeg_epochs = []
        self._eeg_timestamps = []
        self._other_epochs = []
        self._other_timestamps = []
        self._epochs = []
        self._timestamps = []
        self.epoch_labels = []
        self._pending_epoch_labels = {
            LABEL_SOURCE_STIMULUS: [],
            LABEL_SOURCE_EXTERNAL: [],
        }
        self._known_epoch_labels = set()
        
        self._n_epoch = 0
        self.updateCounter.emit(self._n_epoch)
        self.labelsChanged.emit()

        self.average_functions = None
        self.average_functions_mep = None

        if self.use_eeg and (self.average_data or self.average_tep_data):
            self.create_average_functions(which="TEPs")
        if self.average_mep_data:
            self.create_average_functions(which="MEPs")
