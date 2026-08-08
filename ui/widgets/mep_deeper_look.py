from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QWidget,
    QGridLayout,
    QLabel,
    QFrame,
    QVBoxLayout,
    QStackedWidget,
    QLineEdit,
    QSizePolicy,
)
from types import SimpleNamespace

from utils.ui_helpers import create_spin_box, create_button
from utils.layout_utils import create_hbox
from ui.widgets.mep_plot import MEPPlot

from utils.widget_placement import place_widget


class MEPsDeeperLook(QWidget):
    settingsChanged = pyqtSignal()
    FEET_ROW_NAMES = ["AH", "MG", "TA"]
    FEET_DEFAULT_SETTINGS = {
        "xmin_ms": -10,
        "xmax_ms": 80,
        "amp_start_ms": 20,
        "amp_end_ms": 60,
    }
    STANDARD_WINDOW_SIZE = (1700, 500)
    FEET_WINDOW_SIZE = (1700, 900)
    
    def __init__(self, settings, Fs, monitor=1):
        super().__init__()

        self.setWindowTitle("Motor Evoked Potentials")
        self.resize(*self.STANDARD_WINDOW_SIZE)
        
        place_widget(self, monitor=monitor, coordinates=(10, 1080-600))

        self.Fs = Fs
        self.settings = settings # single mep plot settings
        self._standard_settings_snapshot = None
        self._channel_count = 66
        self._feet_amp_counts = [0, 0, 0]

        self._init_state()
        self._setup_ui()
        self._setup_layout()
        self._setup_connections()

    def _init_state(self):
        n_line = 3

        self.ratio = 0.0
        self.line_w = (1-self.ratio) * self.width()
        self.line_h = (1-self.ratio) * self.height() //2
        self.feet_line_w = max(1000, int(self.width() - 150))
        self.feet_line_h = 220


    def _setup_ui(self):
        self._setup_figures_widgets()
        self._setup_feet_widgets()
        self._setup_mep_settings_widgets()
        self._setup_thr_widgets()
    
    def _setup_thr_widgets(self):
        self._frame_thr = QFrame(self)
        self._frame_thr.setContentsMargins(0, 0, 0, 0)
        self._frame_thr.setFixedHeight(int(0.5 * self.line_h))

        self.spinbox_thr = create_spin_box(0, 100, self.settings.thr, data_type="float", decimals=2, step=.1, parent=self._frame_thr, w=60)
        self.spinbox_thr_n_plots = create_spin_box(1, self.settings.n_plots, self.settings.n_plots_thr, parent=self._frame_thr, w=50)
        
        self._label_thr = QLabel(f"Выше порога: {0}/{self.settings.n_plots_thr}")
        self._label_thr.setObjectName("label_thr_counter")
        self._label_thr.setAlignment(Qt.AlignCenter)
        self._label_thr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)


    def _setup_figures_widgets(self):
        n = self.settings.n_plots
        self.figure = MEPPlot(self, w=self.line_w, h=self.line_h, settings=self.settings, Fs=self.Fs, titles=[f"# {i+1}" for i in range(n)], emphasize_first=True)
        self.figure.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._standard_figure = self.figure
        self._all_figures = [self.figure]

    def _setup_feet_widgets(self):
        self._feet_figures = []
        self._feet_settings = []
        self._feet_name_edits = []
        self._feet_channel_spins = []
        self._feet_scale_spins = []
        self._feet_thr_spins = []

        self._feet_page = QWidget(self)
        self._feet_grid = QGridLayout(self._feet_page)
        self._feet_grid.setContentsMargins(0, 0, 0, 0)
        self._feet_grid.setHorizontalSpacing(8)
        self._feet_grid.setVerticalSpacing(4)

        for row in range(3):
            row_name = self._feet_row_name(row)
            control = QFrame(self._feet_page)
            control_layout = QVBoxLayout(control)
            control_layout.setContentsMargins(0, 0, 0, 0)

            plot_row = QFrame(self._feet_page)
            plot_row_layout = QVBoxLayout(plot_row)
            plot_row_layout.setContentsMargins(0, 0, 0, 0)
            plot_row_layout.setSpacing(0)

            name_edit = QLineEdit(row_name, plot_row)
            name_edit.setFixedWidth(90)
            name_edit.setMaxLength(24)
            name_edit.setAlignment(Qt.AlignCenter)

            pair = self._feet_channel_pair(row)
            spin_a = create_spin_box(1, self._channel_count, pair[0], parent=control, w=58)
            spin_b = create_spin_box(1, self._channel_count, pair[1], parent=control, w=58)
            spin_scale = create_spin_box(0.01, 1000, self._feet_row_max_amp(row), data_type="float", decimals=2, step=.1, parent=control, w=58)
            spin_thr = create_spin_box(0, 100, self._feet_row_thr(row), data_type="float", decimals=2, step=.1, parent=control, w=58)

            control_layout.addWidget(QLabel("Ch A:", control))
            control_layout.addWidget(spin_a)
            control_layout.addWidget(QLabel("Ch B:", control))
            control_layout.addWidget(spin_b)
            control_layout.addWidget(QLabel("Scale:", control))
            control_layout.addWidget(spin_scale)
            control_layout.addWidget(QLabel("Thr:", control))
            control_layout.addWidget(spin_thr)
            control_layout.addStretch()

            row_settings = self._create_feet_row_settings(row)
            figure = MEPPlot(
                plot_row,
                w=self.feet_line_w,
                h=self.feet_line_h,
                settings=row_settings,
                Fs=self.Fs,
                titles=self._feet_titles(row),
                emphasize_first=True,
            )
            figure.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            plot_row_layout.addWidget(name_edit, 0, Qt.AlignHCenter)
            plot_row_layout.addWidget(figure)

            self._feet_name_edits.append(name_edit)
            self._feet_channel_spins.append((spin_a, spin_b))
            self._feet_scale_spins.append(spin_scale)
            self._feet_thr_spins.append(spin_thr)
            self._feet_settings.append(row_settings)
            self._feet_figures.append(figure)
            self._all_figures.append(figure)

            self._feet_grid.addWidget(control, row, 0)
            self._feet_grid.addWidget(plot_row, row, 1)

    
    def _setup_mep_settings_widgets(self):
        self._frame_mep_settings = QFrame(self)
        self._frame_mep_settings.setContentsMargins(0, 0, 0, 0)
        self._frame_mep_settings.setFixedHeight(int(self.line_h))

        label1 = QLabel("Макс:", self._frame_mep_settings)
        label2 = QLabel("мВ", self._frame_mep_settings)
        self._spinbox_max_amp = create_spin_box(0.01, 1000, self.settings.max_amp_mV, data_type="float", decimals=2, step=.1, parent=self._frame_mep_settings, w=60)
        self._max_amp = create_hbox([label1, self._spinbox_max_amp, label2])

        label = QLabel("N:    ", self._frame_mep_settings)
        label_epmty = QLabel("", self._frame_mep_settings)
        self._spinbox_n_plots = create_spin_box(1, 10, self.settings.n_plots, parent=self._frame_mep_settings, w=50)
        self._n_plots = create_hbox([label, self._spinbox_n_plots, label_epmty])

        label1 = QLabel("от:   ", self._frame_mep_settings)
        label3 = QLabel("мс", self._frame_mep_settings)
        self._spinbox_min_time = create_spin_box(-300, 0, self.settings.xmin_ms, parent=self._frame_mep_settings, w=50)
        self._time_range_min = create_hbox([label1, self._spinbox_min_time, label3])

        label2 = QLabel("до:   ", self._frame_mep_settings)
        label3 = QLabel("мс", self._frame_mep_settings)
        self._spinbox_max_time = create_spin_box(0, 500, self.settings.xmax_ms, parent=self._frame_mep_settings, w=50)
        self._time_range_max = create_hbox([label2, self._spinbox_max_time, label3])

        label1 = QLabel("ампл. от:", self._frame_mep_settings)
        label3 = QLabel("мс", self._frame_mep_settings)
        self._spinbox_amp_start = create_spin_box(-300, 500, self.settings.amp_start_ms, parent=self._frame_mep_settings, w=50)
        self._amp_start = create_hbox([label1, self._spinbox_amp_start, label3])

        label2 = QLabel("ампл. до:", self._frame_mep_settings)
        label3 = QLabel("мс", self._frame_mep_settings)
        self._spinbox_amp_end = create_spin_box(-300, 500, self.settings.amp_end_ms, parent=self._frame_mep_settings, w=50)
        self._amp_end = create_hbox([label2, self._spinbox_amp_end, label3])

        self._check_remove_trend = QCheckBox("Remove slow trend", self._frame_mep_settings)
        self._check_remove_trend.setChecked(bool(getattr(self.settings, "remove_slow_trend", True)))

        self._check_feet_stim = QCheckBox("feetStim", self._frame_mep_settings)
        self._check_feet_stim.setChecked(bool(getattr(self.settings, "feet_mode", False)))

        self._button_apply = create_button('Применить', disabled=False, parent=self._frame_mep_settings, w=150)
        
    def _setup_layout(self):
        self._setup_mep_settings()
        self._setup_thr_settings()
        self._setup_plot_stack()

        grid = QGridLayout(self)
        grid.setRowStretch(0, 0)   # верхняя строка — минимальная
        grid.setRowStretch(1, 0)   # верхняя строка — минимальная
        #    1               5
        #  +---+----------------------------------+
        #  |   |    thr settings & labels         |
        #  +---+----------------------------------+
        #  |   |    MEP plots                     |
        #  +---+----------------------------------+
        #  |   |    ongoing EMG                   |
        #  +---+----------------------------------+                      

        # self._frame_thr.setStyleSheet("border: 1px solid green;")
        # self._frame_mep_settings.setStyleSheet("border: 1px solid red;")
        # self.figure.setStyleSheet("border: 1px solid blue;")

        row = 0 
        grid.addWidget(self._frame_thr, row, 0, 1, 2)
        row = 1
        grid.addWidget(self._frame_mep_settings, row, 0, 1, 1)
        grid.addWidget(self._plot_stack, row, 1, 1, 1)
        
        row = 2   
        # grid.addLayout(self.layout_settings, 0, 0, 1, 1) ## emg filters

    def _setup_plot_stack(self):
        self._standard_page = QWidget(self)
        standard_grid = QGridLayout(self._standard_page)
        standard_grid.setContentsMargins(0, 0, 0, 0)
        standard_grid.addWidget(self.figure, 0, 0)

        self._plot_stack = QStackedWidget(self)
        self._plot_stack.addWidget(self._standard_page)
        self._plot_stack.addWidget(self._feet_page)
        self._set_feet_page_visible(self.is_feet_stim_mode(), emit=False)
        

    def _setup_thr_settings(self):
        self.grid_thr = QGridLayout(self._frame_thr)
        self.grid_thr.setRowStretch(0, 0)
        self.grid_thr.setRowStretch(1, 0)
        
        layout_thr_value = create_hbox([QLabel("Порог: "), self.spinbox_thr, QLabel("mV")])
        layout_n_plots_value = create_hbox([QLabel("Кол-во попыток: "), self.spinbox_thr_n_plots])

        self.grid_thr.addLayout(layout_thr_value, 0, 0)
        self.grid_thr.addLayout(layout_n_plots_value, 1, 0)

        self.grid_thr.addWidget(self._label_thr, 0, 1, 2, 1)
        self.grid_thr.setColumnStretch(0, 0)
        self.grid_thr.setColumnStretch(1, 1)

        # self.grid_thr.columnStretch(0)
        # self.grid_thr.rowStretch(0)

    def _setup_firuges(self):
        self.layout_figures = QVBoxLayout()
        self.layout_figures.addWidget(self.figure_1)
    
    def _setup_mep_settings(self):
        self.layout_settings = QVBoxLayout(self._frame_mep_settings)
        for layout in [self._max_amp, self._n_plots, self._time_range_min, self._time_range_max, self._amp_start, self._amp_end]:
            self.layout_settings.addLayout(layout)
        self.layout_settings.addWidget(self._check_remove_trend)
        self.layout_settings.addWidget(self._check_feet_stim)
        self.layout_settings.addWidget(self._button_apply)

        self.layout_settings.addStretch()
    
    def update_emg(self, emg2plot):
        if self.is_feet_stim_mode():
            for figure, emg in zip(self._feet_figures, emg2plot):
                figure.update_emg(emg)
            return
        self.figure.update_emg(emg2plot)


    def _setup_connections(self):
        self.figure.amp_counter.connect(self._on_change_amp_counter)
        for row, figure in enumerate(self._feet_figures):
            figure.amp_counter.connect(lambda value, row=row: self._on_change_amp_counter(value, row))
        self.spinbox_thr.valueChanged.connect(self._on_threshold_changed)
        self.spinbox_thr_n_plots.valueChanged.connect(self._on_threshold_changed)
        self._button_apply.clicked.connect(self._apply_mep_settings)
        self._check_remove_trend.stateChanged.connect(self._on_remove_trend_changed)
        self._check_feet_stim.stateChanged.connect(self._on_feet_stim_changed)
        for row, name_edit in enumerate(self._feet_name_edits):
            name_edit.editingFinished.connect(lambda row=row: self._on_feet_row_changed(row))
        for row, spins in enumerate(self._feet_channel_spins):
            for spin in spins:
                spin.valueChanged.connect(lambda _value, row=row: self._on_feet_row_changed(row))
        for row, spin in enumerate(self._feet_scale_spins):
            spin.valueChanged.connect(lambda _value, row=row: self._on_feet_row_changed(row))
        for row, spin in enumerate(self._feet_thr_spins):
            spin.valueChanged.connect(lambda _value, row=row: self._on_feet_row_changed(row))

    def _on_change_amp_counter(self, value, feet_row=None):
        if feet_row is not None:
            self._feet_amp_counts[feet_row] = value
        self._update_threshold_label(value)

    def _on_threshold_changed(self, _value=None):
        self.settings.thr = self.spinbox_thr.value()
        self.settings.n_plots_thr = self._coerce_threshold_window(self.spinbox_thr_n_plots.value())
        self._sync_feet_figure_settings()
        for figure in self._active_figures():
            figure.emit_threshold_count()

    def _on_remove_trend_changed(self, _state):
        self.settings.remove_slow_trend = self._check_remove_trend.isChecked()
        self.settingsChanged.emit()

    def _on_feet_stim_changed(self, _state):
        self._set_feet_page_visible(self._check_feet_stim.isChecked(), emit=True)

    def _on_feet_row_changed(self, row):
        self._sync_feet_settings_from_controls()
        self._sync_feet_figure_settings(row)
        self._feet_figures[row].titles_label = self._feet_titles(row)
        self._feet_figures[row].rebuild_from_settings(reset_history=True)
        self.settingsChanged.emit()

    def _apply_mep_settings(self):
        xmin = self._spinbox_min_time.value()
        xmax = self._spinbox_max_time.value()
        if xmax <= xmin:
            xmax = xmin + 1
            self._spinbox_max_time.setValue(xmax)

        amp_start = self._spinbox_amp_start.value()
        amp_end = self._spinbox_amp_end.value()
        amp_start = max(xmin, min(amp_start, xmax - 1))
        amp_end = max(amp_start + 1, min(amp_end, xmax))
        if self._spinbox_amp_start.value() != amp_start:
            self._spinbox_amp_start.setValue(amp_start)
        if self._spinbox_amp_end.value() != amp_end:
            self._spinbox_amp_end.setValue(amp_end)

        self.settings.max_amp_mV = self._spinbox_max_amp.value()
        self.settings.n_plots = self._spinbox_n_plots.value()
        self.spinbox_thr_n_plots.setMaximum(self.settings.n_plots)
        self.settings.xmin_ms = xmin
        self.settings.xmax_ms = xmax
        self.settings.amp_start_ms = amp_start
        self.settings.amp_end_ms = amp_end
        self.settings.thr = self.spinbox_thr.value()
        self.settings.n_plots_thr = self._coerce_threshold_window(self.spinbox_thr_n_plots.value())
        self.settings.remove_slow_trend = self._check_remove_trend.isChecked()
        self.settings.feet_mode = self.is_feet_stim_mode()
        self._sync_feet_settings_from_controls()

        self.figure.titles_label = [f"# {i+1}" for i in range(self.settings.n_plots)]
        for row, figure in enumerate(self._feet_figures):
            figure.titles_label = self._feet_titles(row)
        self.rebuild_from_settings(reset_history=True)
        self.settingsChanged.emit()

    def is_feet_stim_mode(self):
        return bool(getattr(self.settings, "feet_mode", False))

    def set_channel_count(self, channel_count):
        channel_count = max(2, int(channel_count))
        if channel_count == self._channel_count:
            return
        self._channel_count = channel_count
        for spin_a, spin_b in self._feet_channel_spins:
            for spin in (spin_a, spin_b):
                spin.setMaximum(channel_count)
        self._sync_feet_settings_from_controls()

    def get_feet_channel_pairs(self):
        self._sync_feet_settings_from_controls()
        return [
            (int(pair[0]), int(pair[1]))
            for pair in getattr(self.settings, "feet_channel_pairs", [])
        ]

    def rebuild_from_settings(self, reset_history=True):
        self._sync_controls_from_settings()
        self.figure.titles_label = [f"# {i+1}" for i in range(self.settings.n_plots)]
        self._sync_feet_figure_settings()
        for figure in self._active_figures():
            figure.rebuild_from_settings(reset_history=reset_history)
        if reset_history:
            self._feet_amp_counts = [0, 0, 0]
            self._update_threshold_label(0)

    def _active_figures(self):
        return self._feet_figures if self.is_feet_stim_mode() else [self.figure]

    def _set_feet_page_visible(self, enabled, emit):
        enabled = bool(enabled)
        if enabled:
            if self._standard_settings_snapshot is None:
                self._standard_settings_snapshot = self._settings_snapshot()
            for field, value in self.FEET_DEFAULT_SETTINGS.items():
                setattr(self.settings, field, value)
            if not getattr(self.settings, "feet_row_names", None):
                self.settings.feet_row_names = list(self.FEET_ROW_NAMES)
            if not getattr(self.settings, "feet_channel_pairs", None):
                self.settings.feet_channel_pairs = self._default_feet_pairs()
            if not getattr(self.settings, "feet_max_amp_mV", None):
                self.settings.feet_max_amp_mV = [float(self.settings.max_amp_mV)] * 3
            if not getattr(self.settings, "feet_thr", None):
                self.settings.feet_thr = [float(self.settings.thr)] * 3
            self.settings.feet_mode = True
        else:
            if self._standard_settings_snapshot is not None:
                self._restore_settings_snapshot(self._standard_settings_snapshot)
                self._standard_settings_snapshot = None
            self.settings.feet_mode = False

        if hasattr(self, "_plot_stack"):
            self._plot_stack.setCurrentWidget(self._feet_page if enabled else self._standard_page)
        self.resize(*(self.FEET_WINDOW_SIZE if enabled else self.STANDARD_WINDOW_SIZE))
        self._sync_controls_from_settings()
        self.rebuild_from_settings(reset_history=True)
        if emit:
            self.settingsChanged.emit()

    def _settings_snapshot(self):
        return {
            "xmin_ms": self.settings.xmin_ms,
            "xmax_ms": self.settings.xmax_ms,
            "max_amp_mV": self.settings.max_amp_mV,
            "n_plots": self.settings.n_plots,
            "amp_start_ms": self.settings.amp_start_ms,
            "amp_end_ms": self.settings.amp_end_ms,
            "thr": self.settings.thr,
            "n_plots_thr": self.settings.n_plots_thr,
            "remove_slow_trend": self.settings.remove_slow_trend,
        }

    def _restore_settings_snapshot(self, snapshot):
        for field, value in snapshot.items():
            setattr(self.settings, field, value)

    def _sync_controls_from_settings(self):
        widgets_and_values = [
            (self._spinbox_max_amp, self.settings.max_amp_mV),
            (self._spinbox_n_plots, self.settings.n_plots),
            (self._spinbox_min_time, self.settings.xmin_ms),
            (self._spinbox_max_time, self.settings.xmax_ms),
            (self._spinbox_amp_start, self.settings.amp_start_ms),
            (self._spinbox_amp_end, self.settings.amp_end_ms),
            (self.spinbox_thr, self.settings.thr),
            (self.spinbox_thr_n_plots, self._coerce_threshold_window(self.settings.n_plots_thr)),
        ]
        for widget, value in widgets_and_values:
            blocked = widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(blocked)

        blocked = self._check_remove_trend.blockSignals(True)
        self._check_remove_trend.setChecked(bool(getattr(self.settings, "remove_slow_trend", True)))
        self._check_remove_trend.blockSignals(blocked)

        blocked = self._check_feet_stim.blockSignals(True)
        self._check_feet_stim.setChecked(self.is_feet_stim_mode())
        self._check_feet_stim.blockSignals(blocked)

        names = self._feet_row_names()
        pairs = self._feet_channel_pairs()
        for row, name_edit in enumerate(self._feet_name_edits):
            blocked = name_edit.blockSignals(True)
            name_edit.setText(names[row])
            name_edit.blockSignals(blocked)
        for row, (spin_a, spin_b) in enumerate(self._feet_channel_spins):
            for spin, value in ((spin_a, pairs[row][0]), (spin_b, pairs[row][1])):
                blocked = spin.blockSignals(True)
                spin.setValue(max(1, min(int(value), self._channel_count)))
                spin.blockSignals(blocked)
        scales = self._feet_row_max_amps()
        thresholds = self._feet_row_thrs()
        for row, spin in enumerate(self._feet_scale_spins):
            blocked = spin.blockSignals(True)
            spin.setValue(scales[row])
            spin.blockSignals(blocked)
        for row, spin in enumerate(self._feet_thr_spins):
            blocked = spin.blockSignals(True)
            spin.setValue(thresholds[row])
            spin.blockSignals(blocked)

    def _sync_feet_settings_from_controls(self):
        self.settings.feet_row_names = [
            edit.text().strip() or self.FEET_ROW_NAMES[row]
            for row, edit in enumerate(self._feet_name_edits)
        ]
        self.settings.feet_channel_pairs = [
            [int(spin_a.value()), int(spin_b.value())]
            for spin_a, spin_b in self._feet_channel_spins
        ]
        self.settings.feet_max_amp_mV = [
            float(spin.value())
            for spin in self._feet_scale_spins
        ]
        self.settings.feet_thr = [
            float(spin.value())
            for spin in self._feet_thr_spins
        ]

    def _feet_row_names(self):
        names = list(getattr(self.settings, "feet_row_names", []) or [])
        names = (names + self.FEET_ROW_NAMES)[:3]
        return [name or self.FEET_ROW_NAMES[i] for i, name in enumerate(names)]

    def _feet_row_name(self, row):
        return self._feet_row_names()[row]

    def _feet_channel_pairs(self):
        pairs = list(getattr(self.settings, "feet_channel_pairs", []) or [])
        pairs = (pairs + self._default_feet_pairs())[:3]
        return [
            [
                max(1, min(int(pair[0]), self._channel_count)),
                max(1, min(int(pair[1]), self._channel_count)),
            ]
            for pair in pairs
        ]

    def _feet_channel_pair(self, row):
        return self._feet_channel_pairs()[row]

    def _feet_row_max_amps(self):
        values = list(getattr(self.settings, "feet_max_amp_mV", []) or [])
        values = (values + [float(self.settings.max_amp_mV)] * 3)[:3]
        return [max(float(value), 0.01) for value in values]

    def _feet_row_max_amp(self, row):
        return self._feet_row_max_amps()[row]

    def _feet_row_thrs(self):
        values = list(getattr(self.settings, "feet_thr", []) or [])
        values = (values + [float(self.settings.thr)] * 3)[:3]
        return [max(float(value), 0.0) for value in values]

    def _feet_row_thr(self, row):
        return self._feet_row_thrs()[row]

    def _create_feet_row_settings(self, row):
        return SimpleNamespace(
            xmin_ms=self.settings.xmin_ms,
            xmax_ms=self.settings.xmax_ms,
            max_amp_mV=self._feet_row_max_amp(row),
            n_plots=self.settings.n_plots,
            amp_start_ms=self.settings.amp_start_ms,
            amp_end_ms=self.settings.amp_end_ms,
            thr=self._feet_row_thr(row),
            n_plots_thr=self.settings.n_plots_thr,
        )

    def _sync_feet_figure_settings(self, row=None):
        rows = range(3) if row is None else [row]
        scales = self._feet_row_max_amps()
        thresholds = self._feet_row_thrs()
        for i in rows:
            row_settings = self._feet_settings[i]
            row_settings.xmin_ms = self.settings.xmin_ms
            row_settings.xmax_ms = self.settings.xmax_ms
            row_settings.max_amp_mV = scales[i]
            row_settings.n_plots = self.settings.n_plots
            row_settings.amp_start_ms = self.settings.amp_start_ms
            row_settings.amp_end_ms = self.settings.amp_end_ms
            row_settings.thr = thresholds[i]
            row_settings.n_plots_thr = self.settings.n_plots_thr

    def _default_feet_pairs(self):
        first = max(1, self._channel_count - 5)
        return [[first, first + 1], [first + 2, first + 3], [first + 4, first + 5]]

    def _feet_titles(self, row):
        name = self._feet_row_name(row)
        return [f"{name} #{i+1}" for i in range(self.settings.n_plots)]

    def _update_threshold_label(self, value):
        if not self.is_feet_stim_mode():
            self._label_thr.setText(f"Выше порога: {value}/{self.settings.n_plots_thr}")
            return
        names = self._feet_row_names()
        thresholds = self._feet_row_thrs()
        parts = [
            f"{names[row]} ≥ {thresholds[row]:g}: {self._feet_amp_counts[row]}/{self.settings.n_plots_thr}"
            for row in range(3)
        ]
        self._label_thr.setText("Выше порога: " + "; ".join(parts))

    def _coerce_threshold_window(self, value):
        value = max(1, min(int(value), int(self.settings.n_plots)))
        if self.spinbox_thr_n_plots.value() != value:
            blocked = self.spinbox_thr_n_plots.blockSignals(True)
            self.spinbox_thr_n_plots.setValue(value)
            self.spinbox_thr_n_plots.blockSignals(blocked)
        return value
