from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence, QFont, QFontMetrics, QPalette, QColor
from PyQt5.QtWidgets import (QWidget, QGridLayout, QPushButton, QShortcut, QLabel, QSpinBox, QDoubleSpinBox, 
                            QCheckBox, qApp, QComboBox, QFrame, QHBoxLayout, QSizePolicy)
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import json
from scipy import signal
import time
from collections import deque

from utils import RollingMean, RollingMedian, RollingTrimMean, CheckableComboBox

WIDTH_SET, HEIGHT_SET = 1700, 900  # параметры изначального окна интерфейса
MICROVOLT = "\u03BC"+"V"
filename = r".\resources\mumeg_mks64.ced"
df = pd.read_csv(filename, sep="\t")
CHANNELS = df.labels.values

class PlotCanvas(FigureCanvas):
    """Класс для отрисовки графиков"""
    def __init__(self, parent=None, positions=None, single_w=300, single_h=200, w=1000, h=700, Fs=5000, n_emg=5, dpi=100):
        figsize = (w/dpi, h/dpi)
        self.fig = Figure(figsize=figsize, dpi=100) 
        #self.fig = Figure(constrained_layout=True)
        self.fig.patch.set_alpha(0.0)                          # Делаем фон холста matplolib прозрачным
        
        super().__init__(self.fig)
        self.setStyleSheet("background-color:transparent;")    # делаем виджет прозрачнымs
        
        self.setParent(parent)
        
        fig_width_px, fig_height_px = figsize[0] * dpi, figsize[1] * dpi    # размеры фигуры в пикселях

        titles = CHANNELS.tolist() + ['']
        self.axes = []
        self.lines = []

        width = single_w / fig_width_px
        height = single_h / fig_height_px
        for i, (x_px, y_px) in enumerate(positions):  # создаём оси по заданным пиксельным координатам
            left = x_px / fig_width_px
            bottom = y_px / fig_height_px
            ax = self.fig.add_axes([left, bottom, width, height])

            ax.margins(0.05)
            ax.patch.set_alpha(0.0)
            self.center_axes(ax)      # центруем оси, чтобы они проходили через (0, 0)

            ax.set_title(titles[i], loc='center', y=0.8)

            line, = ax.plot([], [])
            self.axes.append(ax)
            self.lines.append(line)

        self.update_axes([-10, 50, -100, 100])

        emg_w, emg_h = 2 * width, 2 * height
        emg_left = w/fig_width_px - emg_w -20/fig_width_px
        emg_bottom = h/fig_height_px - emg_h -20/fig_height_px
        self.ax_emg = self.fig.add_axes([emg_left, emg_bottom, emg_w, emg_h])
        self.ax_emg.set_ylim([-1, 1])
        self.ax_emg.set_xlim([-15*Fs/1000, 100*Fs/1000])
        self.ax_emg.set_xticks(np.arange(0, 101, 20) *Fs/1000, np.arange(0, 101, 20))
        self.ax_emg.set_ylabel('mV', rotation = 360, labelpad=2,  loc='top')
        self.ax_emg.set_xlabel('ms', loc='right')
        self.ax_emg.grid(True, alpha=.4, color='gray')
        self.lines_emg = [self.ax_emg.plot([], []) for _ in range(n_emg)]

        self.fig.canvas.draw_idle()
        self.backgrounds = [self.fig.canvas.copy_from_bbox(ax.bbox) for ax in self.axes]
                  
    def center_axes(self, ax):
        """центруем оси, чтобы они проходили через (0, 0)"""
        ax.spines['left'].set_position('zero')
        ax.spines['bottom'].set_position('zero')
        ax.spines['right'].set_color('none')
        ax.spines['top'].set_color('none')

    def refresh_plot(self):
        self.axes.clear()                       # если уже что-то было - удалить
        #self.axes.set_position([0.1, 0.1, 0.8, 0.8])
        self.axes.margins(0.05)
        self.axes.patch.set_alpha(0.0)
        self.center_axes() 

        self.update_axes(self)

    def update_position(self, positions=None, single_w=300, single_h=200, w=1000, h=700, dpi=100):
        fig_w, fig_h = self.fig.get_size_inches() * self.fig.dpi  # ширина и высота в пикселях

        def px_to_norm(x_px, y_px, w_px, h_px):
            return [x_px / fig_w, y_px / fig_h, w_px / fig_w, h_px / fig_h]

        for i, (x_px, y_px) in enumerate(positions):  # создаём оси по заданным пиксельным координатам
            self.axes[i].set_position(px_to_norm(x_px, y_px, single_w, single_h))
        
        self.fig.set_size_inches(w/dpi, h/dpi, forward=True)

        self.fig.canvas.draw_idle()
        self.backgrounds = [self.fig.canvas.copy_from_bbox(ax.bbox) for ax in self.axes]

    def update_data(self, i, y, x_shift=0):
        """
        y [MICROVOLT] - TEP
        x_shift [sample] - смещение влево по оси времени 
        """
        x = np.linspace(-x_shift, len(y)-x_shift, len(y))
        #data = np.sin(x)
        self.lines[i].set_data(x, y)
        self.axes[i].draw_artist(self.lines[i])
    
    def update_image(self):
        self.fig.canvas.draw_idle()
        
    def update_emg(self, emg, x_shift=0):
        length = len(emg[0])
        x = np.linspace(x_shift, length+x_shift, length)
        n = len(emg)
        for i in range(n):
            line = self.lines_emg[i][0]
            line.set_data(x, (0.5 + i) * emg[i])
            alpha = 1.0 if len(emg)==1 else 0.3 + 0.7 * (i / (len(emg)-1))
            lw = 2 if len(emg)==1 else 0.8 + 1.8 * (i / (len(emg)-1))
            line.set_alpha(alpha)
            line.set_linewidth(lw)
            line.set_color('blue')
            self.ax_emg.draw_artist(line)
        self.fig.canvas.draw_idle()

    def update_axes(self, limits):
        """
        xmin, xmax [sample] 
        ymn, ymax [MICROVOLT]
        """
        xmin, xmax, ymin, ymax = limits
        # xmid, ymid =  xmin / 4, ymin / 4
        # print(xmid, ymid)
        x_changed = not hasattr(self, "_last_xlim") or (self._last_xlim != (xmin, xmax))
        y_changed = not hasattr(self, "_last_ylim") or (self._last_ylim != (ymin, ymax))
        tick_initialized = hasattr(self, "_tick_initialized")
        
        for i, ax in enumerate(self.axes):
            ax.set_xlim((xmin, xmax))
            ax.set_ylim((ymin, ymax))

            if x_changed:
                ax.set_xticks(np.linspace(0, xmax, 4))
            if y_changed:
                ax.set_yticks(np.linspace(ymin, ymax, 5))

            if not tick_initialized:
                fontsize = np.clip(20 - 0.5 * (ymax - ymin), 6, 16)
                tick_len = 0.25 * min(abs(xmin), abs(xmax))
                ax.tick_params(
                    axis="both",
                    direction="inout",
                    length=tick_len,
                    labelsize=fontsize,
                    pad=2,
                )
                ax.set_xticklabels([])
                ax.set_yticklabels([])

            # self.fig.canvas.blit(ax.bbox)
        self._last_xlim = (xmin, xmax)
        self._last_ylim = (ymin, ymax)
        self._tick_initialized = True
        
        self.fig.canvas.draw()
        self.backgrounds = [self.fig.canvas.copy_from_bbox(ax.bbox) for ax in self.axes]
       
        
        # if x_changed or y_changed or not hasattr(self, "backgrounds"):
        #     self.fig.canvas.draw()
        #     self.backgrounds = [self.fig.canvas.copy_from_bbox(ax.bbox) for ax in self.axes]
        # else:
        #     for ax in self.axes:
        #         self.fig.canvas.restore_region(self.backgrounds[self.axes.index(ax)])
        #         self.fig.canvas.blit(ax.bbox)
        
        

class MainWindow(QWidget):
    
    def __init__(self, teps, meps, filename_params):
        super().__init__()
        self.setWindowTitle("TEP visualization")
        #self.setWindowIcon(QtGui.QIcon(r"./pictures/icon.png"))

        self.dispatcher_meps = meps                       # поток с МВП от резонанса
        self.dispatcher_meps.set_callback(self.get_MEPs)  # функция-обработчик МВП-потока в мВ

        self.dispatcher_teps = teps                       # поток с ТВП от резонанса
        self.dispatcher_teps.set_callback(self.get_TEPs)  # функция-обработчик ТВП-потока в мкВ

        with open(filename_params) as json_data:          # вгрузить настройки приложения
            self.params = json.load(json_data)  

        self.n_epoch = 0                                    # счётчик количества хранимых в памяти эпох
        self.st_TEPs = []                                   # список для хранения всех signle-trial TEPs
        self.EMG = deque(maxlen=5)
        self.average_functions = []                         # список хранящий функции для расчёта средних

        self.save_all = self.params["save_all"]             # флаг хранить ли все эпохи
        self.aver_mode = self.params["aver_mode"]           # флаг отображать усреднённые эпохи (True) или single-trial (False)
        self.aver_method = self.params["aver_methods"][0]   # метод для усреднения эпох
        self.n_aver_max = self.params["n_aver"]             # количество эпох на усреднение
        self.aver_all = self.params["aver_all"]             # флаг нужно ли усреднять все эпохи

        self.aver_empty_func = {                                        # dict с функциями для усреднения
            "mean": lambda x, y, z: RollingMean(x, y, z), 
            "median": lambda x, y, z: RollingMedian(x, y, z), 
            "trimmean": lambda x, y, z: RollingTrimMean(x, y, z)
        }

        self.specific_epoch = False                         # флаг для отслеживания режима показа определенной эпохи или стандартного

        self.SPEED = self.params["SPEED"]
        self.ms_to_sample = lambda x: int(x / 1000 * self.SPEED["Fs"])                                  # функция для пересчёта мс в сэмплы
        self.n_samples = self.ms_to_sample(self.SPEED["window_end"] - self.SPEED["window_start"])       # длина эпохи в сэмплах
        self.time_shift = self.ms_to_sample(0 - self.SPEED["window_start"])                             # смещение относительно нуля для графиков в сэпмлах

        self.resize(WIDTH_SET, HEIGHT_SET)

        self.show_window()


    def show_window(self):
        t1 = time.perf_counter()
        
        self.create_box_settings()
        t2 = time.perf_counter()
        self.create_box_plots()
        t3 = time.perf_counter()
        print(f"create_box_settings: {t2 - t1:.6f} сек")
        print(f"create_box_plots: {t3 - t2:.6f} сек")
        self.show()        

    def create_box_settings(self):
        box_settings = QWidget(self)
        layout = QGridLayout(box_settings)

        """Настройки отображения"""
        self.button_restart = self.create_button('Начать заново', self.restart, False, box_settings)
        self.shortcut_restart = self.create_shortcut_button("Delete", self.restart, False)

        self.label_n_epoch =  QLabel('Количество эпох: {}'.format(self.n_epoch), self)
        font = QFont('Helvetica', 16)
        font.setBold(True)
        self.label_n_epoch.setFont(font)
        text_width = QFontMetrics(font).horizontalAdvance('Количество эпох: 1000')  # ширина текста в пикселях
        text_height = QFontMetrics(font).height()
        self.label_n_epoch.setFixedSize(text_width, text_height)        # чтобы помещался текст с разным количеством эпох

        box_processing = QFrame(box_settings)                        # блок обработки в программе 
        layout_processing = QGridLayout(box_processing)
        # layout_processing.setSpacing(0)
        label1 = QLabel("Показать эпоху №", box_processing)
        self.spin_box_show_epoch = self.spin_box(0, self.n_epoch, self.n_epoch, parent=box_processing)
        self.button_show_epoch = self.create_button('Показать эпоху', self.show_epoch, False, box_processing)
        label2 = QLabel("Удалить эпоху №", box_processing)
        self.spin_box_remove_epoch = self.spin_box(0, self.n_epoch, self.n_epoch, parent=box_processing)
        self.button_remove_epoch = self.create_button('Удалить эпоху', self.remove_epoch, False, box_processing)

        box_averaging = QFrame(box_settings)                        # блок настроек усреднения
        box_averaging.setFrameShape(QFrame.Box)   # коробка с рамкой
        box_averaging.setLineWidth(1)
        layout_averaging = QGridLayout(box_averaging)
        layout_averaging.setSpacing(0)      # пробелы между виджетами
        layout_averaging.setContentsMargins(2, 2, 2, 2)     # отступы от края
        label3 = QLabel("Хранить", box_averaging)
        self.spin_box_save_epoch = self.spin_box(0, self.params['n_max_save'], self.params['n_save'], parent=box_averaging, disabled=self.params['save_all'])
        label4 = QLabel("эпох.", box_averaging)
        self.check_box_save_epoch = self.check_box(self.params['save_all'], 'все', parent=box_averaging, 
                        function=lambda: self.spin_box_save_epoch.setEnabled(not self.spin_box_save_epoch.isEnabled()))
        self.check_box_aver_mode = self.check_box(self.params['aver_mode'], 'Усреднять по ', parent=box_averaging)
        self.spin_box_aver_epoch = self.spin_box(0, 1000, self.params['n_aver'], parent=box_averaging, disabled=self.params['aver_all'])
        label6 = QLabel("эпохам.", box_averaging)
        self.check_box_aver_epoch = self.check_box(self.params['aver_all'], 'всем', parent=box_averaging,
                        function=lambda: self.spin_box_aver_epoch.setEnabled(not self.spin_box_aver_epoch.isEnabled()))
        label7 = QLabel("Метод усреднения:", box_averaging)
        self.combo_box_aver = self.create_combobox(self.params['aver_methods'], parent=box_averaging)
        self.button_aver = self.create_button('Применить', self.update_averaging, True, box_averaging)

        row = 0
        layout_averaging.addWidget(label3, row, 0, Qt.AlignRight)
        layout_averaging.addWidget(self.spin_box_save_epoch, row, 1)
        layout_averaging.addWidget(label4, row, 2)
        layout_averaging.addWidget(self.check_box_save_epoch, row, 3)
        row += 1
        layout_averaging.addWidget(self.check_box_aver_mode, row, 0, Qt.AlignRight)
        layout_averaging.addWidget(self.spin_box_aver_epoch, row, 1)
        layout_averaging.addWidget(label6, row, 2)
        layout_averaging.addWidget(self.check_box_aver_epoch, row, 3)
        row += 1
        layout_averaging.addWidget(label7, row, 0)
        layout_averaging.addWidget(self.combo_box_aver, row, 1)
        layout_averaging.addWidget(self.button_aver, row, 2, 1, 2)

        box_CAR = QFrame(box_settings)                        # блок Common Average Reference
        box_CAR.setFrameShape(QFrame.Box)   # коробка с рамкой
        box_CAR.setLineWidth(1)
        layout_CAR = QGridLayout(box_CAR)
        layout_CAR.setSpacing(0)      # пробелы между виджетами
        layout_CAR.setContentsMargins(2, 2, 2, 2)     # отступы от края
        self.check_box_car = self.check_box(self.params['CAR'], 'Common Average Reference', parent=box_settings)
        self.button_car = self.create_button('Применить', self.update_CAR, True, box_settings)
        label_car = QLabel("Использовать каналы:")
        self.combo_box_channels = self.create_checkable_combobox(CHANNELS, self.params['bad_channels'], parent=box_settings)
        layout_CAR.addWidget(self.check_box_car, 0, 0, 1, 2)
        layout_CAR.addWidget(self.button_car, 0, 2, 1, 2)
        layout_CAR.addWidget(label_car, 1, 0, 1, 2)
        layout_CAR.addWidget(self.combo_box_channels, 1, 2, 1, 2)

        box_baseline = QFrame(box_settings)                        # блок бейзлайн
        box_baseline.setFrameShape(QFrame.Box)  # коробка с рамкой
        box_baseline.setLineWidth(1) 
        layout_baseline = QGridLayout(box_baseline)
        layout_baseline.setSpacing(0)       # пробелы между виджетами
        layout_baseline.setContentsMargins(2, 2, 2, 2)       # отступы от края
        self.check_box_baseline = self.check_box(self.params['baseline'], 'Бейзлайн', parent=box_baseline)
        self.combo_box_baseline = self.create_combobox(self.params['baseline_methods'], parent=box_baseline)
        self.button_update_baseline = self.create_button('Применить', self.update_baseline, True, box_baseline)
        baseline_layout = QHBoxLayout()
        baseline_layout.setContentsMargins(0, 0, 0, 0)
        self.spin_box_baseline_start = self.spin_box(-1000, self.params['baseline_end'], self.params['baseline_start'], step=10, parent=box_baseline)
        self.spin_box_baseline_end = self.spin_box(self.params['baseline_start'], 0, self.params['baseline_end'], step=10, parent=box_baseline)
        label_start = QLabel("от", box_baseline)
        label_end = QLabel("до", box_baseline)
        label_ms = QLabel("мс", box_baseline)
        baseline_layout.addWidget(label_start)
        baseline_layout.addWidget(self.spin_box_baseline_start)
        baseline_layout.addWidget(label_end)
        baseline_layout.addWidget(self.spin_box_baseline_end)
        baseline_layout.addWidget(label_ms)

        layout_baseline.addWidget(self.check_box_baseline, 0, 0, 1, 1)
        layout_baseline.addWidget(self.combo_box_baseline, 0, 1, 1, 1)
        layout_baseline.addWidget(self.button_update_baseline, 0, 2, 1, 2)
        layout_baseline.addLayout(baseline_layout, 1, 0, 1, 2)


        box_lowpass = QFrame(box_settings)                        # блок фильтр lowpass
        box_lowpass.setFrameShape(QFrame.Box)  # коробка с рамкой
        box_lowpass.setLineWidth(1) 
        layout_lowpass = QGridLayout(box_lowpass)
        layout_lowpass.setSpacing(0)       # пробелы между виджетами
        layout_lowpass.setContentsMargins(2, 2, 2, 2)       # отступы от края
        self.check_box_lowpass2 = self.check_box(self.params["lowpass"], 'lowpass', parent=box_lowpass)
        self.spin_box_lowpass2 = self.spin_box(min=1, max=2500, value=self.params["high_freq"], parent=box_lowpass)
        label_hz = QLabel("Гц", box_lowpass)
        self.button_update_lowpass = self.create_button('Применить', self.update_lowpass, True, box_lowpass)
        layout_lowpass.addWidget(self.check_box_lowpass2, 0, 0)
        layout_lowpass.addWidget(self.spin_box_lowpass2, 0, 1)
        layout_lowpass.addWidget(label_hz, 0, 2)
        layout_lowpass.addWidget(self.button_update_lowpass, 0, 3)

        box_rereference = QFrame(box_settings)                        # блок фильтр re-reference
        box_rereference.setFrameShape(QFrame.Box)  # коробка с рамкой
        box_rereference.setLineWidth(1) 
        layout_rereference = QGridLayout(box_rereference)
        layout_rereference.setSpacing(0)       # пробелы между виджетами
        layout_rereference.setContentsMargins(2, 2, 2, 2)       # отступы от края
        self.check_box_rereference = self.check_box(self.params["rereference"], 're-reference', parent=box_rereference)
        self.combo_box_rereference = self.create_checkable_combobox(CHANNELS, self.params['rereference_channel'], status=True, parent=box_rereference)
        self.button_update_rereference = self.create_button('Применить', self.update_rereference, True, box_rereference)
        layout_rereference.addWidget(self.check_box_rereference, 0, 0)
        layout_rereference.addWidget(self.combo_box_rereference, 0, 1)
        layout_rereference.addWidget(self.button_update_rereference, 0, 2)
        
        row = 0
        layout_processing.addWidget(label1, row, 0)
        layout_processing.addWidget(self.spin_box_show_epoch, row, 1)
        layout_processing.addWidget(self.button_show_epoch, row, 2, 1, 2)
        row += 1
        layout_processing.addWidget(label2, row, 0)
        layout_processing.addWidget(self.spin_box_remove_epoch, row, 1)
        layout_processing.addWidget(self.button_remove_epoch, row, 2, 1, 2)
        row += 1
        layout_processing.addWidget(box_averaging, row, 0, 1, 4)
        row += 1
        layout_processing.addWidget(box_lowpass, row, 0, 1, 4)
        row += 1
        layout_processing.addWidget(box_rereference, row, 0, 1, 4)
        row += 1
        layout_processing.addWidget(box_baseline, row, 0, 1, 4)
        row += 1
        layout_processing.addWidget(box_CAR, row, 0, 1, 4)

        """настройки SPEED"""
        box_window = QFrame(box_settings)                         # window size
        box_window.setFrameShape(QFrame.Box)        
        box_window.setLineWidth(1) 
        layout_window = QHBoxLayout(box_window)
        layout_window.setSpacing(0)       # пробелы между виджетами
        layout_window.setContentsMargins(2, 2, 2, 2)       # отступы от края
        label = QLabel("Размер окна:", self)
        start, end = self.SPEED["window_start"], self.SPEED["window_end"]
        self.spin_box_window_start = self.spin_box(-1000, end, start, step=10, parent=box_window)
        self.spin_box_window_end = self.spin_box(start, 1000, end, step=10, parent=box_window)
        label_start = QLabel("от", box_window)
        label_end = QLabel("до", box_window)
        label_ms = QLabel("мс", box_window)
        layout_window.addWidget(label)
        layout_window.addWidget(label_start)
        layout_window.addWidget(self.spin_box_window_start)
        layout_window.addWidget(label_end)
        layout_window.addWidget(self.spin_box_window_end)
        layout_window.addWidget(label_ms)


        box_artifact = QFrame(box_settings)                         # TMS artifact
        box_artifact.setFrameShape(QFrame.Box)        
        box_artifact.setLineWidth(1) 
        layout_artifact = QGridLayout(box_artifact)
        layout_artifact.setSpacing(0)       # пробелы между виджетами
        layout_artifact.setContentsMargins(2, 2, 2, 2)       # отступы от края
        self.combo_box_artifact = self.create_combobox(['linear interpolation', 'zeros'], parent=box_artifact)
        self.check_box_artifact = self.check_box(self.SPEED['artifact'], 'ТМС артефакт', parent=box_artifact)
        start, end = self.SPEED["artifact_start"], self.SPEED["artifact_end"]
        self.spin_box_artifact_start = self.spin_box(self.SPEED["window_start"], end, start, step=1, parent=box_artifact)
        self.spin_box_artifact_end = self.spin_box(start, self.SPEED["window_end"], end, step=1, parent=box_artifact)
        label_start = QLabel("от", box_artifact)
        label_end = QLabel("до", box_artifact)
        label_ms = QLabel("мс", box_artifact)
        layout_artifact.addWidget(self.check_box_artifact, 0, 0, 1, 3)
        layout_artifact.addWidget(self.combo_box_artifact, 0, 3, 1, 2)
        layout_artifact.addWidget(label_start, 1, 0)
        layout_artifact.addWidget(self.spin_box_artifact_start, 1, 1)
        layout_artifact.addWidget(label_end, 1, 2)
        layout_artifact.addWidget(self.spin_box_artifact_end, 1, 3)
        layout_artifact.addWidget(label_ms, 1, 4)

        box_filtering = QFrame(box_settings)                            ## filtering
        box_filtering.setFrameShape(QFrame.Box)       
        box_filtering.setLineWidth(1)
        layout_filtering = QGridLayout(box_filtering)
        layout_filtering.setSpacing(0)
        layout_filtering.setContentsMargins(2, 2, 2, 2)       # отступы от края
        label = QLabel('Фильтрация', box_filtering)
        label_hz1 = QLabel('Гц', box_filtering)
        label_hz2 = QLabel('Гц', box_filtering)
        label_hz3 = QLabel('Гц', box_filtering)
        self.check_box_notch = self.check_box(self.SPEED["notch"], 'Notch', parent=box_filtering)
        self.spin_box_notch_fr = self.spin_box(min=0, max=100, value=self.SPEED["notch_fr"], parent=box_filtering)
        self.check_box_highpass = self.check_box(self.SPEED["highpass"], 'highpass', parent=box_filtering)
        self.spin_box_highpass = self.spin_box(min=1, max=100, value=self.SPEED["low_freq"], parent=box_filtering)
        self.check_box_lowpass = self.check_box(self.SPEED["lowpass"], 'lowpass', parent=box_filtering)
        self.spin_box_lowpass = self.spin_box(min=1, max=100, value=self.SPEED["high_freq"], parent=box_filtering)
        layout_filtering.addWidget(label, 0, 0, 1, 2)
        layout_filtering.addWidget(self.check_box_notch, 1, 0)
        layout_filtering.addWidget(self.spin_box_notch_fr, 1, 1)
        layout_filtering.addWidget(label_hz1, 1, 2)
        layout_filtering.addWidget(self.check_box_highpass, 2, 0)
        layout_filtering.addWidget(self.spin_box_highpass, 2, 1)
        layout_filtering.addWidget(label_hz2, 2, 2)
        layout_filtering.addWidget(self.check_box_lowpass, 3, 0)
        layout_filtering.addWidget(self.spin_box_lowpass, 3, 1)
        layout_filtering.addWidget(label_hz3, 3, 2)

        box_resampling = QFrame(box_settings)                               ## resampling
        box_resampling.setFrameShape(QFrame.Box)        
        box_resampling.setLineWidth(1) 
        layout_resampling = QGridLayout(box_resampling)
        layout_resampling.setSpacing(0)
        layout_resampling.setContentsMargins(2, 2, 2, 2)
        self.check_box_resampling = self.check_box(self.SPEED["resampling"], 'Ресемплинг', parent=box_resampling)
        label_hz1 = QLabel('Гц', box_resampling)
        label_hz2 = QLabel('Гц', box_resampling)
        self.spin_box_fs = self.spin_box(1000, 50000, self.SPEED["Fs_orig"], step=1000, parent=box_resampling)
        label_resample = QLabel('→', box_resampling)
        self.spin_box_resampling = self.spin_box(250, 25000, self.SPEED["Fs"], step=250, parent=box_resampling)
        layout_resampling.addWidget(self.check_box_resampling, 0, 0, 1, 3)
        layout_resampling.addWidget(self.spin_box_fs, 1, 0)
        layout_resampling.addWidget(label_hz1, 1, 1)
        layout_resampling.addWidget(label_resample, 1, 2)
        layout_resampling.addWidget(self.spin_box_resampling, 1, 3)
        layout_resampling.addWidget(label_hz2, 1, 4)

        box_SPEED = QFrame(box_settings)                            ## SPEED processing
        layout_SPEED = QGridLayout(box_SPEED)
        label = QLabel('SPEED settings', box_SPEED)
        self.button_speed = self.create_button("Сохранить настройки", self.launch_speed, True, box_SPEED)
        layout_SPEED.addWidget(label, 0, 0)
        layout_SPEED.addWidget(self.button_speed, 0, 1)
        layout_SPEED.addWidget(box_window, 1, 0, 1, 2)
        layout_SPEED.addWidget(box_artifact, 2, 0, 1, 2)
        layout_SPEED.addWidget(box_filtering, 3, 0, 1, 2)
        layout_SPEED.addWidget(box_resampling, 4, 0, 1, 2)
         
        layout.addWidget(self.button_restart, 0, 0)
        layout.addWidget(self.label_n_epoch, 0, 2, 1, 2)
        layout.addWidget(box_processing, 1, 0, 1, 2)
        #layout.addWidget(self.button_clean_last, 2, 0)
        layout.addWidget(box_SPEED, 2, 0, 1, 1)

        box_settings.move(0, 0)     # поместить виджет в левый верхний угол
        self.box_processing = box_processing

    def create_box_plots(self):
        
        df_pos = self.calculate_positions()
        y_aver = self.plot_height #(np.mean(np.diff(df_pos.loc[df_pos.x_centered == 0]['y_centered'].sort_values()))).astype(int)
        x_aver = self.plot_width #(np.mean(np.diff(df_pos.loc[df_pos.y_centered == 0]['x_centered'].sort_values()))).astype(int) 
        
        self.box_scale = QWidget(self)
        
        # self.box_scale.setStyleSheet("background-color: lightblue;")
        ymin, ymax = self.params["plot"]["ymin"], self.params["plot"]["ymax"]
        xmin, xmax = self.params["plot"]["xmin"], self.params["plot"]["xmax"]

        self.spin_box_scale_ymin = self.spin_box(-10000, 0, ymin, step=10, parent=self.box_scale, function=self.update_scale)
        self.spin_box_scale_ymax = self.spin_box(1, 10000, ymax, step=10, parent=self.box_scale, function=self.update_scale)
        self.spin_box_scale_xmin = self.spin_box(-1000, 0, xmin, step=5, parent=self.box_scale, function=self.update_scale)
        self.spin_box_scale_xmax = self.spin_box(1, self.SPEED["window_end"] , xmax, step=5, parent=self.box_scale,  function=self.update_scale)
        
        self.create_shortcut_scale(keyword="Alt+Up", spin1=self.spin_box_scale_ymax, spin2=self.spin_box_scale_ymin, action='more')
        self.create_shortcut_scale(keyword="Alt+Down", spin1=self.spin_box_scale_ymax, spin2=self.spin_box_scale_ymin, action='less')
        self.create_shortcut_scale(keyword="Alt+Left", spin1=self.spin_box_scale_xmax, spin2=self.spin_box_scale_xmin, action='less')
        self.create_shortcut_scale(keyword="Alt+Right", spin1=self.spin_box_scale_xmax, spin2=self.spin_box_scale_xmin, action='more')

        self.label_scale_y = QLabel(MICROVOLT, self.box_scale)
        self.label_scale_x = QLabel('ms', self.box_scale)
        
        xpos, ypos = df_pos['x'].min()-0*x_aver, int(df_pos['y'].max()+0.2*y_aver)
        positions = np.concatenate([df_pos[['x', 'y']].values, np.array([[xpos, ypos]])], axis=0)
        self.figure = PlotCanvas(self, positions, single_w=x_aver, single_h=y_aver, w=WIDTH_SET, h=HEIGHT_SET, Fs=self.SPEED['Fs'])
        self.figure.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        #self.figure.update_axes([xmin, xmax, ymin, ymax])
        self.figure.move(0, 0)
        
    def calculate_positions(self):
        th = np.pi / 180 * np.array(df.theta.values)

        total_width, total_height = self.width(), self.height()
        left_pad, right_pad = 400, 20   
        top_pad, bottom_pad = 100, 0#120, 10

        usable_width = total_width - (left_pad + right_pad)
        usable_height = total_height - (top_pad + bottom_pad)

        radius_norm = df.radius.values / (df.radius.max() - df.radius.min())

        self.plot_width = usable_width // 11
        self.plot_height = usable_height // 9

        scale_x = ((usable_width-self.plot_width) / 2) * 0.9
        scale_y = (usable_height / 2) * 1

        df['y_centered'] = (radius_norm * np.cos(th) * scale_y).astype(int)
        df['x_centered'] = (radius_norm * np.sin(th) * scale_x).astype(int)

        x_center, y_center = left_pad + (usable_width-self.plot_width) // 2, bottom_pad + usable_height // 2
        df['x'] = df['x_centered'] + x_center
        df['y'] = df['y_centered'] + y_center
  
        self.data = dict((pos, []) for pos in df['labels'].values)

        return df[['x', 'y', 'labels', 'x_centered', 'y_centered']]
    
    def resizeEvent(self, event):
        df_pos = self.calculate_positions()
        y_aver = self.plot_height #(np.mean(np.diff(df_pos.loc[df_pos.x_centered == 0]['y_centered'].sort_values()))).astype(int)
        x_aver = self.plot_width #(np.mean(np.diff(df_pos.loc[df_pos.y_centered == 0]['x_centered'].sort_values()))).astype(int) 

        xpos, ypos = df_pos['x'].min()-0*x_aver, int(df_pos['y'].min()-0.2*y_aver)
        # self.scale_plot.setGeometry(xpos, ypos, x_aver, y_aver)

        xmax = self.spin_box_scale_xmax.value()
        xmin = self.spin_box_scale_xmin.value()
        ymax = self.spin_box_scale_ymax.value()
        ymin = self.spin_box_scale_ymin.value()

        self.update_scale_shit_positions(x_aver, y_aver, xmin, xmax, ymin, ymax)

        xpad, ypad = int(0.6*x_aver),  int(0.3*y_aver)
        self.box_scale.setGeometry(xpos-xpad, ypos-ypad, x_aver+xpad*2, y_aver+ypad*2)

        self.figure.resize(self.width(), self.height())

        positions = np.concatenate([df_pos[['x', 'y']].values, np.array([[xpos, int(df_pos['y'].max()+0.3*y_aver)]])], axis=0)
        self.figure.update_position(positions, single_w=x_aver, single_h=y_aver, w=self.width(), h=self.height())
        self.figure.update_axes([self.ms_to_sample(xmin), self.ms_to_sample(xmax), ymin, ymax])
        #self.update_label_pos(x_aver, y_aver, xmin, xmax, ymin, ymax)

    def get_MEPs(self, msg, timestamp):
        # распаковать "сообщение" в формате {"MEPs": list of EEG data in microvolt} 
        # data = np.array(json.loads(msg)["MEPs"]).T[0]  # [n_samples x 1]
        data = np.array(msg).T[0]
        x_min, x_max = self.ms_to_sample(-15), self.ms_to_sample(100)

        self.EMG.append(data[self.time_shift+x_min:self.time_shift+x_max])
        self.figure.update_emg(list(self.EMG), x_min)

    def get_TEPs(self, msg, timestamp):
        # если не стоит флаг "хранить все" и эпох больше допустимого: True -- обрезать, False -- сохранить все
        trim_last = (not self.save_all) & (self.n_epoch + 1 > self.spin_box_save_epoch.value())

        if not trim_last:          # если не обрезать, то обновить счётчик количества эпох
            self.n_epoch += 1
            self.update_label_counter()
        else:                       # если обрезать
            self.st_TEPs = self.st_TEPS[1:]                     # удалить первую эпоху

        # распаковать "сообщение" в формате {"TEPs": list of EEG data in microvolt} 
        #data = np.array(json.loads(msg)["TEPs"]).T  # [n_channels x n_samples]
        data = np.array(msg).T
        print(f'input data shape: {data.shape}')
        self.st_TEPs.append(data)                   # добавить новый массив в список хранимых TEPs  [n_epoch x n_channels x n_samples]

        # если нужно, вычесть бейзлайн и применить CAR фильтр к новой эпохе
        data = self.referef(self.CAR(self.baseline(self.lowpass_filter(data))))                    # [n_ch x n_samples] 

        t0 = time.perf_counter()
        for i, ch_data in enumerate(data):
            if not self.aver_mode:                      # если single-trial режим, отобразить новую эпоху
                self.figure.update_data(i, ch_data, self.time_shift)
            else:                                       # если режим усреднения, обновить значения
                avg_funcs = self.average_functions[i]
                n = len(avg_funcs)
                for j in range(n): # обновить сохранённые функции
                    avg_funcs[j].add(ch_data[j])
                average_TEPs = [f.calculate() for f in avg_funcs]  # усреднённые TEPs
                self.figure.update_data(i, average_TEPs, self.time_shift)      # отобразить усреднённые TEPs
        self.figure.update_image()
        t1 = time.perf_counter()
        print(f"update plots (new epoch): {t1 - t0:.6f} сек")


    def show_epoch(self):
        if self.specific_epoch: # если был режим показа отдельной эпохи - вернуться к стандартному отображению
            self.update_plots()
            self.button_show_epoch.setText("Показать эпоху")
        else:                   # если не был включён режим показа отдельной эпохи - показать её
            n_show = self.spin_box_show_epoch.value()    # номер эпохи для просмотра
            data = self.CAR(self.baseline(self.st_TEPs[n_show-1]))
            for i in range(len(CHANNELS)):
                self.figure.update_data(i, data[i], self.time_shift)
            self.button_show_epoch.setText("Стандартный режим")
            self.figure.update_image()
        self.specific_epoch = not self.specific_epoch

    def restart_plots(self):
        self.figure.refresh()

    def restart(self):
        self.n_epoch = 0
        self.update_label_counter()

        self.st_TEPs = []
        self.average_functions = []
        self.update_averaging()

        self.restart_plots()

    def remove_epoch(self):  
        self.n_epoch -= 1
        self.update_label_counter()

        n_delete = self.spin_box_remove_epoch.value()    # номер эпохи для удаления 

        del self.st_TEPs[n_delete-1]                     # минус один для учёта нумерации с нуля

        if self.aver_mode:
            self.create_average_functions()
        if self.n_epoch > 0:
            self.update_plots()
        else:
            self.restart_plots()

    def update_label_pos(self, x_aver, y_aver, xmin, xmax, ymin, ymax):
        for i, label in enumerate(self.pos_labels):

            f_label = self.font()
            f_label.setPixelSize(int(y_aver * 0.25))
            label.setFont(f_label)
            width, height = label.fontMetrics().horizontalAdvance(label.text()), label.fontMetrics().height()
            x_axes_pos = int(x_aver / (xmax-xmin) * abs(xmin))
            y_axes_pos = int(y_aver / (ymax-ymin) * abs(ymax))
            
            x_label_pos = int(self.plots[i].x() + x_axes_pos - width*1.2)
            y_label_pos = int(self.plots[i].y() + y_axes_pos + height*0.3)

            label.move(x_label_pos, y_label_pos)

        qApp.processEvents()

    def update_scale(self):
        xmax = self.ms_to_sample(self.spin_box_scale_xmax.value())
        xmin = self.ms_to_sample(self.spin_box_scale_xmin.value())
        
        ymax = self.spin_box_scale_ymax.value()
        ymin = self.spin_box_scale_ymin.value()
        self.figure.update_axes([xmin, xmax, ymin, ymax])

               
        # x_aver, y_aver  = canvas.width(), canvas.height()
        # self.update_scale_shit_positions(x_aver, y_aver, xmin, xmax, ymin, ymax)

        #self.update_label_pos(x_aver, y_aver, xmin, xmax, ymin, ymax)

    def update_scale_shit_positions(self, x_aver, y_aver, xmin, xmax, ymin, ymax):
        width, height = int(x_aver*0.4), int(y_aver *0.3)

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
    
    def update_plots(self):
        t0 = time.perf_counter()
        if not self.aver_mode:
            data = self.referef(self.CAR(self.baseline(self.lowpass_filter(self.st_TEPs[-1]))))                    # [n_ch x n_samples]
        for i in range(len(CHANNELS)):
            if not self.aver_mode:                      # если single-trial режим, отобразить новую эпоху
                self.figure.update_data(i, data[i], self.time_shift)
            else:                                       # если режим усреднения, обновить значения     
                average_TEPs = np.array([f.calculate() for f in self.average_functions[i]])  # усреднённые TEPs
                self.figure.update_data(i, average_TEPs, self.time_shift)      # отобразить усреднённые TEPs
        self.figure.update_image()
        t1 = time.perf_counter()
        print(f"update plots (redraw): {t1 - t0:.6f} сек")

    def create_average_functions(self):
        function = self.aver_empty_func[self.aver_method]
        if self.n_epoch != 0:
            d = self.n_epoch - self.n_aver_max if not self.aver_all else 0
            data = np.array([self.referef(self.CAR(self.baseline(self.lowpass_filter(np.array(TEPs, dtype=float))))) for TEPs in self.st_TEPs[d:]])
        self.average_functions = []
        for i in range(len(CHANNELS)):
            if self.n_epoch == 0:
                self.average_functions.append([function([], self.n_aver_max, self.aver_all) for _ in range(self.n_samples)])
            else:
                self.average_functions.append([function(data[:, i, j], self.n_aver_max, self.aver_all) for j in range(self.n_samples)])

    def update_averaging(self):
        """применение настроек для усреднения эпох"""
        
        ## обновить количество сохранённых эпох
        self.save_all = self.check_box_save_epoch.isChecked()   # флаг нужно ли хранить все эпохи
        max_value = self.spin_box_save_epoch.value()            # максимальное значение эпох на сохранение
        if (not self.save_all) & (self.n_epoch > max_value):    # если нужно обрезать 
            d = self.n_epoch - max_value                        # сколько лишних
            self.st_TEPs = self.st_TEPs[d:]                     # обрезать list с хранимыми TEPs
            self.n_epoch = max_value                            # обновить счётчик эпох
            self.update_label_counter()                         

        ## обновить отображение усреднённых или сингл-трайл графиков
        self.aver_mode = self.check_box_aver_mode.isChecked()   # флаг усреднять (True) или single-trial (False)
        self.aver_all = self.check_box_aver_epoch.isChecked()   # флаг нужно ли усреднять все эпохи
        self.aver_method = self.combo_box_aver.currentText()    # текущий выбранный метод усреднения
        self.n_aver_max = self.spin_box_aver_epoch.value()      # количество эпох на усреднение

        if self.aver_mode:  # если усреднять - создать новые функции
            self.create_average_functions()

        if self.n_epoch > 0:        # если есть накопленные эпохи - нарисовать
            self.update_plots()

    def update_baseline(self):
        self.apply_baseline = self.check_box_baseline.isChecked()   # вычитать ли бейзлайн
        if self.apply_baseline:
            self.baseline_start, self.baseline_end = self.spin_box_baseline_start.value(), self.spin_box_baseline_end.value()
            ind_start = self.ms_to_sample(self.baseline_start - self.SPEED["window_start"])
            ind_end = ind_start + self.ms_to_sample(self.baseline_end - self.baseline_start) + 1
            func = (lambda x: np.mean(x, axis=1)) if self.combo_box_baseline.currentText() == 'mean' else (lambda x: np.median(x, axis=1))
            self.calculate_baseline = lambda x: func(x[:, ind_start:ind_end]).reshape((-1, 1))
        self.baseline = (lambda x: x - self.calculate_baseline(x)) if self.apply_baseline else (lambda x: x)
        if self.aver_mode:  # если усреднять - создать новые функции
            self.create_average_functions()
        if self.n_epoch > 0:
            self.update_plots()
    
    def update_lowpass(self):
        
        self.apply_filter = self.check_box_lowpass2.isChecked()
        if self.apply_filter:
            self.sos_lowpass = signal.butter(2, self.spin_box_lowpass2.value()/self.SPEED["Fs"]*2, btype='lowpass', output='sos')
        self.lowpass_filter = (lambda x: signal.sosfilt(self.sos_lowpass, x, axis=0)) if self.apply_filter else (lambda x: x)           # функция для применения фильтра
        if self.aver_mode:  # если усреднять - создать новые функции
            self.create_average_functions()
        if self.n_epoch > 0:
            self.update_plots()

    def update_rereference(self):
        self.apply_reref = self.check_box_rereference.isChecked()
        self.reref_channel = self.combo_box_rereference.checkedItems()[0]
        ind = np.where(CHANNELS == self.reref_channel)[0][0]

        n_channels = len(CHANNELS)
        e_r = np.zeros((n_channels, 1)); 
        e_r[ind, 0] = 1.0
        R = np.eye(n_channels) - np.ones((n_channels, 1)) @ e_r.T

        #self.referef = (lambda x: x - x[ind]) if self.apply_reref else (lambda x: x)
        self.referef = (lambda x: R @ x) if self.apply_reref else (lambda x: x)
        if self.aver_mode:  # если усреднять - создать новые функции
            self.create_average_functions()
        if self.n_epoch > 0:
            self.update_plots()

    def update_CAR(self):
        self.apply_CAR= self.check_box_car.isChecked()   # применять ли CAR
        if self.apply_CAR: 
            self.CAR_channels = self.combo_box_channels.checkedItems()
            n_sel = len(self.CAR_channels)
            if n_sel == 0:
                raise ValueError("Не отмечены каналы для построения CAR фильтра.")
            is_selected = np.array([ch in self.CAR_channels for ch in CHANNELS])
            n_channels = len(CHANNELS)
            W = np.eye(n_channels) - (1/n_sel) * np.outer(np.ones(n_channels), is_selected.astype(float)) # матрица фильтра CAR                 
        self.CAR = (lambda x: W @ x) if self.apply_CAR else (lambda x: x)           # функция для вычисления CAR
        if self.aver_mode:  # если усреднять - создать новые функции
            self.create_average_functions()
        if self.n_epoch > 0:

            self.update_plots()

    def launch_speed(self):
        """сохранить настройки SPEED"""
        self.SPEED = {}
        self.SPEED["window_start"] = self.spin_box_window_start.value()
        self.SPEED["window_end"] = self.spin_box_window_end.value()

        self.SPEED["artifact"] = self.check_box_artifact.isChecked()
        self.SPEED["artifact_start"] = self.spin_box_artifact_start.value()
        self.SPEED["artifact_end"] = self.spin_box_artifact_end.value()

        self.SPEED["notch"] = self.check_box_notch.isChecked()
        self.SPEED["notch_fr"] = self.spin_box_notch_fr.value()
        self.SPEED["highpass"] = self.check_box_highpass.isChecked()
        self.SPEED["low_freq"] = self.spin_box_highpass.value()
        self.SPEED["lowpass"] = self.check_box_lowpass.isChecked()
        self.SPEED["high_freq"] = self.spin_box_lowpass.value()

        self.SPEED["resampling"] = self.check_box_resampling.isChecked()
        self.SPEED["Fs_orig"] = self.spin_box_fs.value()
        self.SPEED["Fs"] = self.spin_box_resampling.value()

        self.ms_to_sample = lambda x: int(x / 1000 * self.SPEED["Fs"])       # функция для пересчёта мс в сэмплы
        self.n_samples = self.ms_to_sample(self.SPEED["window_end"] - self.SPEED["window_start"])    # длина эпохи в сэмплах
        self.time_shift = self.ms_to_sample(0 - self.SPEED["window_start"])    # смещение относительно нуля для графиков в сэпмлах

        with open(self.params["SPEED_settings_path"], 'w') as f:
            json.dump(self.SPEED, f)


    def spin_box(self, min, max, value, data_type = 'int', step=1, decimals=4, parent=None, w=None, h=None, function=None, disabled=False):
        par = self if parent is None else parent
        if data_type == 'int':
            spin_box = QSpinBox(par)
        else:
            spin_box = QDoubleSpinBox(par)
            spin_box.setDecimals(decimals)
        spin_box.setRange(min, max)
        spin_box.setValue(value)
        spin_box.setSingleStep(step)
        if w is not None and h is not None:
            spin_box.resize(w, h)
        if function is not None:
            spin_box.valueChanged.connect(function)
        spin_box.setDisabled(disabled)
        return spin_box
    
    def spin_box_with_unit(self, unit, min, max, value, step=1, data_type='int', decimals=4, w=None, h=None, function=None, parent=None):
        parent = self if parent is None else parent
        box = QWidget(parent)
        layout = QGridLayout()
        layout.setSpacing(0)
        spin_box = self.spin_box(min, max, value, data_type, step, decimals, parent, w, h)
        if function is not None:
            spin_box.valueChanged[int].connect(function)
        label_time = QLabel(unit, self)
        layout.addWidget(spin_box, 0, 0, 1, 2)
        layout.addWidget(label_time, 0, 2, 1, 1)
        box.setLayout(layout)

        return box
    
    def fit_font_to_width_spinbox(self, spinbox: QSpinBox, padding_w=0, padding_h=0):
        
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
    
    def create_combobox(self, items, parent=None):
        parent = self if parent is None else parent
        combobox = QComboBox(parent)
        combobox.addItems(items)
        return combobox

    def create_checkable_combobox(self, channels, bad_channels, status=False, parent=None):
        parent = self if parent is None else parent
        combobox = CheckableComboBox(parent)
        for item in channels:
            checked = status if item in bad_channels else not status
            combobox.addItem(item, checked)
        return combobox

    def create_button(self, text, function, enabled=True, parent=None):
        parent = self if parent is None else parent
        button = QPushButton(text, parent)         # кнопка очистить
        button.clicked.connect(function)
        button.setEnabled(enabled)
        return button
    
    def create_shortcut_button(self, keyword, function, enabled=True):
        shortcut = QShortcut(QKeySequence(keyword), self)
        shortcut.activated.connect(function)
        shortcut.setEnabled(enabled)
        return shortcut

    def create_shortcut_scale(self, keyword, spin1, spin2, action):
        shortcut = QShortcut(QKeySequence(keyword), self)
        alpha = 1 if action == 'more' else -1
        shortcut.activated.connect(lambda: (spin1.setValue(spin1.value() + alpha * spin1.singleStep()),
                                            spin2.setValue(spin2.value() + (-1)*alpha * spin2.singleStep())))
        
    def check_box(self, state, text='', parent=None, function=None):
        parent = self if parent is None else parent
        check_box = QCheckBox(text, parent)
        if state:
            check_box.toggle()
        if function is not None:
            check_box.stateChanged.connect(function)
        return check_box
    
    def update_label_counter(self):
        self.label_n_epoch.setText('Количество эпох: {}'.format(self.n_epoch))
        qApp.processEvents()    # для обновления отображения в Qt-приложении

        # если эпохи есть, то разрешить их очистку из памяти по нажатию кнопки 
        active_status = True if self.n_epoch > 0 else False      
        self.button_restart.setEnabled(active_status)
        self.shortcut_restart.setEnabled(active_status)
        self.button_remove_epoch.setEnabled(active_status)
        #self.shortcut_remove_epoch.setEnabled(True)
        self.button_show_epoch.setEnabled(active_status)

        self.spin_box_show_epoch.setMaximum(self.n_epoch)
        self.spin_box_show_epoch.setValue(self.n_epoch)
        self.spin_box_remove_epoch.setMaximum(self.n_epoch)
        self.spin_box_remove_epoch.setValue(self.n_epoch)

def initial_calculations(self):
    self.update_CAR()
    self.update_baseline()
    self.update_lowpass()
    self.update_rereference()
    self.update_averaging()
    
def showEvent(self, event):
    QTimer.singleShot(10, self.initial_calculations)