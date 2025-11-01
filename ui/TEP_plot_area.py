from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QWidget
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

import numpy as np
import pandas as pd

from utils.ui_helpers import shortcut_scale, spin_box

from widgets.teps_plot import TEPsPlot
MICROVOLT = "\u03BC"+"V"

class TEPsPanel(QFrame):
    """
    Панель с настройками. 
    """
    def __init__(self, parent=None, params=None, init_size=[600, 800]):
        super().__init__(parent)

        self.params = params or {}
        self.w, self.h = init_size

        self.ms_to_sample = lambda x: int(x / 1000 * self.params["SPEED"]["Fs"])

        self._init_ui()

    def _init_ui(self):
        
        self.setObjectName("tep_main_panel")    # для привязки стиля
        self.resize(self.w, self.h)
        self.setMinimumWidth(300)

        self._calculate_positions() # --> create self.df_pos
        self._setup_ui()
        self._setup_layout()
    
    def _setup_ui(self):
        
        y_aver = self.plot_height 
        x_aver = self.plot_width

        self.box_scale = QWidget(self)
        
        ymin, ymax = self.params["plot"]["ymin"], self.params["plot"]["ymax"]
        xmin, xmax = self.params["plot"]["xmin"], self.params["plot"]["xmax"]

        self.spin_box_scale_ymin = spin_box(-10000, 0, ymin, step=10, parent=self.box_scale, function=self._update_scale)
        self.spin_box_scale_ymax = spin_box(1, 10000, ymax, step=10, parent=self.box_scale, function=self._update_scale)
        self.spin_box_scale_xmin = spin_box(-1000, 0, xmin, step=5, parent=self.box_scale, function=self._update_scale)
        self.spin_box_scale_xmax = spin_box(1, self.params["SPEED"]["window_end"] , xmax, step=5, parent=self.box_scale,  function=self._update_scale)
        
        shortcut_scale(keyword="Alt+Up", spin1=self.spin_box_scale_ymax, spin2=self.spin_box_scale_ymin, action='more')
        shortcut_scale(keyword="Alt+Down", spin1=self.spin_box_scale_ymax, spin2=self.spin_box_scale_ymin, action='less')
        shortcut_scale(keyword="Alt+Left", spin1=self.spin_box_scale_xmax, spin2=self.spin_box_scale_xmin, action='less')
        shortcut_scale(keyword="Alt+Right", spin1=self.spin_box_scale_xmax, spin2=self.spin_box_scale_xmin, action='more')

        self.label_scale_y = QLabel(MICROVOLT, self.box_scale)
        self.label_scale_x = QLabel('ms', self.box_scale)
        
        xpos, ypos = self.df_pos['x'].min()-0*x_aver, int(self.df_pos['y'].max()+0.2*y_aver)
        positions = np.concatenate([self.df_pos[['x', 'y']].values, np.array([[xpos, ypos]])], axis=0)

        self.figure = TEPsPlot(self, positions, single_w=x_aver, single_h=y_aver, w=self.width(), h=self.height(), channels=self.channels)

        self.ms_to_sample = lambda x: int(x / 1000 * self.params["SPEED"]["Fs"])                                  # функция для пересчёта мс в сэмплы
        self.n_samples = self.ms_to_sample(self.params["SPEED"]["window_end"] - self.params["SPEED"]["window_start"])       # длина эпохи в сэмплах
        self.time_shift = self.ms_to_sample(0 - self.params["SPEED"]["window_start"])                             # смещение относительно нуля для графиков в сэпмлах

        self.figure.set_x_shift(-self.time_shift, self.n_samples)

        self.figure.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        
    def _setup_layout(self):
        self.figure.move(0, 0)

    def _update_scale(self):
        xmax = self.ms_to_sample(self.spin_box_scale_xmax.value())
        xmin = self.ms_to_sample(self.spin_box_scale_xmin.value())
        
        ymax = self.spin_box_scale_ymax.value()
        ymin = self.spin_box_scale_ymin.value()

        self.figure.update_axes([xmin, xmax, ymin, ymax])
    
    def _update_scale_shit_positions(self, x_aver, y_aver, xmin, xmax, ymin, ymax):
        width, height = int(x_aver*0.6), int(y_aver *0.3)

        xpad, ypad = int(0.6*x_aver),  int(0.3*y_aver)
        x_axes_pos = int(x_aver / (xmax-xmin) * abs(xmin)) + xpad 
        y_axes_pos = int(y_aver / (ymax-ymin) * abs(ymax)) + ypad

        self.spin_box_scale_ymax.move(x_axes_pos-width//4, ypad-height)
        self.spin_box_scale_ymin.move(x_axes_pos-width//4, y_aver + ypad)
        self.spin_box_scale_xmin.move(xpad-width, y_axes_pos-height//2)
        self.spin_box_scale_xmax.move(x_aver+xpad, y_axes_pos-height//2)

        width = 40 if width < 40 else width
        height = 20 if height < 20 else height
        self.label_scale_y.move(self.spin_box_scale_ymax.x()+width, self.spin_box_scale_ymax.y())
        self.label_scale_x.move(self.spin_box_scale_xmax.x()+width, self.spin_box_scale_xmax.y())

        self.spin_box_scale_ymin.resize(width, height)
        self.spin_box_scale_ymax.resize(width, height)
        self.spin_box_scale_xmax.resize(width, height)
        self.spin_box_scale_xmin.resize(width, height)

        self.fit_font_to_width_spinbox(self.spin_box_scale_xmax)
        self.fit_font_to_width_spinbox(self.spin_box_scale_ymax)
        self.fit_font_to_width_spinbox(self.spin_box_scale_xmin)
        self.fit_font_to_width_spinbox(self.spin_box_scale_ymin)

        f_label = self.font()
        f_label.setPixelSize(int(height * 0.8))
        self.label_scale_y.setFont(f_label)
        self.label_scale_x.setFont(f_label)

    def fit_font_to_width_spinbox(self, spinbox, padding_w=0, padding_h=0):
        
        width = spinbox.width() - padding_w
        height = spinbox.height() - padding_h
        if width <= 0 or height <= 0:
            return

        font = spinbox.font()
        fs = font.pointSize()
        if fs <= 0:
            fs = 12

        max_text = str(spinbox.maximum())
        fm = QFontMetrics(font)

        # уменьшаем, пока и ширина, и высота не влезают
        while (fm.horizontalAdvance(max_text) > width or fm.height() > height) and fs > 1:
            fs -= 1
            font.setPointSize(fs)
            fm = QFontMetrics(font)

        spinbox.setFont(font)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_inner_sizes()

    def _update_inner_sizes(self):
        width = self.width()
        height = self.height()

        self._calculate_positions()
        y_aver = self.plot_height 
        x_aver = self.plot_width 

        xpos, ypos = self.df_pos['x'].min()-0*x_aver, int(self.df_pos['y'].min()-0.2*y_aver)
        # self.scale_plot.setGeometry(xpos, ypos, x_aver, y_aver)

        xmax = self.spin_box_scale_xmax.value()
        xmin = self.spin_box_scale_xmin.value()
        ymax = self.spin_box_scale_ymax.value()
        ymin = self.spin_box_scale_ymin.value()

        self._update_scale_shit_positions(x_aver, y_aver, xmin, xmax, ymin, ymax)

        xpad, ypad = int(0.6*x_aver),  int(0.3*y_aver)
        self.box_scale.setGeometry(xpos-xpad, ypos-ypad, x_aver+xpad*2, y_aver+ypad*2)

        self.figure.resize(self.width(), self.height())

        positions = np.concatenate([self.df_pos[['x', 'y']].values, np.array([[xpos, int(self.df_pos['y'].max()+0.3*y_aver)]])], axis=0)
        # self.figure.update_position(positions, single_w=x_aver, single_h=y_aver, w=self.width(), h=self.height())
        self.figure.update_axes([self.ms_to_sample(xmin), self.ms_to_sample(xmax), ymin, ymax])
        #self.update_label_pos(x_aver, y_aver, xmin, xmax, ymin, ymax)

    def _calculate_positions(self):
        filename = r".\resources\mumeg_mks64.ced"
        df = pd.read_csv(filename, sep="\t")

        self.channels = df.labels.values

        th = np.pi / 180 * np.array(df.theta.values)

        total_width, total_height = self.width(), self.height()
        left_pad, right_pad = 0, 0#20, 20   
        top_pad, bottom_pad = 60, 0#120, 10

        usable_width = total_width - (left_pad + right_pad)
        usable_height = total_height - (top_pad + bottom_pad)

        radius_norm = df.radius.values / (df.radius.max() - df.radius.min())

        self.plot_width = usable_width // 11
        self.plot_height = usable_height // 8#9

        scale_x = ((usable_width-self.plot_width) / 2) * 1#0.9
        scale_y = (usable_height / 2) * 1

        df['y_centered'] = (radius_norm * np.cos(th) * scale_y).astype(int)
        df['x_centered'] = (radius_norm * np.sin(th) * scale_x).astype(int)

        x_center, y_center = left_pad + (usable_width-self.plot_width) // 2, bottom_pad + usable_height // 2
        df['x'] = df['x_centered'] + x_center
        df['y'] = df['y_centered'] + y_center
  
        self.data = dict((pos, []) for pos in df['labels'].values)

        self.df_pos = df[['x', 'y', 'labels', 'x_centered', 'y_centered']]