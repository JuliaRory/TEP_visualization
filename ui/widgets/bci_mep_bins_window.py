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


class BCIMEPDelayWindow(QWidget):
    def __init__(self, settings, speed_settings=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.settings = settings
        self.speed_settings = speed_settings
        self._latest_processor = None
        self._latest_epoch_index = 0
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
        controls_layout.addWidget(self._table)
        controls_layout.addWidget(self._button_add_bin)
        controls_layout.addWidget(self._button_clear)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._controls_frame)
        splitter.addWidget(self.canvas)
        splitter.setSizes([430, 820])

        layout = QHBoxLayout(self)
        layout.addWidget(splitter)

    def _setup_connections(self):
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

        item_name = QTableWidgetItem(str(bin_cfg.get("name", "")))
        self._table.setItem(row, 0, item_name)

        item_count = QTableWidgetItem("0")
        item_count.setFlags(item_count.flags() & ~Qt.ItemIsEditable)
        item_count.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row, 1, item_count)

        spin_from = create_spin_box(
            -5000,
            5000,
            int(bin_cfg.get("from_ms", 0)),
            parent=self._table,
            w=85,
        )
        spin_to = create_spin_box(
            -5000,
            5000,
            int(bin_cfg.get("to_ms", 0)),
            parent=self._table,
            w=85,
        )
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
            bins = [
                {"name": "-400", "from_ms": -550, "to_ms": -250},
                {"name": "-200", "from_ms": -250, "to_ms": -150},
                {"name": "-100", "from_ms": -150, "to_ms": -75},
                {"name": "-50", "from_ms": -75, "to_ms": 25},
                {"name": "0", "from_ms": -25, "to_ms": 25},
            ]
            self.settings.bci_mep_bins = bins
        return bins

    def add_bin(self):
        bins = self._bin_settings()
        row = len(bins)
        bin_cfg = {"name": f"bin {row + 1}", "from_ms": 0, "to_ms": 0}
        bins.append(bin_cfg)
        self._bin_values.append([])
        self._add_bin_row(row, bin_cfg)
        self._update_bin_table()

    def _on_table_item_changed(self, item):
        if self._updating_table or item.column() != 0:
            return
        row = item.row()
        bins = self._bin_settings()
        if 0 <= row < len(bins):
            bins[row]["name"] = item.text().strip() or f"bin {row + 1}"

    def update_from_processor(self, processor):
        self._latest_processor = processor
        self.speed_settings = getattr(processor.settings, "speed", self.speed_settings)
        n_epoch = int(getattr(processor, "_n_epoch", len(getattr(processor, "_epochs", []))))
        if n_epoch <= 0 or not getattr(processor, "_epochs", None):
            return

        add_to_bins = n_epoch != self._latest_epoch_index
        self._latest_epoch_index = n_epoch
        self._process_epoch(processor, n_epoch, add_to_bins=add_to_bins)

    def clear_bins(self):
        self._all_delays = []
        self._bin_values = [[] for _ in self._bin_settings()]
        self._update_bin_table()

    def _process_epoch(self, processor, n_epoch, add_to_bins):
        epoch = np.asarray(processor._epochs[-1], dtype=float)
        if epoch.ndim != 2 or epoch.shape[0] < 2:
            return

        emg = processor._baseline(epoch[-2:, :] * 1e3)
        mep_mV = np.diff(emg, axis=0).flatten()
        time_ms = self._time_axis(processor, mep_mV.size)
        mep_mV = self._prepare_mep_signal(mep_mV, time_ms)
        tkeo = self._calculate_tkeo(mep_mV * 1e-3)

        threshold = self._threshold_value()
        delay_ms = self._detect_delay(time_ms, tkeo, threshold)

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
                self._rebuild_bins()
        else:
            self._label_delay.setText("delay: -")

        self._plot_result()

    def _time_axis(self, processor, n_samples):
        speed = getattr(processor.settings, "speed", self.speed_settings)
        self.speed_settings = speed
        fs = float(getattr(speed, "Fs", 0) or 0)
        start_ms = float(getattr(speed, "window_start", 0))
        end_ms = float(getattr(speed, "window_end", start_ms))
        if fs > 0:
            return start_ms + np.arange(n_samples, dtype=float) * 1000.0 / fs
        return np.linspace(start_ms, end_ms, n_samples, endpoint=False)

    def _x_limits(self):
        speed = self.speed_settings
        start_ms = float(getattr(speed, "window_start", -300))
        end_ms = float(getattr(speed, "window_end", 300))
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
        for idx, bin_cfg in enumerate(self._bin_settings()):
            lo = float(bin_cfg.get("from_ms", -math.inf))
            hi = float(bin_cfg.get("to_ms", math.inf))
            if lo > hi:
                lo, hi = hi, lo
            if lo < delay_ms <= hi or (idx == 0 and delay_ms == lo):
                self._bin_values[idx].append(float(delay_ms))
        self._update_bin_table()

    def _rebuild_bins(self):
        self._bin_values = [[] for _ in self._bin_settings()]
        for delay_ms in self._all_delays:
            self._append_delay_to_bins(delay_ms)
        self._update_bin_table()

    def _update_bin_table(self):
        self._updating_table = True
        for row, bin_cfg in enumerate(self._bin_settings()):
            values = self._bin_values[row] if row < len(self._bin_values) else []
            self._table.item(row, 1).setText(str(len(values)))
            text = ", ".join(f"{value:.1f}" for value in values)
            self._table.item(row, 4).setText(text)
        self._updating_table = False

    def _on_bin_changed(self, row, key, value):
        bins = self._bin_settings()
        if 0 <= row < len(bins):
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
                ax.axvline(delay_ms, color="#d4772f", lw=2, label="movement onset")

        for ax in (ax_mep, ax_tkeo):
            ax.grid(True, alpha=0.25)
            ax.legend(loc="upper right", fontsize=8)

        x_start, x_end = self._x_limits()
        ax_tkeo.set_xlim(x_start, x_end)

        self.figure.tight_layout()
        self.canvas.draw()
