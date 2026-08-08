from PyQt5.QtWidgets import QCheckBox, QFrame,  QHBoxLayout, QLabel,  QSplitter, QVBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal

from utils.ui_helpers import  create_button, create_spin_box
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
    def __init__(self, parent=None,   Fs=5000, settings=None, settings_dl=None, init_size=[600, 800]):
        super().__init__(parent)
        """Внешний вид виджета"""
        self.resize(init_size[0], init_size[1])
        self.setMinimumHeight(50)

        """Параметры"""
        self.Fs = Fs
        self.settings = settings
        self.settings_dl = settings_dl

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

    def set_channel_count(self, channel_count):
        channel_count = max(2, int(channel_count))
        if channel_count == self._channel_count:
            return
        self._channel_count = channel_count
        for spin in (self._spinbox_channel_a, self._spinbox_channel_b):
            blocked = spin.blockSignals(True)
            spin.setMaximum(channel_count)
            spin.setValue(max(1, min(int(spin.value()), channel_count)))
            spin.blockSignals(blocked)
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
        if False:
            print('skip')

    # --- События ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # self.figure.resize(self.width(), self.height())
        # self.figure.refresh_plots()
