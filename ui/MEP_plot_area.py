from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QWidget
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

import numpy as np
import pandas as pd

from utils.ui_helpers import shortcut_scale, spin_box
from widgets.mep_plot import MEPPlot

MICROVOLT = "\u03BC"+"V"

class MEPsPanel(QFrame):
    """
    Панель с настройками, заменяет метод create_box_settings.
    Принимает ссылки на функции из главного окна (update_averaging и т.д.)
    и словари с параметрами (params, SPEED).
    """
    def __init__(self, parent=None, callbacks=None, params=None, init_size=[600, 800]):
        super().__init__(parent)

        self.callbacks = callbacks or {}
        self.params = params or {}
        self.w, self.h = init_size

        self.ms_to_sample = lambda x: int(x / 1000 * self.params["SPEED"]["Fs"])

        self._init_ui()

    def _init_ui(self):
        
        self.setObjectName("mep_main_panel")    # для привязки стиля
        self.resize(self.w, self.h)
        self.setMinimumWidth(300)

        self._setup_ui()
        self._setup_layout()
    
    def _setup_ui(self):
        self.figure = MEPPlot(self, single_w=0.7*self.width(), single_h=300, w=self.width(), h=self.height(), Fs=self.params["SPEED"]['Fs'])
        self.figure.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    
    def _setup_layout(self):
        self.figure.move(0, 0)