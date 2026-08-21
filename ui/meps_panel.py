from PyQt5.QtWidgets import QCheckBox, QFrame,  QHBoxLayout, QLabel,  QSplitter, QVBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

from utils.ui_helpers import  create_button, create_spin_box, create_check_box
from utils.layout_utils import create_hbox

from ui.widgets.mep_plot import MEPPlot
from ui.widgets.mep_deeper_look import MEPsDeeperLook

MICROVOLT = "\u03BC"+"V"

class MEPsPanel(QFrame):
    """
    
    """
    deeperLookActivate = pyqtSignal()
    movementDetectionActivate = pyqtSignal()
    conditionAnalysisActivate = pyqtSignal()
    processingChanged = pyqtSignal()
    emgProcessingApplyRequested = pyqtSignal()
    def __init__(self, parent=None,   Fs=5000, settings=None, settings_dl=None, processing_settings=None, init_size=[600, 800]):
        super().__init__(parent)
        """Внешний вид виджета"""
        self.resize(init_size[0], init_size[1])
        self.setMinimumHeight(50)

        """Параметры"""
        self.Fs = Fs
        self.settings = settings
        self.settings_dl = settings_dl
        self.processing_settings = processing_settings

        self._init_state()

        """Визуальная часть виджета"""
        self._setup_ui()
        self._setup_layout()

        """Связи"""
        self._setup_connections()

        """Финализация"""
        self._post_init()


    # --- Initialization ---
    def _init_state(self):
        
        self.setObjectName("mep_main_panel")    # для привязки стиля
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.left_right_ratio = getattr(self.settings, "set_plot_ratio", 0.15)
        self.n5_5, self.n5_10 = 0, 0
        self.n10_5, self.n10_10 = 0, 0
        self._channel_count = 66
        self._emg_processing_details_visible = True
        
    # --- Widgets ---
    def _setup_ui(self):
        self.figure = MEPPlot(self, w=(1-self.left_right_ratio)*self.width(), h=self.height(), settings=self.settings, Fs=self.Fs)
        self.figure.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._label = QLabel("MEP", self)
        self._label.setObjectName("label_mep")
        # self._label.setFixedWidth(60)

        # self._label_counter = QLabel(f">0.5 mV: {self.n5_5}/5; {self.n5_10}/10.\n>1.0 mV: {self.n10_5}/5; {self.n10_10}/10.")
        self._label_counter = QLabel(self._counter_text(0))
        self._label_counter.setObjectName("label_amp_counter")
        # self._label_counter.setFixedWidth(150)

        self._frame_settings = QFrame(self)

        self._button_deeper_look = create_button("MEP threshold", parent=self, w=100)
        self._button_movement_detection = create_button("MEP delays", w=100)
        self._button_condition_analysis = create_button("MEP conditions",  w=120)
        self._check_remove_trend = QCheckBox("Remove slow trend", self)
        self._check_remove_trend.setChecked(bool(getattr(self.settings, "remove_slow_trend", True)))
        pair = self._channel_pair()
        self._spinbox_channel_a = create_spin_box(1, self._channel_count, pair[0], parent=self, w=55)
        self._spinbox_channel_b = create_spin_box(1, self._channel_count, pair[1], parent=self, w=55)

        self._frame_emg_processing = QFrame(self)
        self._frame_emg_processing.setObjectName("emg_processing_panel")
        self._frame_emg_processing.setStyleSheet("""
            QFrame#emg_processing_panel {
                background-color: rgba(70, 90, 100, 51);
                border: 1px solid rgba(70, 90, 100, 90);
                border-radius: 6px;
            }
        """)
        self._button_emg_processing_toggle = create_button("ОБРАБОТКА ЭМГ ▾", parent=self._frame_emg_processing, w=130)
        self._button_emg_processing_apply = create_button("Применить", parent=self._frame_emg_processing, w=85)

        p = self.processing_settings
        self.check_box_emg_highpass = create_check_box(
            bool(getattr(p, "do_emg_highpass_filtering", True)),
            "ФВЧ",
            parent=self._frame_emg_processing,
        )
        self.spin_box_emg_highpass = create_spin_box(
            0.01,
            10000,
            float(getattr(p, "emg_highpass_freq_Hz", 10)),
            data_type="float",
            decimals=2,
            step=1,
            parent=self._frame_emg_processing,
            w=70,
        )

        self.check_box_emg_lowpass = create_check_box(
            bool(getattr(p, "do_emg_lowpass_filtering", True)),
            "ФНЧ",
            parent=self._frame_emg_processing,
        )
        self.spin_box_emg_lowpass = create_spin_box(
            1,
            10000,
            int(getattr(p, "emg_lowpass_freq_Hz", 1000)),
            step=50,
            parent=self._frame_emg_processing,
            w=70,
        )

        self.check_box_emg_resampling = create_check_box(
            bool(getattr(p, "do_emg_resampling", True)),
            "Resampling",
            parent=self._frame_emg_processing,
        )
        self.spin_box_emg_resampling = create_spin_box(
            1,
            100000,
            int(getattr(p, "emg_resample_freq_Hz", 2000)),
            step=250,
            parent=self._frame_emg_processing,
            w=70,
        )

        self.check_box_emg_baseline = create_check_box(
            bool(getattr(p, "do_emg_baseline_correction", True)),
            "Бейзлайн",
            parent=self._frame_emg_processing,
        )
        self.spin_box_emg_baseline_from = create_spin_box(
            -10000,
            10000,
            int(getattr(p, "emg_baseline_from_ms", -75)),
            step=5,
            parent=self._frame_emg_processing,
            w=60,
        )
        self.spin_box_emg_baseline_to = create_spin_box(
            -10000,
            10000,
            int(getattr(p, "emg_baseline_to_ms", -20)),
            step=5,
            parent=self._frame_emg_processing,
            w=60,
        )
        self._emg_processing_details = QFrame(self._frame_emg_processing)

    # --- Layout ---
    def _setup_layout(self):
        layout_settings = QVBoxLayout(self._frame_settings)
        layout_settings.addWidget(self._label)
        layout_settings.addWidget(self._label_counter)
        layout_settings.addLayout(create_hbox([QLabel("EMG A:", self), self._spinbox_channel_a]))
        layout_settings.addLayout(create_hbox([QLabel("EMG B:", self), self._spinbox_channel_b]))
        layout_settings.addWidget(self._check_remove_trend)
        layout_settings.addWidget(self._button_deeper_look)
        # layout_settings.addWidget(self._button_movement_detection)
        # layout_settings.addWidget(self._button_condition_analysis)
        

        self.splitter = QSplitter(Qt.Horizontal, parent=self)        # позволяет изменять размер
        self.splitter.addWidget(self._frame_settings)
        self.splitter.addWidget(self.figure)
        self.splitter.setCollapsible(0, False)
        self.splitter.setOpaqueResize(False)
        
        # self.splitter.setStretchFactor(0, 1)
        # self.splitter.setStretchFactor(1, 4) # растягивается в два раза сильнее
        # self.splitter.setGeometry(0, 0, self.width(),  self.height())  #  вручную задаём положение и размер
        # self.splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        for i in range(self.splitter.count() - 1):
            handle = self.splitter.handle(i + 1)
            handle.setEnabled(False)   # делает ручку недоступной
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.splitter)

        emg_processing_layout = QVBoxLayout(self._frame_emg_processing)
        emg_processing_layout.setContentsMargins(6, 6, 6, 6)
        emg_processing_layout.setSpacing(3)
        emg_processing_layout.addLayout(create_hbox([
            self._button_emg_processing_toggle,
            self._button_emg_processing_apply,
        ]))

        emg_details_layout = QVBoxLayout(self._emg_processing_details)
        emg_details_layout.setContentsMargins(0, 0, 0, 0)
        emg_details_layout.setSpacing(2)
        emg_details_layout.addLayout(create_hbox([
            self.check_box_emg_highpass,
            self.spin_box_emg_highpass,
            QLabel("Гц", self._frame_emg_processing),
        ]))
        emg_details_layout.addLayout(create_hbox([
            self.check_box_emg_lowpass,
            self.spin_box_emg_lowpass,
            QLabel("Гц", self._frame_emg_processing),
        ]))
        emg_details_layout.addLayout(create_hbox([
            self.check_box_emg_resampling,
            self.spin_box_emg_resampling,
            QLabel("Гц", self._frame_emg_processing),
        ]))
        emg_details_layout.addLayout(create_hbox([
            self.check_box_emg_baseline,
            QLabel("от", self._frame_emg_processing),
            self.spin_box_emg_baseline_from,
            QLabel("до", self._frame_emg_processing),
            self.spin_box_emg_baseline_to,
            QLabel("мс", self._frame_emg_processing),
        ]))
        emg_processing_layout.addWidget(self._emg_processing_details)
        self._frame_emg_processing.adjustSize()
        self._frame_emg_processing.raise_()

        self.splitter.setSizes([int(self.left_right_ratio * self.width()), int((1-self.left_right_ratio) * self.width())])   # Можно задать начальные пропорции
        

    # --- Сигналы ---
    def _setup_connections(self):
        self.figure.amp_counter.connect(self._on_change_amp_counter)
        self._button_deeper_look.clicked.connect(self._on_deeper_look_button_clicked)
        self._button_movement_detection.clicked.connect(self.movementDetectionActivate.emit)
        self._button_condition_analysis.clicked.connect(self.conditionAnalysisActivate.emit)
        self._check_remove_trend.stateChanged.connect(self._on_remove_trend_changed)
        self._spinbox_channel_a.valueChanged.connect(self._on_channel_pair_changed)
        self._spinbox_channel_b.valueChanged.connect(self._on_channel_pair_changed)
        self._button_emg_processing_toggle.clicked.connect(self._toggle_emg_processing_details)
        self._button_emg_processing_apply.clicked.connect(self._on_emg_processing_apply)
    
    def _on_change_amp_counter(self, value):
        self._label_counter.setText(self._counter_text(value))

    def _counter_text(self, value):
        return f"≥ {self.settings.thr:g} mV:\n    {value} / {self.settings.n_plots_thr}.  "

    def _on_remove_trend_changed(self, _state):
        self.settings.remove_slow_trend = self._check_remove_trend.isChecked()
        self.processingChanged.emit()

    def _on_channel_pair_changed(self, _value=None):
        self.settings.channel_pair = [
            int(self._spinbox_channel_a.value()),
            int(self._spinbox_channel_b.value()),
        ]
        self.processingChanged.emit()

    def _on_emg_processing_apply(self):
        self.sync_emg_processing_settings_from_ui()
        self.emgProcessingApplyRequested.emit()

    def sync_emg_processing_settings_from_ui(self):
        if self.processing_settings is None:
            return
        self.processing_settings.do_emg_highpass_filtering = self.check_box_emg_highpass.isChecked()
        self.processing_settings.emg_highpass_freq_Hz = self.spin_box_emg_highpass.value()
        self.processing_settings.do_emg_lowpass_filtering = self.check_box_emg_lowpass.isChecked()
        self.processing_settings.emg_lowpass_freq_Hz = self.spin_box_emg_lowpass.value()
        self.processing_settings.do_emg_resampling = self.check_box_emg_resampling.isChecked()
        self.processing_settings.emg_resample_freq_Hz = self.spin_box_emg_resampling.value()
        self.processing_settings.do_emg_baseline_correction = self.check_box_emg_baseline.isChecked()
        self.processing_settings.emg_baseline_from_ms = self.spin_box_emg_baseline_from.value()
        self.processing_settings.emg_baseline_to_ms = self.spin_box_emg_baseline_to.value()

    def sync_emg_processing_ui_from_settings(self):
        p = self.processing_settings
        if p is None:
            return
        self.check_box_emg_highpass.setChecked(bool(getattr(p, "do_emg_highpass_filtering", True)))
        self.spin_box_emg_highpass.setValue(float(getattr(p, "emg_highpass_freq_Hz", 10)))
        self.check_box_emg_lowpass.setChecked(bool(getattr(p, "do_emg_lowpass_filtering", True)))
        self.spin_box_emg_lowpass.setValue(int(getattr(p, "emg_lowpass_freq_Hz", 1000)))
        self.check_box_emg_resampling.setChecked(bool(getattr(p, "do_emg_resampling", True)))
        self.spin_box_emg_resampling.setValue(int(getattr(p, "emg_resample_freq_Hz", 2000)))
        self.check_box_emg_baseline.setChecked(bool(getattr(p, "do_emg_baseline_correction", True)))
        self.spin_box_emg_baseline_from.setValue(int(getattr(p, "emg_baseline_from_ms", -75)))
        self.spin_box_emg_baseline_to.setValue(int(getattr(p, "emg_baseline_to_ms", -20)))

    def _toggle_emg_processing_details(self):
        self._set_emg_processing_details_visible(not self._emg_processing_details_visible)

    def _set_emg_processing_details_visible(self, visible):
        self._emg_processing_details_visible = bool(visible)
        self._emg_processing_details.setVisible(self._emg_processing_details_visible)
        self._button_emg_processing_toggle.setText(
            "ОБРАБОТКА ЭМГ ▾" if self._emg_processing_details_visible else "ОБРАБОТКА ЭМГ ▸"
        )
        self._frame_emg_processing.adjustSize()
        self._position_emg_processing_frame()

    def _position_emg_processing_frame(self):
        if not hasattr(self, "_frame_emg_processing"):
            return
        self._frame_emg_processing.adjustSize()
        figure_pos = self.figure.mapTo(self, self.figure.rect().topLeft())
        x = figure_pos.x() + max(0, self.figure.width() - self._frame_emg_processing.width() - 12)
        y = figure_pos.y() + 10
        self._frame_emg_processing.move(x, y)
        self._frame_emg_processing.raise_()

    def set_channel_count(self, channel_count):
        channel_count = max(2, int(channel_count))
        if channel_count == self._channel_count:
            return
        self._channel_count = channel_count
        pair = self._channel_pair()
        if pair[0] == pair[1] or pair[0] > channel_count or pair[1] > channel_count:
            pair = [1, min(2, channel_count)]
            self.settings.channel_pair = pair
        for spin in (self._spinbox_channel_a, self._spinbox_channel_b):
            blocked = spin.blockSignals(True)
            spin.setMaximum(channel_count)
            spin.blockSignals(blocked)
        self._spinbox_channel_a.setValue(pair[0])
        self._spinbox_channel_b.setValue(pair[1])
        self._on_channel_pair_changed()

    def _channel_pair(self):
        pair = list(getattr(self.settings, "channel_pair", [65, 66]) or [65, 66])
        pair = (pair + [66])[:2]
        return [
            max(1, min(int(pair[0]), self._channel_count)),
            max(1, min(int(pair[1]), self._channel_count)),
        ]

    def _on_deeper_look_button_clicked(self):
        if hasattr(self, "_deeper_look_window") and self._deeper_look_window.isVisible():
            self._deeper_look_window.raise_()
            self._deeper_look_window.activateWindow()
            return

        self._deeper_look_window = MEPsDeeperLook(self.settings_dl, self.Fs, monitor=2)

        self._deeper_look_window.show()
        self._deeper_look_window.raise_()

        self.deeperLookActivate.emit() # --> MainWindow --> plot_updater

    # --- Финализация ---
    def _post_init(self):
        self._position_emg_processing_frame()

    # --- События ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_emg_processing_frame()
        # self.figure.resize(self.width(), self.height())
        # self.figure.refresh_plots()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._position_emg_processing_frame)
