import os

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt

from logic.mep_condition_analysis import (
    analyze_conditions,
    condition_options,
    load_sequences,
)
from utils.ui_helpers import create_button, create_spin_box


class MEPConditionAnalysisWindow(QWidget):
    def __init__(self, epoch_path, stimuli_filename, parent=None):
        super().__init__(parent)
        self.epoch_path = epoch_path
        self.stimuli_filename = stimuli_filename
        self.sequences = load_sequences(stimuli_filename)
        self._condition_rows = []
        self.result = None

        self.setWindowTitle("MEP conditions")
        self.resize(1350, 760)

        self._setup_ui()
        self._setup_layout()
        self._setup_connections()
        self._reload_condition_rows()
        self.refresh_plot()

    def _setup_ui(self):
        self._settings_frame = QFrame(self)
        self._settings_scroll = QScrollArea(self)
        self._settings_scroll.setWidgetResizable(True)
        self._settings_scroll.setWidget(self._settings_frame)

        self._label_record = QLabel(os.path.basename(self.epoch_path), self)
        self._label_info = QLabel("MEP: --", self)
        self._button_refresh = create_button("Обновить", parent=self)
        self._button_add_condition = create_button("+ condition", parent=self)
        self._button_remove_condition = create_button("- condition", parent=self)

        self._combo_sequence = QComboBox(self)
        self._combo_sequence.addItems(sorted(self.sequences.keys()))

        self._spin_amp_from = create_spin_box(-300, 500, 15, data_type="float", decimals=1, step=1, parent=self, w=70)
        self._spin_amp_to = create_spin_box(-300, 500, 40, data_type="float", decimals=1, step=1, parent=self, w=70)
        self._spin_plot_from = create_spin_box(-300, 500, 10, data_type="float", decimals=1, step=1, parent=self, w=70)
        self._spin_plot_to = create_spin_box(-300, 500, 60, data_type="float", decimals=1, step=1, parent=self, w=70)

        self._rows_frame = QFrame(self)
        self._rows_layout = QGridLayout(self._rows_frame)

        self.figure = Figure(figsize=(9.5, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)

    def _setup_layout(self):
        settings_layout = QVBoxLayout(self._settings_frame)
        settings_layout.addWidget(self._label_record)
        settings_layout.addWidget(QLabel("Последовательность", self))
        settings_layout.addWidget(self._combo_sequence)

        amp_grid = QGridLayout()
        amp_grid.addWidget(QLabel("ампл. от, мс", self), 0, 0)
        amp_grid.addWidget(self._spin_amp_from, 0, 1)
        amp_grid.addWidget(QLabel("ампл. до, мс", self), 1, 0)
        amp_grid.addWidget(self._spin_amp_to, 1, 1)
        amp_grid.addWidget(QLabel("график от, мс", self), 2, 0)
        amp_grid.addWidget(self._spin_plot_from, 2, 1)
        amp_grid.addWidget(QLabel("график до, мс", self), 3, 0)
        amp_grid.addWidget(self._spin_plot_to, 3, 1)
        settings_layout.addLayout(amp_grid)

        settings_layout.addWidget(QLabel("Условия", self))
        settings_layout.addWidget(self._rows_frame)
        settings_layout.addWidget(self._button_add_condition)
        settings_layout.addWidget(self._button_remove_condition)
        settings_layout.addWidget(self._button_refresh)
        settings_layout.addWidget(self._label_info)
        settings_layout.addStretch()

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(self._settings_scroll)
        splitter.addWidget(self.canvas)
        splitter.setSizes([360, 990])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

    def _setup_connections(self):
        self._combo_sequence.currentTextChanged.connect(self._reload_condition_rows)
        self._button_refresh.clicked.connect(self.refresh_plot)
        self._button_add_condition.clicked.connect(self._add_condition_row)
        self._button_remove_condition.clicked.connect(self._remove_condition_row)

    def _current_sequence(self):
        return self.sequences.get(self._combo_sequence.currentText(), {})

    def _condition_options(self):
        return condition_options(self._current_sequence())

    def _reload_condition_rows(self, *_args):
        while self._condition_rows:
            self._remove_condition_row()

        options = self._condition_options()
        for _ in range(min(2, max(len(options), 1))):
            self._add_condition_row()

    def _add_condition_row(self, *_args):
        options = self._condition_options()
        row_idx = len(self._condition_rows)

        checkbox = QCheckBox(self._rows_frame)
        checkbox.setChecked(True)
        combo = QComboBox(self._rows_frame)
        for value, label in options:
            combo.addItem(label, value)
        if options:
            combo.setCurrentIndex(min(row_idx, len(options) - 1))

        self._rows_layout.addWidget(checkbox, row_idx, 0)
        self._rows_layout.addWidget(combo, row_idx, 1)
        self._condition_rows.append((checkbox, combo))

    def _remove_condition_row(self, *_args):
        if not self._condition_rows:
            return
        checkbox, combo = self._condition_rows.pop()
        checkbox.setParent(None)
        combo.setParent(None)
        checkbox.deleteLater()
        combo.deleteLater()

    def _selected_conditions(self):
        selected = []
        for checkbox, combo in self._condition_rows:
            if checkbox.isChecked() and combo.count() > 0:
                selected.append(int(combo.currentData()))
        return selected

    def refresh_plot(self):
        if not os.path.exists(self.epoch_path):
            QMessageBox.warning(self, "MEP conditions", f"Файл не найден:\n{self.epoch_path}")
            return

        selected = self._selected_conditions()
        if not selected:
            QMessageBox.information(self, "MEP conditions", "Выберите хотя бы одно условие.")
            return

        amp_from = self._spin_amp_from.value()
        amp_to = self._spin_amp_to.value()
        if amp_to <= amp_from:
            amp_to = amp_from + 1
            self._spin_amp_to.setValue(amp_to)

        try:
            self.result = analyze_conditions(
                self.epoch_path,
                self._current_sequence(),
                selected,
                amp_from_ms=amp_from,
                amp_to_ms=amp_to,
            )
        except Exception as exc:
            QMessageBox.warning(self, "MEP conditions", str(exc))
            return

        self._plot_result()
        self._update_info()

    def _plot_result(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        time = self.result["time"]
        plot_from = self._spin_plot_from.value()
        plot_to = self._spin_plot_to.value()
        if plot_to <= plot_from:
            plot_to = plot_from + 1
            self._spin_plot_to.setValue(plot_to)

        mask = (time >= plot_from) & (time <= plot_to)
        if not np.any(mask):
            mask = np.ones_like(time, dtype=bool)

        colors = ["#961CBB", "#4927C5", "#1b8a5a", "#c05a22", "#2f6b9a", "#b85450", "#7b5db8"]
        for idx, condition in enumerate(self.result["conditions"]):
            epochs = condition["epochs"]
            if epochs.size == 0:
                continue
            mean_epoch = np.nanmean(-epochs, axis=0)
            sem_epoch = np.nanstd(-epochs, axis=0) / np.sqrt(max(epochs.shape[0], 1))
            color = colors[idx % len(colors)]
            label = (
                f"{condition['label']} "
                f"(n={condition['n_epochs']}, mean={condition['mean_amplitude']:.3f} mV)"
            )
            ax.plot(time[mask], mean_epoch[mask], label=label, color=color, lw=1.8)
            ax.fill_between(
                time[mask],
                mean_epoch[mask] - sem_epoch[mask],
                mean_epoch[mask] + sem_epoch[mask],
                color=color,
                alpha=0.25,
            )

        ax.axvspan(self._spin_amp_from.value(), self._spin_amp_to.value(), color="0.9", alpha=0.6)
        ax.axvline(0, color="black", lw=0.8)
        ax.grid(color="lightgray", linewidth=0.5)
        ax.set_xlabel("Время (мс)")
        ax.set_ylabel("Амплитуда МВП (мВ)")
        ax.set_title(os.path.basename(self.epoch_path))
        ax.legend(fontsize=9)
        self.figure.tight_layout()
        self.canvas.draw()

    def _update_info(self):
        parts = []
        for condition in self.result["conditions"]:
            parts.append(
                f"{condition['label']}: n={condition['n_epochs']}, "
                f"mean={condition['mean_amplitude']:.3f} mV, "
                f"median={condition['median_amplitude']:.3f} mV"
            )
        warnings = self.result.get("warnings", [])
        text = "\n".join(parts)
        if warnings:
            text += "\n" + "\n".join(warnings)
        self._label_info.setText(text)
