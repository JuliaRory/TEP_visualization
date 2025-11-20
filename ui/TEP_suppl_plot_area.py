from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QWidget, QVBoxLayout
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

import matplotlib.pyplot as plt

import numpy as np
import pandas as pd

from utils.ui_helpers import shortcut_scale, spin_box, create_button
from utils.layout_utils import create_hbox, create_vbox

from widgets.teps_suppl_plot import supplPlot
# from widgets.meps_suppl_plot import MEPsSupplPlot
from widgets.topoplot_plot import TopoPlot, ColorBar
# from widgets.interactive_plot import PlotWindow

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
        
        self.figure_TEP = supplPlot(self, 
                                        w=self.width(), h=(1-self._ratio)*self.height()//2, 
                                        params=self.params["TEP"],
                                        Fs=self.params["Fs"])
        self.figure_TEP.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self.figure_MEP = supplPlot(self, 
                                    w=self.width(), h=(1-self._ratio)*self.height()//2, 
                                    params=self.params["MEP"],
                                        Fs=self.params["Fs"])
        self.figure_MEP.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        if self.params["topoplot"]["draw"]:
            n = self.params['n_plots']
            w_available = 0.8 * self.width()
            w_topo = int(w_available // n)
            self.figure_topo = [TopoPlot(self, w=w_topo, timestamp=self.params["timestamps_ms"][i], params=self.params["topoplot"]) for i in range(n)]
            
            self.colorbar = ColorBar(self, image=self.figure_topo[0].im)

        label1 = QLabel("Макс:", self)
        label2 = QLabel(MICROVOLT, self)
        self._spinbox_max_amp = spin_box(0, 10000, self.params["TEP"]["amp"], parent=self, w=50, step=10)
        self._max_amp = create_hbox([label1, self._spinbox_max_amp, label2])

        label1 = QLabel("от:   ", self)
        label2 = QLabel("до:   ", self)
        label3 = QLabel("мс", self)
        self._spinbox_min_time = spin_box(-300, 0, self.params["xmin_ms"], parent=self, w=50, step=5)
        self._spinbox_max_time = spin_box(0, 500, self.params["xmax_ms"], parent=self, w=50, step=5)
        self._time_range = create_hbox([label1, self._spinbox_min_time, label2, self._spinbox_max_time, label3])

        self._button_interactive_plot = create_button(text="Интерактив", disabled=True)

        """Для топоплотов"""
        ts = self.params["timestamps_ms"]
        
        self.spinbox_ts_1 = spin_box(-20, 1000, ts[0], parent=self, w=50, step=1)
        self.spinbox_ts_2 = spin_box(-20, 1000, ts[1], parent=self, w=50, step=1)
        self.spinbox_ts_3 = spin_box(-20, 1000, ts[2], parent=self, w=50, step=1)
        self.spinbox_ts = [self.spinbox_ts_1, self.spinbox_ts_2, self.spinbox_ts_3]

        # self._button_apply = create_button('Применить', checkable=True, parent=self, w=150)

        self._frame_settings = QFrame(self)
    
    def _setup_layout(self):
        if self.params["topoplot"]["draw"]:
            n = self.params['n_plots']
            d_width = (1-0.8-0.1) * self.width() / n
            left = int(0.1 * self.width())
            for i, topoplot in enumerate(self.figure_topo):
                left_new = int(left+(topoplot.width() + d_width)*i)
                topoplot.move(left_new, left)
                self.spinbox_ts[i].move(left_new + topoplot.width()//2-25, left-30)
            
            self.colorbar.move(0, 0)

        butt_pos = int((1-self._ratio)*self.height()) - self.figure_TEP.height()
        self.figure_TEP.move(0, butt_pos)
        self.figure_MEP.move(0, butt_pos + self.figure_TEP.height() + 10)

        # self._button_interactive_plot.move(20, butt_pos - 20)

        layout_settings = QVBoxLayout(self._frame_settings)
        for layout in [self._max_amp,self._time_range]:
            layout_settings.addLayout(layout)
        # layout_settings.addWidget(self._button_apply)

        self._frame_settings.move(0, butt_pos + self.figure_TEP.height() * 2 + 20)

    # --- Сигналы ---
    def _setup_connections(self):
        for spin_box in [self._spinbox_min_time, self._spinbox_max_time, self._spinbox_max_amp]:
            spin_box.valueChanged.connect(self._update_scale)
        
        self._button_interactive_plot.clicked.connect(self._on_interactive_plot_button_clicked)
    
    # --- Логика ---
    def _update_scale(self):
        xmax = self._spinbox_max_time.value()
        xmin = self._spinbox_min_time.value()
        ymax = self._spinbox_max_amp.value()

        self.figure_TEP.update_axes(xmax, xmin, ymax)
        self.figure_MEP.update_axes(xmax, xmin, self.params["MEP"]["amp"])

    def _on_interactive_plot_button_clicked(self):
        self.inter_plot = PlotWindow()
        
        self.inter_plot.show()

    # --- Финализация ---
    def _post_init(self):
        self._update_scale()
        

    # --- События ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.figure_TEP.resize(self.width(), int((1 - self._ratio)*self.height()//2))
        self.figure_MEP.resize(self.width(), int((1 - self._ratio)*self.height()//2))
    