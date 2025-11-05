from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QWidget, QVBoxLayout
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

import numpy as np
import pandas as pd

from utils.ui_helpers import shortcut_scale, spin_box, create_button
from utils.layout_utils import create_hbox, create_vbox

from widgets.teps_suppl_plot import TEPsSupplPlot
from widgets.topoplot_plot import TopoPlot

MICROVOLT = "\u03BC"+"V"

class TEPsSupplPanel(QFrame):
    """

    """
    def __init__(self, parent=None, params=None, init_size=[600, 800]):
        super().__init__(parent)
        """Внешний вид виджета"""
        self.resize(init_size[0], init_size[1])
        self.setMinimumWidth(300)

        """Параметры"""
        self.params = params or {}
        self.parent = parent
        self._init_state()

        """Визуальная часть виджета"""
        self._setup_ui()
        self._setup_layout()
        
        """Связи"""
        self._setup_connections()

        """Финализация"""
        self._post_init()

    def _init_state(self):
        
        self.setObjectName("tep_suppl_panel")    # для привязки стиля
        self.ms_to_sample = lambda x: int(x / 1000 * self.params["Fs"])

        self._ratio = self.params["topo_butt_ratio"]

        
    def _setup_ui(self):
        
        self.figure = TEPsSupplPlot(self, w=self.width(), h=self._ratio*self.height(), params=self.params)
        self.figure.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.figure_topo = TopoPlot(self)
        self.figure_topo.setGeometry(50, 50, 400, 300)

        label1 = QLabel("Макс:", self)
        label2 = QLabel(MICROVOLT, self)
        self._spinbox_max_amp = spin_box(0, 1000, self.params["max_amp_mV"], parent=self, w=50)
        self._max_amp = create_hbox([label1, self._spinbox_max_amp, label2])

        label1 = QLabel("от:   ", self)
        label2 = QLabel("до:   ", self)
        label3 = QLabel("мс", self)
        self._spinbox_min_time = spin_box(-300, 0, self.params["xmin_ms"], parent=self, w=50)
        self._spinbox_max_time = spin_box(0, 500, self.params["xmax_ms"], parent=self, w=50)
        self._time_range = create_hbox([label1, self._spinbox_min_time, label2, self._spinbox_max_time, label3])

        self._button_apply = create_button('Применить', checkable=True, parent=self, w=150)

        self._frame_settings = QFrame(self)
    
    def _setup_layout(self):
        
        butt_pos = int(self._ratio*self.height()) - 150
        self.figure.move(0, butt_pos)

        layout_settings = QVBoxLayout(self._frame_settings)
        for layout in [self._max_amp,self._time_range]:
            layout_settings.addLayout(layout)
        layout_settings.addWidget(self._button_apply)

        self._frame_settings.move(0, butt_pos + self.figure.height())

    # --- Сигналы ---
    def _setup_connections(self):
        if False:
            print('skip')
    
    # --- Финализация ---
    def _post_init(self):
        if False:
            print('skip')