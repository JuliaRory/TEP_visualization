import math

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt
from scipy.ndimage import median_filter
from PyQt5.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils.ui_helpers import create_button, create_spin_box


DEFAULT_BCI_MEP_BINS = [
    {"name": "-400", "from_ms": -500, "to_ms": -250},
    {"name": "-200", "from_ms": -250, "to_ms": -150},
    {"name": "-100", "from_ms": -150, "to_ms": -75},
    {"name": "-50", "from_ms": -75, "to_ms": -25},
    {"name": "0", "from_ms": -25, "to_ms": 25},
]


class BCIMEPDelayWindow(QWidget):
    def __init__(self, settings, speed_settings=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.settings = settings
        self.speed_settings = speed_settings
        self._latest_processor = None
        self._latest_epoch_index = 0
        self._last_added_epoch_index = 0
        self._last_added_epoch_id = None
        self._latest_result = None
        self._all_delays = []
        self._bin_values = [[] for _ in self._bin_settings()]
        self._updating_table = False

        self.setWindowTitle("BCI MEP delays")
        self.resize(1250, 850)

        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        self._sync_table_from_settings()
        self._plot_empty()

    def _setup_ui(self):
        self._controls_frame = QFrame(self)

        self._label_epoch = QLabel("Epoch: -", self)
        self._label_epoch_len = QLabel("Epoch duration: -", self)
        self._label_delay = QLabel("delay: -", self)
        self._label_delay.setAlignment(Qt.AlignCenter)
        self._label_delay.setStyleSheet("font-size: 42px; font-weight: 700;")

        self._button_refresh = create_button("Обновить", parent=self)
        self._button_clear = create_button("Очистить", parent=self)
        self._button_add_bin = create_button("Добавить бин", parent=self)

        self._spin_threshold = create_spin_box(
            0.0,
            1e6,
            float(getattr(self.settings, "bci_mep_threshold", 4.0)),
            data_type="float",
            step=0.1,
            decimals=6,
            parent=self,
            w=95,
        )
        self._spin_threshold_scale = create_spin_box(
            -30,
            9,
            int(getattr(self.settings, "bci_mep_threshold_scale", -9)),
            parent=self,
            w=70,
        )
        self._spin_mep_ymax = create_spin_box(
            0.001,
            1000.0,
            float(getattr(self.settings, "bci_mep_plot_ymax_mV", 0.5)),
            data_type="float",
            step=0.05,
            decimals=3,
            parent=self,
            w=90,
        )
        self._spin_tkeo_scale = create_spin_box(
            -30,
            9,
            int(getattr(self.settings, "bci_mep_tkeo_scale", -8)),
            parent=self,
            w=70,
        )
        self._spin_tkeo_ymax = create_spin_box(
            0.001,
            1e9,
            float(getattr(self.settings, "bci_mep_tkeo_ymax", 1.0)),
            data_type="float",
            step=0.1,
            decimals=6,
            parent=self,
            w=90,
        )
        self._check_remove_trend = QCheckBox("Remove slow trend", self)
        self._check_remove_trend.setChecked(bool(getattr(self.settings, "bci_mep_remove_trend", True)))
        self._spin_trend_window_ms = create_spin_box(
            1.0,
            1000.0,
            float(getattr(self.settings, "bci_mep_trend_window_ms", 100.0)),
            data_type="float",
            step=5.0,
            decimals=1,
            parent=self,
            w=90,
        )

        self._table = QTableWidget(0, 5, self)
        self._table.setHorizontalHeaderLabels(["Название бина", "N", "от, мс", "до, мс", "задержки"])
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)

        self.figure = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)

        self.summary_figure = Figure(figsize=(4.2, 3.2), dpi=100)
        self.summary_canvas = FigureCanvas(self.summary_figure)

    def _setup_layout(self):
        scale_grid = QGridLayout()
        scale_grid.addWidget(QLabel("TKEO threshold", self), 0, 0)
        scale_grid.addWidget(self._spin_threshold, 0, 1)
        scale_grid.addWidget(QLabel("x 10^", self), 0, 2)
        scale_grid.addWidget(self._spin_threshold_scale, 0, 3)
        scale_grid.addWidget(QLabel("MEP ymax, mV", self), 1, 0)
        scale_grid.addWidget(self._spin_mep_ymax, 1, 1)
        scale_grid.addWidget(QLabel("TKEO ymax", self), 2, 0)
        scale_grid.addWidget(self._spin_tkeo_ymax, 2, 1)
        scale_grid.addWidget(QLabel("x 10^", self), 2, 2)
        scale_grid.addWidget(self._spin_tkeo_scale, 2, 3)
        scale_grid.addWidget(self._check_remove_trend, 3, 0, 1, 2)
        scale_grid.addWidget(QLabel("trend ms", self), 3, 2)
        scale_grid.addWidget(self._spin_trend_window_ms, 3, 3)

        controls_layout = QVBoxLayout(self._controls_frame)
        controls_layout.addWidget(self._label_epoch)
        controls_layout.addWidget(self._label_epoch_len)
        controls_layout.addWidget(self._label_delay)
        controls_layout.addLayout(scale_grid)
        controls_layout.addWidget(self._button_refresh)
        controls_layout.addWidget(self._table)
        controls_layout.addWidget(self.summary_canvas)
        controls_layout.addWidget(self._button_add_bin)
        controls_layout.addWidget(self._button_clear)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._controls_frame)
        splitter.addWidget(self.canvas)
        splitter.setSizes([430, 820])

        layout = QHBoxLayout(self)
        layout.addWidget(splitter)

    def _setup_connections(self):
        self._button_refresh.clicked.connect(self.clear_bins)
        self._button_clear.clicked.connect(self.clear_bins)
        self._button_add_bin.clicked.connect(self.add_bin)
        self._table.itemChanged.connect(self._on_table_item_changed)
        for spinbox in (
            self._spin_threshold,
            self._spin_threshold_scale,
            self._spin_mep_ymax,
            self._spin_tkeo_ymax,
            self._spin_tkeo_scale,
            self._spin_trend_window_ms,
        ):
            self._connect_plot_spinbox(spinbox)
        self._check_remove_trend.stateChanged.connect(self._on_settings_changed)

    def _connect_plot_spinbox(self, spinbox):
        spinbox.setKeyboardTracking(True)
        spinbox.valueChanged.connect(self._on_settings_changed)
        spinbox.editingFinished.connect(self._on_settings_changed)

    def _sync_table_from_settings(self):
        self._updating_table = True
        self._table.setRowCount(0)
        for row, bin_cfg in enumerate(self._bin_settings()):
            self._add_bin_row(row, bin_cfg)
        self._updating_table = False

        self._update_bin_table()

    def _add_bin_row(self, row, bin_cfg):
        self._table.insertRow(row)

        effective = self._effective_bin(bin_cfg)
        item_name = QTableWidgetItem(str(effective.get("name", "")))
        if self._is_auto_delay_bin(bin_cfg):
            item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
        self._table.setItem(row, 0, item_name)

        item_count = QTableWidgetItem("0")
        item_count.setFlags(item_count.flags() & ~Qt.ItemIsEditable)
        item_count.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row, 1, item_count)

        spin_from = create_spin_box(
            -5000,
            5000,
            int(effective.get("from_ms", 0)),
            parent=self._table,
            w=85,
        )
        spin_to = create_spin_box(
            -5000,
            5000,
            int(effective.get("to_ms", 0)),
            parent=self._table,
            w=85,
        )
        if self._is_auto_delay_bin(bin_cfg):
            spin_from.setDisabled(True)
            spin_to.setDisabled(True)
        spin_from.valueChanged.connect(lambda value, r=row: self._on_bin_changed(r, "from_ms", value))
        spin_to.valueChanged.connect(lambda value, r=row: self._on_bin_changed(r, "to_ms", value))
        self._table.setCellWidget(row, 2, spin_from)
        self._table.setCellWidget(row, 3, spin_to)

        item_values = QTableWidgetItem("")
        item_values.setFlags(item_values.flags() & ~Qt.ItemIsEditable)
        self._table.setItem(row, 4, item_values)

    def _bin_settings(self):
        bins = getattr(self.settings, "bci_mep_bins", None)
        if not bins:
            bins = [dict(bin_cfg) for bin_cfg in DEFAULT_BCI_MEP_BINS]
            self.settings.bci_mep_bins = bins
        self._ensure_standard_bins(bins)
        return bins

    def _ensure_standard_bins(self, bins):
        for idx, base in enumerate(DEFAULT_BCI_MEP_BINS):
            if idx >= len(bins):
                bins.append(dict(base))
            bins[idx].update(
                {
                    "name": base["name"],
                    "from_ms": base["from_ms"],
                    "to_ms": base["to_ms"],
                    "base_name_ms": int(base["name"]),
                    "base_from_ms": int(base["from_ms"]),
                    "base_to_ms": int(base["to_ms"]),
                    "auto_delay": True,
                }
            )

    def _current_delay_ms(self):
        return int(getattr(self.settings, "phases_delay_ms", 0))

    def _is_auto_delay_bin(self, bin_cfg):
        return bool(bin_cfg.get("auto_delay", False))

    def _effective_bin(self, bin_cfg):
        if not self._is_auto_delay_bin(bin_cfg):
            return bin_cfg

        delay_ms = self._current_delay_ms()
        name_ms = int(bin_cfg.get("base_name_ms", bin_cfg.get("name", 0))) + delay_ms
        from_ms = int(bin_cfg.get("base_from_ms", bin_cfg.get("from_ms", 0))) + delay_ms
        to_ms = int(bin_cfg.get("base_to_ms", bin_cfg.get("to_ms", 0))) + delay_ms
        return {"name": str(name_ms), "from_ms": from_ms, "to_ms": to_ms}

    def update_delay_from_settings(self):
        self._sync_table_from_settings()
        self._rebuild_bins()

    def add_bin(self):
        bins = self._bin_settings()
        row = len(bins)
        bin_cfg = {"name": f"bin {row + 1}", "from_ms": 0, "to_ms": 0, "auto_delay": False}
        bins.append(bin_cfg)
        self._bin_values.append([])
        self._add_bin_row(row, bin_cfg)
        self._update_bin_table()

    def _on_table_item_changed(self, item):
        if self._updating_table or item.column() != 0:
            return
        row = item.row()
        bins = self._bin_settings()
        if 0 <= row < len(bins) and not self._is_auto_delay_bin(bins[row]):
            bins[row]["name"] = item.text().strip() or f"bin {row + 1}"

    def update_from_processor(self, processor):
        self._latest_processor = processor
        self.speed_settings = getattr(processor.settings, "speed", self.speed_settings)
        n_epoch = int(getattr(processor, "_n_epoch", len(getattr(processor, "_epochs", []))))
        epoch = processor.get_other_epoch(-1) if hasattr(processor, "get_other_epoch") else None
        if n_epoch <= 0 or epoch is None:
            self._latest_epoch_index = 0
            self._latest_result = None
            self._label_epoch.setText("Epoch: -")
            self._label_epoch_len.setText("Epoch duration: -")
            self._label_delay.setText("delay: -")
            self._plot_empty()
            return

        epoch_id = id(epoch)
        add_to_bins = epoch_id != self._last_added_epoch_id
        self._latest_epoch_index = n_epoch
        self._process_epoch(processor, n_epoch, add_to_bins=add_to_bins)

    def clear_bins(self):
        self._all_delays = []
        self._bin_values = [[] for _ in self._bin_settings()]
        self._last_added_epoch_index = 0
        self._last_added_epoch_id = None
        self._update_bin_table()

    def _process_epoch(self, processor, n_epoch, add_to_bins):
        epoch = processor.get_other_epoch(-1) if hasattr(processor, "get_other_epoch") else None
        epoch = np.asarray(epoch, dtype=float)
        if epoch.ndim != 2 or epoch.shape[0] < 2:
            return

        mep_mV = np.diff(epoch[-2:, :] * 1e3, axis=0).flatten()
        time_ms = self._time_axis(processor, mep_mV.size)
        mep_mV = self._prepare_mep_signal(mep_mV, time_ms)
        tkeo = self._calculate_tkeo(mep_mV * 1e-3)

        threshold = self._threshold_value()
        delay_ms = -self._detect_delay(time_ms, tkeo, threshold)

        self._latest_result = {
            "time_ms": time_ms,
            "mep_mV": mep_mV,
            "tkeo": tkeo,
            "threshold": threshold,
            "delay_ms": delay_ms,
            "n_epoch": n_epoch,
        }

        x_start, x_end = self._x_limits()
        duration = float(x_end - x_start)
        self._label_epoch.setText(f"Epoch: #{n_epoch}")
        self._label_epoch_len.setText(
            f"Epoch duration: {duration:.1f} ms ({x_start:.1f}..{x_end:.1f} ms)"
        )

        if np.isfinite(delay_ms):
            self._label_delay.setText(f"{delay_ms:.1f} ms")
            if add_to_bins:
                self._all_delays.append(float(delay_ms))
                self._last_added_epoch_index = n_epoch
                self._last_added_epoch_id = id(epoch)
                self._rebuild_bins()
        else:
            self._label_delay.setText("delay: -")

        self._plot_result()

    def _time_axis(self, processor, n_samples):
        fs = float(getattr(processor, "mep_sampling_rate_Hz", 0) or 0)
        processing = getattr(processor.settings, "processing_settings", None)
        start_ms = float(getattr(processing, "epoch_window_start_ms", 0))
        end_ms = float(getattr(processing, "epoch_window_end_ms", start_ms))
        if fs > 0:
            return start_ms + np.arange(n_samples, dtype=float) * 1000.0 / fs
        return np.linspace(start_ms, end_ms, n_samples, endpoint=False)

    def _x_limits(self):
        processor = getattr(self, "_latest_processor", None)
        processing = getattr(getattr(processor, "settings", None), "processing_settings", None)
        start_ms = float(getattr(processing, "epoch_window_start_ms", -300))
        end_ms = float(getattr(processing, "epoch_window_end_ms", 300))
        if end_ms <= start_ms:
            end_ms = start_ms + 1.0
        return start_ms, end_ms

    def _prepare_mep_signal(self, mep_mV, time_ms):
        mep_mV = np.asarray(mep_mV, dtype=float)
        if not self._check_remove_trend.isChecked() or mep_mV.size < 3:
            return mep_mV

        dt_ms = self._sample_step_ms(time_ms)
        if not np.isfinite(dt_ms) or dt_ms <= 0:
            return mep_mV

        window_ms = max(float(self._spin_trend_window_ms.value()), dt_ms * 3)
        kernel = max(3, int(round(window_ms / dt_ms)))
        if kernel % 2 == 0:
            kernel += 1
        if kernel >= mep_mV.size:
            kernel = mep_mV.size - 1 if mep_mV.size % 2 == 0 else mep_mV.size
        if kernel < 3:
            return mep_mV

        trend = median_filter(mep_mV, size=kernel, mode="nearest")
        cleaned = mep_mV - trend
        return cleaned

    @staticmethod
    def _sample_step_ms(time_ms):
        time_ms = np.asarray(time_ms, dtype=float)
        if time_ms.size < 2:
            return np.nan
        return float(np.nanmedian(np.diff(time_ms)))

    @staticmethod
    def _calculate_tkeo(signal):
        signal = np.asarray(signal, dtype=float)
        tkeo = np.zeros_like(signal)
        if signal.size < 3:
            return tkeo
        tkeo[1:-1] = signal[1:-1] ** 2 - signal[:-2] * signal[2:]
        tkeo[0] = tkeo[1]
        tkeo[-1] = tkeo[-2]
        return tkeo

    @staticmethod
    def _detect_delay(time_ms, tkeo, threshold):
        idxs = np.where(np.asarray(tkeo) > threshold)[0]
        if idxs.size == 0:
            return np.nan
        return float(time_ms[int(idxs[0])])

    def _threshold_value(self):
        return float(self._spin_threshold.value()) * (10.0 ** int(self._spin_threshold_scale.value()))

    def _append_delay_to_bins(self, delay_ms):
        for idx in self._matching_bin_indices(delay_ms):
            self._bin_values[idx].append(float(delay_ms))
        self._update_bin_table()

    def _matching_bin_indices(self, delay_ms):
        matches = []
        for idx, bin_cfg in enumerate(self._bin_settings()):
            effective = self._effective_bin(bin_cfg)
            lo = float(effective.get("from_ms", -math.inf))
            hi = float(effective.get("to_ms", math.inf))
            if lo > hi:
                lo, hi = hi, lo
            if lo < delay_ms <= hi or (idx == 0 and delay_ms == lo):
                matches.append(idx)
        return matches

    def _rebuild_bins(self):
        self._bin_values = [[] for _ in self._bin_settings()]
        for delay_ms in self._all_delays:
            for idx in self._matching_bin_indices(delay_ms):
                self._bin_values[idx].append(float(delay_ms))
        self._update_bin_table()

    def _update_bin_table(self):
        self._updating_table = True
        for row, bin_cfg in enumerate(self._bin_settings()):
            while row >= len(self._bin_values):
                self._bin_values.append([])
            effective = self._effective_bin(bin_cfg)
            self._table.item(row, 0).setText(str(effective.get("name", "")))
            self._table.cellWidget(row, 2).setValue(int(effective.get("from_ms", 0)))
            self._table.cellWidget(row, 3).setValue(int(effective.get("to_ms", 0)))
            values = self._bin_values[row] if row < len(self._bin_values) else []
            self._table.item(row, 1).setText(str(len(values)))
            text = ", ".join(f"{value:.1f}" for value in values)
            self._table.item(row, 4).setText(text)
        self._updating_table = False
        self._plot_summary()

    def _on_bin_changed(self, row, key, value):
        if self._updating_table:
            return
        bins = self._bin_settings()
        if 0 <= row < len(bins) and not self._is_auto_delay_bin(bins[row]):
            bins[row][key] = int(value)
        self._rebuild_bins()

    def _on_settings_changed(self, _value=None):
        self.settings.bci_mep_threshold = float(self._spin_threshold.value())
        self.settings.bci_mep_threshold_scale = int(self._spin_threshold_scale.value())
        self.settings.bci_mep_plot_ymax_mV = float(self._spin_mep_ymax.value())
        self.settings.bci_mep_tkeo_ymax = float(self._spin_tkeo_ymax.value())
        self.settings.bci_mep_tkeo_scale = int(self._spin_tkeo_scale.value())
        self.settings.bci_mep_remove_trend = self._check_remove_trend.isChecked()
        self.settings.bci_mep_trend_window_ms = float(self._spin_trend_window_ms.value())
        if self._latest_processor is not None and self._latest_epoch_index > 0:
            self._process_epoch(self._latest_processor, self._latest_epoch_index, add_to_bins=False)
        else:
            self._plot_empty()

    def _plot_empty(self):
        self.figure.clear()
        ax_mep = self.figure.add_subplot(211)
        ax_tkeo = self.figure.add_subplot(212)
        x_start, x_end = self._x_limits()
        mep_ymax = self._mep_ymax()
        for ax, title in ((ax_mep, "MEP"), (ax_tkeo, "TKEO")):
            ax.axvline(0, color="black", lw=1, ls="--")
            ax.set_xlim(x_start, x_end)
            ax.set_title(title)
            ax.set_xlabel("time, ms")
            ax.grid(True, alpha=0.25)
        ax_mep.set_ylim(-mep_ymax, mep_ymax)
        ax_tkeo.set_ylim(0, self._tkeo_ymax())
        self.figure.tight_layout()
        self.canvas.draw()
        self._plot_summary()

    def _mep_ymax(self):
        return max(float(self._spin_mep_ymax.value()), 1e-9)

    def _tkeo_ymax(self):
        return max(float(self._spin_tkeo_ymax.value()), 1e-12) * (10.0 ** int(self._spin_tkeo_scale.value()))

    def _plot_result(self):
        if not self._latest_result:
            self._plot_empty()
            return

        data = self._latest_result
        time_ms = data["time_ms"]
        mep_mV = data["mep_mV"]
        tkeo = data["tkeo"]
        threshold = data["threshold"]
        delay_ms = data["delay_ms"]

        self.figure.clear()
        ax_mep = self.figure.add_subplot(211)
        ax_tkeo = self.figure.add_subplot(212, sharex=ax_mep)

        ax_mep.plot(time_ms, mep_mV, color="#2f6b9a", lw=1.2)
        ax_mep.axhline(0, color="0.45", lw=0.8)
        ax_mep.axvline(0, color="black", lw=1, ls="--", label="0 ms")
        ax_mep.set_ylabel("mV")
        ax_mep.set_title("Current MEP")
        mep_ymax = self._mep_ymax()
        ax_mep.set_ylim(-mep_ymax, mep_ymax)

        ax_tkeo.plot(time_ms, tkeo, color="#7b5db8", lw=1.2)
        ax_tkeo.axhline(threshold, color="#b85450", lw=1, ls="--", label="threshold")
        ax_tkeo.axvline(0, color="black", lw=1, ls="--")
        ax_tkeo.set_ylabel("V^2")
        ax_tkeo.set_xlabel("time, ms")
        ax_tkeo.set_title("TKEO(MEP)")
        ax_tkeo.set_ylim(0, self._tkeo_ymax())

        if np.isfinite(delay_ms):
            for ax in (ax_mep, ax_tkeo):
                ax.axvline(-delay_ms, color="#d4772f", lw=2, label="movement onset")

        for ax in (ax_mep, ax_tkeo):
            ax.grid(True, alpha=0.25)
            ax.legend(loc="upper right", fontsize=8)

        x_start, x_end = self._x_limits()
        ax_tkeo.set_xlim(x_start, x_end)

        self.figure.tight_layout()
        self.canvas.draw()

    def _plot_summary(self):
        self.summary_figure.clear()
        ax_bar = self.summary_figure.add_subplot(211)
        ax_hist = self.summary_figure.add_subplot(212)

        bins = self._bin_settings()
        labels = [str(self._effective_bin(bin_cfg).get("name", "")) for bin_cfg in bins]
        counts = [
            len(self._bin_values[idx]) if idx < len(self._bin_values) else 0
            for idx in range(len(bins))
        ]

        x = np.arange(len(labels))
        ax_bar.bar(x, counts, color="#4d7fa3")
        ax_bar.set_xticks(x)
        ax_bar.set_xticklabels(labels, fontsize=8)
        ax_bar.set_ylabel("N")
        ax_bar.set_title("Bins")
        ax_bar.grid(True, axis="y", alpha=0.25)

        finite_delays = np.asarray(
            [value for value in self._all_delays if np.isfinite(value)],
            dtype=float,
        )
        if finite_delays.size:
            ax_hist.hist(finite_delays, bins="auto", color="#7b5db8", edgecolor="white")
        ax_hist.set_xlabel("delay, ms")
        ax_hist.set_ylabel("N")
        ax_hist.set_title("Delay histogram")
        ax_hist.grid(True, axis="y", alpha=0.25)

        self.summary_figure.tight_layout()
        self.summary_canvas.draw()
