from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel,  QFrame,  QVBoxLayout

from utils.ui_helpers import create_spin_box, create_button
from utils.layout_utils import create_hbox
from ui.widgets.mep_plot import MEPPlot

from utils.widget_placement import place_widget


class MEPsDeeperLook(QWidget):
    
    def __init__(self, settings, Fs):
        super().__init__()

        self.setWindowTitle("Motor Evoked Potentials")
        self.resize(1700, 500)
        
        place_widget(self, monitor=3, coordinates=(10, 1080-600))

        self.Fs = Fs
        self.settings = settings # single mep plot settings

        self._init_state()
        self._setup_ui()
        self._setup_layout()
        self._setup_connections()

    def _init_state(self):
        n_line = 3

        self.ratio = 0.0
        self.line_w = (1-self.ratio) * self.width()
        self.line_h = (1-self.ratio) * self.height() //2


    def _setup_ui(self):
        self._setup_figures_widgets()
        self._setup_mep_settings_widgets()
        self._setup_thr_widgets()
    
    def _setup_thr_widgets(self):
        self._frame_thr = QFrame(self)
        self._frame_thr.setContentsMargins(0, 0, 0, 0)
        self._frame_thr.setFixedHeight(int(0.5 * self.line_h))

        self.spinbox_thr = create_spin_box(0, 100, self.settings.thr, data_type="float", decimals=2, step=.1, parent=self._frame_thr, w=50)
        self.spinbox_thr_n_plots = create_spin_box(0, 20, self.settings.n_plots_thr, parent=self._frame_thr, w=50)
        
        self._label_thr = QLabel(f"Выше порога: {0}/{self.settings.n_plots_thr}")
        self._label_thr.setObjectName("label_thr_counter")
        self._label_thr.setFixedWidth(500)


    def _setup_figures_widgets(self):
        n = self.settings.n_plots
        self.figure = MEPPlot(self, w=self.line_w, h=self.line_h, settings=self.settings, Fs=self.Fs, titles=[f"# {i+1}" for i in range(n)], emphasize_first=True)
        self.figure.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    
    def _setup_mep_settings_widgets(self):
        self._frame_mep_settings = QFrame(self)
        self._frame_mep_settings.setContentsMargins(0, 0, 0, 0)
        self._frame_mep_settings.setFixedHeight(int(self.line_h))

        label1 = QLabel("Макс:", self._frame_mep_settings)
        label2 = QLabel("мВ", self._frame_mep_settings)
        self._spinbox_max_amp = create_spin_box(0, 1000, self.settings.max_amp_mV, parent=self._frame_mep_settings, w=50)
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

        self._button_apply = create_button('Применить', disabled=False, parent=self._frame_mep_settings, w=150)
        
    def _setup_layout(self):
        self._setup_mep_settings()
        self._setup_thr_settings()

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
        grid.addWidget(self._frame_thr, row, 1, 1, 2)
        row = 1
        grid.addWidget(self._frame_mep_settings, row, 0, 1, 1)
        grid.addWidget(self.figure, row, 1, 1, 5)
        
        row = 2   
        # grid.addLayout(self.layout_settings, 0, 0, 1, 1) ## emg filters
        

    def _setup_thr_settings(self):
        self.grid_thr = QGridLayout(self._frame_thr)
        self.grid_thr.setRowStretch(0, 0)
        self.grid_thr.setRowStretch(1, 0)
        
        layout_thr_value = create_hbox([QLabel("Порог: "), self.spinbox_thr, QLabel("mV")])
        layout_n_plots_value = create_hbox([QLabel("Кол-во попыток: "), self.spinbox_thr_n_plots])

        self.grid_thr.addLayout(layout_thr_value, 0, 0)
        self.grid_thr.addLayout(layout_n_plots_value, 1, 0)

        self.grid_thr.addWidget(self._label_thr, 0, 1)

        # self.grid_thr.columnStretch(0)
        # self.grid_thr.rowStretch(0)

    def _setup_firuges(self):
        self.layout_figures = QVBoxLayout()
        self.layout_figures.addWidget(self.figure_1)
    
    def _setup_mep_settings(self):
        self.layout_settings = QVBoxLayout(self._frame_mep_settings)
        for layout in [self._max_amp, self._n_plots, self._time_range_min, self._time_range_max]:
            self.layout_settings.addLayout(layout)
        self.layout_settings.addWidget(self._button_apply)

        self.layout_settings.addStretch()
    
    def update_emg(self, emg2plot):
        line1_new_value = emg2plot

        line2_new_value = self.figure_1.lines[-1].get_ydata()
        line3_new_value = self.figure_2.lines[-1].get_ydata()
        
        self.figure_1.update_emg(line1_new_value, normalize=True)
        self.figure_2.update_emg(line2_new_value, normalize=False)
        self.figure_3.update_emg(line3_new_value, normalize=False)


    def _setup_connections(self):
        self.figure.amp_counter.connect(lambda value: self._label_thr.setText(f"Выше порога: {value}/{self.settings.n_plots_thr}"))