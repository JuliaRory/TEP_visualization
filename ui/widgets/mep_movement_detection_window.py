import os

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt

from logic.mep_movement_detection import (
    MovementDetectionSettings,
    analyze_epoch_file,
)
from utils.ui_helpers import create_button, create_spin_box


class MEPMovementDetectionWindow(QWidget):
    def __init__(self, epoch_path, parent=None):
        super().__init__(parent)
        self.epoch_path = epoch_path
        self.settings = MovementDetectionSettings()
        self.result = None
        self.saved_figure_path = None

        self.setWindowTitle("MEP movement delay detection")
        self.resize(1500, 850)

        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        self.recalculate()

    def _setup_ui(self):
        self._settings_frame = QFrame(self)
        self._settings_scroll = QScrollArea(self)
        self._settings_scroll.setWidgetResizable(True)
        self._settings_scroll.setWidget(self._settings_frame)

        self._button_recalculate = create_button("Рассчитать", parent=self)
        self._label_record = QLabel(os.path.basename(self.epoch_path), self)
        self._label_summary = QLabel("", self)
        self._label_saved = QLabel("", self)

        self._spinboxes = {}
        self._checkboxes = {}
        self._create_settings_widgets()

        self.figure = Figure(figsize=(10, 7), dpi=100)
        self.canvas = FigureCanvas(self.figure)

    def _create_settings_widgets(self):
        specs = [
            ("baseline_from_ms", "baseline от, мс", -1000, 1000, 1, 2),
            ("baseline_to_ms", "baseline до, мс", -1000, 1000, 1, 2),
            ("art_from_ms", "артефакт от, мс", -1000, 1000, 0.5, 2),
            ("art_to_ms", "артефакт до, мс", -1000, 1000, 0.5, 2),
            ("mep_from_ms", "MEP от, мс", -1000, 1000, 1, 2),
            ("mep_to_ms", "MEP до, мс", -1000, 1000, 1, 2),
            ("threshold_k", "threshold k", 0, 1000, 0.5, 2),
            ("baseline_percentile", "baseline percentile", 0, 100, 0.1, 2),
            ("prominence_k", "prominence k", 0, 1000, 0.5, 2),
            ("smooth_ms", "smooth, мс", 0, 200, 0.5, 2),
            ("min_width_ms", "min width, мс", 0, 200, 0.5, 2),
            ("min_distance_ms", "min distance, мс", 0, 1000, 1, 2),
            ("confirmation_window_ms", "confirmation, мс", 0, 1000, 1, 2),
            ("required_fraction", "required fraction", 0, 1, 0.05, 3),
            ("min_peak_area", "min peak area", 0, 1e-7, 1e-10, 12),
            ("better_candidate_area_ratio", "better area ratio", 0, 1000, 0.5, 2),
            ("better_candidate_min_separation_ms", "better separation, мс", 0, 1000, 1, 2),
            ("pre_tms_ignore_after_ms", "pre-TMS ignore after, мс", -1000, 1000, 1, 2),
            ("early_delay_ms", "рано <, мс", -1000, 1000, 1, 2),
            ("late_delay_ms", "поздно >, мс", -1000, 1000, 1, 2),
            ("plot_from_ms", "график от, мс", -1000, 1000, 1, 2),
            ("plot_to_ms", "график до, мс", -1000, 1000, 1, 2),
            ("plot_ymax_mV", "масштаб, мВ", 0.01, 100, 0.1, 2),
            ("notch_hz", "notch, Гц", 1, 1000, 1, 2),
            ("notch_width_hz", "notch width, Гц", 0.1, 100, 0.1, 2),
            ("bandpass_low_hz", "bandpass low, Гц", 0.1, 2000, 1, 2),
            ("bandpass_high_hz", "bandpass high, Гц", 1, 3000, 1, 2),
        ]

        for attr, label, minimum, maximum, step, decimals in specs:
            spinbox = create_spin_box(
                minimum,
                maximum,
                getattr(self.settings, attr),
                data_type="float",
                decimals=decimals,
                step=step,
                parent=self._settings_frame,
                w=90,
            )
            self._spinboxes[attr] = (label, spinbox)

        self._checkboxes["detect_pre_tms"] = QCheckBox("detect pre-TMS", self._settings_frame)
        self._checkboxes["detect_pre_tms"].setChecked(self.settings.detect_pre_tms)

    def _setup_layout(self):
        settings_layout = QVBoxLayout(self._settings_frame)
        settings_layout.addWidget(self._label_record)
        settings_layout.addWidget(self._button_recalculate)
        settings_layout.addWidget(self._label_summary)
        settings_layout.addWidget(self._label_saved)

        grid = QGridLayout()
        row = 0
        for attr, (label, spinbox) in self._spinboxes.items():
            grid.addWidget(QLabel(label, self._settings_frame), row, 0)
            grid.addWidget(spinbox, row, 1)
            row += 1
        grid.addWidget(self._checkboxes["detect_pre_tms"], row, 0, 1, 2)
        settings_layout.addLayout(grid)
        settings_layout.addStretch()

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._settings_scroll)
        splitter.addWidget(self.canvas)
        splitter.setSizes([330, 1170])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def _setup_connections(self):
        self._button_recalculate.clicked.connect(self.recalculate)

    def _sync_settings_from_ui(self):
        for attr, (_, spinbox) in self._spinboxes.items():
            setattr(self.settings, attr, spinbox.value())
        self.settings.detect_pre_tms = self._checkboxes["detect_pre_tms"].isChecked()

    def recalculate(self):
        self._sync_settings_from_ui()
        try:
            self.result = analyze_epoch_file(self.epoch_path, self.settings)
        except Exception as exc:
            QMessageBox.warning(self, "MEP movement detection", str(exc))
            return

        self._update_summary()
        self._plot_result()
        self._save_figure()

    def _update_summary(self):
        n_epochs = len(self.result["rows"])
        early = self.result["early_count"]
        late = self.result["late_count"]
        self._label_summary.setText(
            f"Эпох: {n_epochs}. Слишком рано: {early}. Слишком поздно: {late}."
        )

    def _plot_result(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        time = self.result["time"]
        epochs = self.result["emg_epochs"]
        delays = self.result["delays"]
        rows = self.result["rows"]
        plot_mask = (time >= self.settings.plot_from_ms) & (time <= self.settings.plot_to_ms)
        if not np.any(plot_mask):
            plot_mask = np.ones_like(time, dtype=bool)

        scale = max(float(self.settings.plot_ymax_mV), 1e-6)
        spacing = scale * 2.6

        for idx, epoch in enumerate(epochs):
            y0 = idx * spacing
            color = "#2f6b9a"
            delay = delays[idx] if idx < len(delays) else np.nan
            if np.isfinite(delay) and delay < self.settings.early_delay_ms:
                color = "#b85450"
            elif np.isfinite(delay) and delay > self.settings.late_delay_ms:
                color = "#7b5db8"

            ax.plot(time[plot_mask], epoch[plot_mask] + y0, lw=0.8, color=color, alpha=0.85)
            ax.text(
                self.settings.plot_from_ms,
                y0,
                str(idx + 1),
                va="center",
                ha="right",
                fontsize=8,
                color="#555555",
            )

            if np.isfinite(delay):
                ax.plot(delay, y0, marker="o", ms=3.5, color="red", zorder=5)
                if idx < len(rows) and np.isfinite(rows[idx]["peak_time"]):
                    ax.plot(rows[idx]["peak_time"], y0, marker="|", ms=8, color="black", zorder=5)

        ax.axvspan(self.settings.art_from_ms, self.settings.art_to_ms, color="0.85", alpha=0.7)
        ax.axvspan(self.settings.mep_from_ms, self.settings.mep_to_ms, color="0.9", alpha=0.6)
        ax.axvline(self.settings.early_delay_ms, color="#b85450", lw=1, ls="--")
        ax.axvline(self.settings.late_delay_ms, color="#7b5db8", lw=1, ls="--")
        ax.axvline(0, color="black", lw=0.8)

        ax.set_xlim(self.settings.plot_from_ms, self.settings.plot_to_ms)
        ax.set_ylim(-spacing, max(spacing, len(epochs) * spacing))
        ax.set_xlabel("time [ms]")
        ax.set_ylabel("epochs")
        ax.set_yticks([])
        ax.set_title(
            f"{self.result['record_name']} | "
            f"too early: {self.result['early_count']} | "
            f"too late: {self.result['late_count']}"
        )
        self.figure.tight_layout()
        self.canvas.draw()

    def _save_figure(self):
        os.makedirs(os.path.join("data", "meps"), exist_ok=True)
        stem = os.path.splitext(os.path.basename(self.epoch_path))[0]
        self.saved_figure_path = os.path.join("data", "meps", f"{stem}.png")
        self.figure.savefig(self.saved_figure_path, dpi=160)
        self._label_saved.setText(f"PNG: {self.saved_figure_path}")
