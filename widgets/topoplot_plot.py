from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFrame
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QPainter, QColor, QPen

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import mne
import numpy as np
import pandas as pd

from matplotlib import colormaps as cm
from matplotlib.colors import ListedColormap
viridisBig = cm.get_cmap('jet')
newcmp = ListedColormap(viridisBig(np.linspace(0, 1, 15)))

class TopoPlot(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._init_state()
        self._setup_ui()
        self._setup_layout()
        self._finalize()

    def _init_state(self):
        self.setStyleSheet("background-color: white; border: 2px solid gray;")
        
        # --- параметры для отрисовки голов ---
        filename = r".\resources\mumeg_mks64.ced"
        self.df = pd.read_csv(filename, sep="\t")

        self.channels = self.df.labels.values
        th = np.pi / 180 * np.array(self.df.theta.values)
        self.df['y'] = np.round(np.array(self.df.radius.values) * np.cos(th), 2)
        self.df['x'] = np.round(np.array(self.df.radius.values) * np.sin(th), 2)

        # --- перемещение / изменение размера ---
        self.dragging = False
        self.resizing = False
        self.drag_start_pos = QPoint()
        self.original_rect = QRect()

        self.resize_handle_size = 10

    def _setup_ui(self):
        # --- график matplotlib ---
        self.fig = Figure(figsize=(4, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        
        self.ax = self.fig.add_subplot(111)
        self.ax.plot([0, 1, 2, 3], [0, 2, 1, 3])
        self.fig.tight_layout()
    
    def _setup_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def _finalize(self):
        self.canvas.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    # --- Логика ---
    def plot_topomap(self, data, info=None, pos=None, picks=None,
                     vmin=None, vmax=None, cmap='RdBu_r', show_names=False,
                     sensors=True, contours=6):
        """
        data: 1D array of sensor values (len == n_channels) OR mne.Evoked/data slice
        info: mne.Info (если data не содержит info)
        pos: позиция каналов (обычно можно пропустить, mne использует info)
        picks: индексы каналов или names
        """
        # очистка осей
        self.ax.clear()

        # Подготавливаем вход: если передан Evoked или Epochs/Raw - взять data и info
        if hasattr(data, 'data') and hasattr(data, 'info'):
            evoked = data
            # пример: выбрать момент времени по индексу time_idx
            # values = evoked.data[:, time_idx]
            # тут просто нарисуем среднюю по времени:
            values = np.mean(evoked.data, axis=1)
            this_info = evoked.info
        else:
            values = np.asarray(data)
            this_info = self.df[['x', 'y']].values
        min_value = np.min(values)
        max_value = np.max(values)
        vlim = min(np.abs(min_value), np.abs(max_value))
        # Если picks задан как None, MNE попытается взять все доступные каналы
        # Передаём axes и show=False, чтобы MNE не открывал новое окно
        im, cn = mne.viz.plot_topomap(
            values, this_info if pos is None else pos,
            axes=self.ax,
            show=False,
            cmap=newcmp,
            #names =self.channels,
            vlim=[vmin, vmax],
            sphere=0.5, 
            contours=6,
            image_interp='cubic',
            ch_type='eeg', 
            extrapolate='head', 
            # outlines='head'  # или 'skirt' / None
        )

        # im, cn = mne.viz.plot_topomap(ERP[:, idx], ,  image_interp='cubic', ch_type='eeg', names =channels[inds],
        # size=5, show=False, contours=6, sphere=0.5, 
        # cmap=newcmp, extrapolate='head',  vlim=[-8, 8])
        if self.time1:
            plt.colorbar(im)
            self.time1 = False 
        # Перерисовать canvas
        self.canvas.draw()

    # --- События ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            rect = self.rect()
            resize_area = rect.adjusted(rect.width() - self.resize_handle_size,
                                        rect.height() - self.resize_handle_size, 0, 0)
            if resize_area.contains(event.pos()):
                self.resizing = True
            else:
                self.dragging = True
            self.drag_start_pos = event.globalPos()
            self.original_rect = self.geometry()

    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.globalPos() - self.drag_start_pos
            self.move(self.original_rect.topLeft() + delta)
        elif self.resizing:
            delta = event.globalPos() - self.drag_start_pos
            new_width = max(100, self.original_rect.width() + delta.x())
            new_height = max(100, self.original_rect.height() + delta.y())
            self.setGeometry(self.original_rect.x(), self.original_rect.y(), new_width, new_height)

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.resizing = False

    def paintEvent(self, event):
        """рисуем уголок для изменения размера"""
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(QColor("gray"))
        painter.setPen(pen)
        size = self.resize_handle_size
        w, h = self.width(), self.height()
        painter.drawLine(w - size, h, w, h - size)
        painter.drawLine(w - size // 2, h, w, h - size // 2)
    
        
class TopoCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.fig = Figure(figsize=(4, 4), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)

        filename = r".\resources\mumeg_mks64.ced"
        self.df = pd.read_csv(filename, sep="\t")

        self.channels = self.df.labels.values
        th = np.pi / 180 * np.array(self.df.theta.values)
        self.df['y'] = np.round(np.array(self.df.radius.values) * np.cos(th), 2)
        self.df['x'] = np.round(np.array(self.df.radius.values) * np.sin(th), 2)

        self.time1 = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def plot_topomap(self, data, info=None, pos=None, picks=None,
                     vmin=None, vmax=None, cmap='RdBu_r', show_names=False,
                     sensors=True, contours=6):
        """
        data: 1D array of sensor values (len == n_channels) OR mne.Evoked/data slice
        info: mne.Info (если data не содержит info)
        pos: позиция каналов (обычно можно пропустить, mne использует info)
        picks: индексы каналов или names
        """
        # очистка осей
        self.ax.clear()

        # Подготавливаем вход: если передан Evoked или Epochs/Raw - взять data и info
        if hasattr(data, 'data') and hasattr(data, 'info'):
            evoked = data
            # пример: выбрать момент времени по индексу time_idx
            # values = evoked.data[:, time_idx]
            # тут просто нарисуем среднюю по времени:
            values = np.mean(evoked.data, axis=1)
            this_info = evoked.info
        else:
            values = np.asarray(data)
            this_info = self.df[['x', 'y']].values
        min_value = np.min(values)
        max_value = np.max(values)
        vlim = min(np.abs(min_value), np.abs(max_value))
        # Если picks задан как None, MNE попытается взять все доступные каналы
        # Передаём axes и show=False, чтобы MNE не открывал новое окно
        im, cn = mne.viz.plot_topomap(
            values, this_info if pos is None else pos,
            axes=self.ax,
            show=False,
            cmap=newcmp,
            #names =self.channels,
            vlim=[vmin, vmax],
            sphere=0.5, 
            contours=6,
            image_interp='cubic',
            ch_type='eeg', 
            extrapolate='head', 
            # outlines='head'  # или 'skirt' / None
        )

        # im, cn = mne.viz.plot_topomap(ERP[:, idx], ,  image_interp='cubic', ch_type='eeg', names =channels[inds],
        # size=5, show=False, contours=6, sphere=0.5, 
        # cmap=newcmp, extrapolate='head',  vlim=[-8, 8])
        if self.time1:
            plt.colorbar(im)
            self.time1 = False 
        # Перерисовать canvas
        self.canvas.draw()

    # def _load_config(self):


class TopoPlot222(FigureCanvas):
    """Класс для отрисовки графиков"""
    def __init__(self, parent=None, single_w=300, single_h=200, w=1000, h=700, Fs=5000, n_emg=5, dpi=100):
        figsize = (w/dpi, h/dpi)
        self.fig = Figure(figsize=figsize, dpi=100) 
        #self.fig = Figure(constrained_layout=True)
        self.fig.patch.set_alpha(0.0)                          # Делаем фон холста matplolib прозрачным
        
        super().__init__(self.fig)
        self.setStyleSheet("background-color:transparent;")    # делаем виджет прозрачнымs
        
        self.setParent(parent)
        
        fig_width_px, fig_height_px = figsize[0] * dpi, figsize[1] * dpi    # размеры фигуры в пикселях

        self.axes = []
        self.lines = []

        width = single_w / fig_width_px
        height = single_h / fig_height_px

        emg_w, emg_h = width, height
        emg_left = 100/fig_width_px #w/fig_width_px - emg_w #-
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