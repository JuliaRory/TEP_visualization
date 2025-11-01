from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QWidget
)
from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import Qt

import numpy as np
import pandas as pd

from utils.ui_helpers import shortcut_scale, spin_box, fit_font_to_width_spinbox

from widgets.teps_plot import TEPsPlot
MICROVOLT = "\u03BC"+"V"

class TEPsPanel(QFrame):
    def __init__(self, parent=None, params=None, init_size=(600, 800)):
        super().__init__(parent)

        """Внешний вид виджета"""
        self.resize(init_size[0], init_size[1])
        self.setMinimumWidth(300)
        
        """Параметры"""
        self.params = params or {}
        self._init_state()

        """Визуальная часть виджета"""
        self._setup_ui()
        self._setup_layout()
        self._setup_connections()

        """Финализация"""
        self._post_init()

    def _init_state(self):
        
        self.setObjectName("tep_main_panel")    # для привязки стиля

        self.ymin, self.ymax = self.params["plot"]["ymin"], self.params["plot"]["ymax"]
        self.xmin, self.xmax = self.params["plot"]["xmin"], self.params["plot"]["xmax"]
        
        self.ms_to_sample = lambda x: int(x / 1000 * self.params["SPEED"]["Fs"])
        self.n_samples = self.ms_to_sample(self.params["SPEED"]["window_end"] - self.params["SPEED"]["window_start"])       # длина одной эпохи в сэмплах
        self.x_shift = self.ms_to_sample(0 - self.params["SPEED"]["window_start"])                                       # смещение относительно нуля для графиков в сэпмлах

        filename = r".\resources\mumeg_mks64.ced"
        self.df_orig = pd.read_csv(filename, sep="\t")

        self.channels = self.df_orig.labels.values

        self.left_pad, self.right_pad = 0, 0#20, 20   
        self.top_pad, self.bottom_pad = 100, 0#120, 10
        self._calculate_positions() # --> create self.df_pos
        self.scale_left, self.scale_bottom = int( self.df_pos['x'].min()+0.2*self.plot_width), int(self.df_pos['y'].max()+0.2*self.plot_height)                     #  позиция для пустых осей для задания масштаба
        self._positions = np.concatenate([self.df_pos[['x', 'y']].values, np.array([[self.scale_left, self.scale_bottom]])], axis=0)      #  добавляем к списку позиций основных графиков позицию пустых осей
    
    def _setup_ui(self):
        
        """Создаём спинбоксы (и shortcut) для масштабирования графиков"""
        self.spin_box_scale_ymin = spin_box(-10000, 0, self.ymin, step=10, parent=self) 
        self.spin_box_scale_ymax = spin_box(1, 10000, self.ymax, step=10, parent=self) 
        self.spin_box_scale_xmin = spin_box(-1000, 0, self.xmin, step=5, parent=self) 
        self.spin_box_scale_xmax = spin_box(1, 1000, self.xmax, step=5, parent=self) 

        shortcut_scale(keyword="Alt+Up", spin1=self.spin_box_scale_ymax, spin2=self.spin_box_scale_ymin, action='more', parent=self) 
        shortcut_scale(keyword="Alt+Down", spin1=self.spin_box_scale_ymax, spin2=self.spin_box_scale_ymin, action='less', parent=self) 
        shortcut_scale(keyword="Alt+Left", spin1=self.spin_box_scale_xmax, spin2=self.spin_box_scale_xmin, action='less', parent=self) 
        shortcut_scale(keyword="Alt+Right", spin1=self.spin_box_scale_xmax, spin2=self.spin_box_scale_xmin, action='more', parent=self) 

        self._label_scale_y = QLabel(MICROVOLT, parent=self) 
        self._label_scale_x = QLabel('ms', parent=self) 

        """Создаём полотно для графиков"""
        self.figure = TEPsPlot(self, self._positions, single_w=self.plot_width, single_h=self.plot_height, w=self.width(), h=self.height(), channels=self.channels)
        
        self.figure.setAttribute(Qt.WA_TransparentForMouseEvents, True)                                               # делаем фигуру "прозрачной", чтобы она не перекрывала другие виджеты
    
    # --- Layout ---
    def _setup_layout(self):
        self.figure.move(0, 0)  # помещаем график
                                # масштабирующие спинбоксы размещаем во время resize_event

    # --- Сигналы ---
    def _setup_connections(self):
        for spin_box in [self.spin_box_scale_ymin, self.spin_box_scale_ymax, self.spin_box_scale_xmin, self.spin_box_scale_xmax]:
            spin_box.valueChanged.connect(self._update_scale)
        
    # --- Логика ---
    def _update_scale(self):
        xmax = self.ms_to_sample(self.spin_box_scale_xmax.value())
        xmin = self.ms_to_sample(self.spin_box_scale_xmin.value())
        
        ymax = self.spin_box_scale_ymax.value()
        ymin = self.spin_box_scale_ymin.value()

        self.figure.update_axes([xmin, xmax, ymin, ymax])

    def _calculate_positions(self):
        df = self.df_orig.copy()

        th = np.pi / 180 * np.array(df.theta.values)

        total_width, total_height = self.width(), self.height()

        usable_width = total_width - (self.left_pad + self.right_pad)
        usable_height = total_height - (self.top_pad + self.bottom_pad)

        radius_norm_x = df.radius.values / (df.radius.max() - df.radius.min())
        df_center = df.loc[df.Y == 0]
        radius_norm_y = df.radius.values / (df_center.radius.max() - df_center.radius.min())

        self.plot_width = int((usable_width // 11) * 0.93)
        self.plot_height = int((usable_height // 9)  * 0.95)

        scale_x = ((usable_width-self.plot_width) / 2) * 1
        scale_y = ((usable_height-self.plot_height) / 2) * 1

        df['y_centered'] = (radius_norm_y * np.cos(th) * scale_y).astype(int)
        df['x_centered'] = (radius_norm_x * np.sin(th) * scale_x).astype(int)

        x_center, y_center = self.left_pad + (usable_width-self.plot_width) // 2, self.bottom_pad + (usable_height - self.plot_height) // 2
        df['x'] = df['x_centered'] + x_center
        df['y'] = df['y_centered'] + y_center
  
        self.df_pos = df[['x', 'y', 'labels', 'x_centered', 'y_centered']]
    
    def _update_inner_sizes(self):

        self.figure.resize(self.width(), self.height())

        """Обновление позиций графика"""
        self._calculate_positions()                                                                  # рассчитать новые позиции графиков
        self.scale_left, self.scale_bottom = int( self.df_pos['x'].min()+0.2*self.plot_width), int(self.df_pos['y'].max()+0.2*self.plot_height)                     #  позиция для пустых осей для задания масштаба
        self._positions = np.concatenate([self.df_pos[['x', 'y']].values, np.array([[self.scale_left, self.scale_bottom]])], axis=0)      #  добавляем к списку позиций основных графиков позицию пустых осей

        x_aver, y_aver = self.plot_width, self.plot_height                                            # новые размеры графиков

        self.xmax, self.xmin = self.spin_box_scale_xmax.value(), self.spin_box_scale_xmin.value()
        self.ymax, self.ymin = self.spin_box_scale_ymax.value(), self.spin_box_scale_ymin.value()

        # self.figure.update_position(positions, single_w=x_aver, single_h=y_aver, w=self.width(), h=self.height())
        #self.update_label_pos(x_aver, y_aver, xmin, xmax, ymin, ymax)
      
        """Обновление положения спинбоксов для масштабирования графиков"""
        width, height = int(x_aver*0.3), int(y_aver *0.2)                                           # размеры спинбоксов
        width = 40 if width < 40 else width
        height = 20 if height < 20 else height

        scale_left = self.scale_left - width - int(width*0.2)
        scale_right = self.scale_left  + self.plot_width + int(width*0.2)
        scale_bottom =self.height() - ( self.scale_bottom ) + int(height*0.2)
        scale_top = self.height() - (self.scale_bottom + self.plot_height + height) - int(height*0.2)
        scale_center_x = self.scale_left + int(self.plot_width / (self.xmax-self.xmin) * abs(self.xmin))
        scale_center_y = self.height() - (self.scale_bottom + self.plot_height//2) - height//2

        self.spin_box_scale_ymax.move(scale_center_x, scale_top)
        self.spin_box_scale_ymin.move(scale_center_x, scale_bottom)
        self.spin_box_scale_xmin.move(scale_left, scale_center_y)
        self.spin_box_scale_xmax.move(scale_right, scale_center_y)

        self._label_scale_y.move(self.spin_box_scale_ymax.x()+width, self.spin_box_scale_ymax.y())
        self._label_scale_x.move(self.spin_box_scale_xmax.x()+width, self.spin_box_scale_xmax.y())

        self.spin_box_scale_ymin.resize(width, height)
        self.spin_box_scale_ymax.resize(width, height)
        self.spin_box_scale_xmax.resize(width, height)
        self.spin_box_scale_xmin.resize(width, height)

        fit_font_to_width_spinbox(self.spin_box_scale_xmax)
        fit_font_to_width_spinbox(self.spin_box_scale_ymax)
        fit_font_to_width_spinbox(self.spin_box_scale_xmin)
        fit_font_to_width_spinbox(self.spin_box_scale_ymin)

        f_label = self.font()
        f_label.setPixelSize(int(height * 0.8))
        self._label_scale_y.setFont(f_label)
        self._label_scale_x.setFont(f_label)

    # --- Финализация ---
    def _post_init(self):
        self.figure.update_axes([self.ms_to_sample(self.xmin), self.ms_to_sample(self.xmax), self.ymin, self.ymax])                       #  задаём оси с правильным масштабом
        self.figure.set_x_shift(-self.x_shift, self.n_samples)                                                                            #  задаём размеры эпохи и смещение относительно 0 по оси абсцисс

    # --- События ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_inner_sizes()


   

        

       
        

    

    
    

    