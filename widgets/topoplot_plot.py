from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFrame
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QPainter, QColor, QPen

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import mne
from mne.viz.topomap import _make_head_outlines, _setup_interp
import numpy as np
import pandas as pd
from scipy.interpolate import LinearNDInterpolator, griddata

from matplotlib import colormaps as cm
from matplotlib.colors import ListedColormap


class TopoPlot(QFrame):
    def __init__(self, parent=None, w=40, timestamp=20, params=None):
        super().__init__(parent)
        self.resize(w, w)

        self.timestamp = timestamp
        self.params = params

        self._init_state()
        self._setup_ui()
        self._setup_layout()
        self._finalize()

    def _init_state(self):
        self.setStyleSheet("background-color: white; border: 2px solid gray;")
        
        # --- параметры для отрисовки голов ---
        filename = r".\resources\mumeg_mks64.ced"
        df = pd.read_csv(filename, sep="\t")

        self.channels = df.labels.values
        th = np.pi / 180 * np.array(df.theta.values)
        df['y'] = np.round(np.array(df.radius.values) * np.cos(th), 2)
        df['x'] = np.round(np.array(df.radius.values) * np.sin(th), 2)
        self._pos = df[['x', 'y']].values
        
        # --- подготовка графика ---
        self._vlim = (self.params["vmin"], self.params["vmax"])
        viridisBig = cm.get_cmap('jet')
        #newcmp = ListedColormap(viridisBig(np.linspace(0, 1, 15)))
        self._cmap = viridisBig

        # sphere = self.params["sphere"]
        # grid_res = len(self._pos)
        # _interp, extrapolate, res, _ = _setup_interp(
        #         self._pos, grid_res, image_interp="nearest", extrapolate='head', outlines="head", border="mean")
        # self.xi, self.yi = np.mgrid[-0.5:0.5:res*1j, -0.5:0.5:res*1j]

        # self.head_outlines = _make_head_outlines(
        #     sphere=(0.0, 0.0, 0.0, 0.5),
        #     pos=self._pos,
        #     outlines='head',
        # )

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
        self.ax.set_axis_off()                      # полностью скрываем оси
        self.ax.patch.set_visible(False)            # убираем фон осей
        for spine in self.ax.spines.values():       # убираем рамку
            spine.set_visible(False)

        self.ax.set_title(f"{self.timestamp} ms", loc='right')
        self.ax.set_aspect('equal')

        values = np.zeros(len(self._pos))

        im, _ = mne.viz.plot_topomap(
                values, 
                self._pos, 
                axes=self.ax,
                show=False,
                cmap=self._cmap,
                vlim=self._vlim,
                sphere=0.5,
                contours=self.params["countours"],
                ch_type='eeg', 
                extrapolate='head',
                sensors=self.params["sensors"],
                image_interp='cubic'  
            )
        
        
        self.im = im

        # --- важное: забираем сетку интерполяции из im ---
        frame = im.get_extent()  # границы изображения [left, right, bottom, top]
        xi, yi = np.mgrid[frame[0]:frame[1]:64j, frame[2]:frame[3]:64j]
        self.data2z = lambda x: griddata(self._pos, x, (xi, yi), method='cubic')
    
    def _setup_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def _finalize(self):
        self.canvas.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    # --- Логика ---
    def plot_topomap(self, data):
        # data: 1D array of sensor values (len == n_channels)
        zi =  self.data2z(data)
        self.im.set_data(zi)
        self.ax.draw_artist(self.im)
        self.canvas.blit()

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