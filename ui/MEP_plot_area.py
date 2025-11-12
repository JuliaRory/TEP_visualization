from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QWidget, QSplitter, QVBoxLayout, QSizePolicy
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

import numpy as np
import pandas as pd

from utils.ui_helpers import shortcut_scale, spin_box, create_button
from utils.layout_utils import create_hbox, create_vbox
from widgets.mep_plot import MEPPlot

MICROVOLT = "\u03BC"+"V"

class MEPsPanel(QFrame):
    """
    
    """
    def __init__(self, parent=None,  params=None, init_size=[600, 800]):
        super().__init__(parent)
        """Внешний вид виджета"""
        self.resize(init_size[0], init_size[1])
        
        

        self.setMinimumHeight(50)

        """Параметры"""
        self.params = params or {}
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

        self.ratio = self.params["set_plot_ratio"]
        self.n5_5, self.n5_10 = 0, 0
        self.n10_5, self.n10_10 = 0, 0
        
    # --- Widgets ---
    def _setup_ui(self):
        self.figure = MEPPlot(self, w=(1-self.ratio)*self.width(), h=self.height(), params=self.params)
        self.figure.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._label = QLabel("MEP", self)
        self._label.setFixedWidth(60)
        self._label_counter = QLabel(f">0.5 mV: {self.n5_5}/5; {self.n5_10}/10.\n>1.0 mV: {self.n10_5}/5; {self.n10_10}/10.")
        self._label_counter.setFixedWidth(150)

        label1 = QLabel("Макс:", self)
        label2 = QLabel("мВ", self)
        self._spinbox_max_amp = spin_box(0, 1000, self.params["max_amp_mV"], parent=self, w=50)
        self._max_amp = create_hbox([label1, self._spinbox_max_amp, label2])

        label = QLabel("N:    ", self)
        label_epmty = QLabel("", self)
        self._spinbox_n_plots = spin_box(1, 10, self.params["n_plots"], parent=self, w=50)
        self._n_plots = create_hbox([label, self._spinbox_n_plots, label_epmty])

        label1 = QLabel("от:   ", self)
        label3 = QLabel("мс", self)
        self._spinbox_min_time = spin_box(-300, 0, self.params["xmin_ms"], parent=self, w=50)
        self._time_range_min = create_hbox([label1, self._spinbox_min_time, label3])

        label2 = QLabel("до:   ", self)
        label3 = QLabel("мс", self)
        self._spinbox_max_time = spin_box(0, 500, self.params["xmax_ms"], parent=self, w=50)
        self._time_range_max = create_hbox([label2, self._spinbox_max_time, label3])

        self._button_apply = create_button('Применить', checkable=False, parent=self, w=150)

        self._frame_settings = QFrame(self)

    # --- Layout ---
    def _setup_layout(self):
        layout_settings = QVBoxLayout(self._frame_settings)
        layout_settings.addWidget(self._label)
        layout_settings.addWidget(self._label_counter)
        for layout in [self._max_amp, self._n_plots, self._time_range_min, self._time_range_max]:
            layout_settings.addLayout(layout)
        layout_settings.addWidget(self._button_apply)
        

        self.splitter = QSplitter(Qt.Horizontal, parent=self)        # позволяет изменять размер
        self.splitter.addWidget(self._frame_settings)
        self.splitter.addWidget(self.figure)
        self.splitter.setCollapsible(0, False)
        self.splitter.setOpaqueResize(False)
        
        self.splitter.setSizes([int(self.ratio * self.width()), int((1-self.ratio) * self.width())])   # Можно задать начальные пропорции
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 4) # растягивается в два раза сильнее
        self.splitter.setGeometry(0, 0, self.width(),  self.height())  #  вручную задаём положение и размер
        self.splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        for i in range(self.splitter.count() - 1):
            handle = self.splitter.handle(i + 1)
            handle.setEnabled(False)   # делает ручку недоступной

    # --- Сигналы ---
    def _setup_connections(self):
        if False:
            print('skip')
    
    # --- Финализация ---
    def _post_init(self):
        if False:
            print('skip')

    # --- События ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.figure.resize(self.width(), self.height())