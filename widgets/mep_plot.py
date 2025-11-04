from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import transforms
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

from PyQt5.QtGui import QFont, QFontMetrics
import numpy as np
from collections import deque

class MEPPlot(FigureCanvas):
    """Класс для отрисовки графиков"""
    def __init__(self, parent=None, w=1000, h=700, params=None, dpi=100):
        
        self.figsize = (w/dpi, h/dpi)
        self.dpi = dpi
        self.params = params or {}
        
        self.fig = Figure(figsize=self.figsize, dpi=100) 
        
        self.fig.patch.set_alpha(0.0)                          # Делаем фон холста matplolib прозрачным
        
        super().__init__(self.fig)
        self.setParent(parent)

        self.setStyleSheet("background-color:transparent;")    # делаем виджет прозрачнымs

        self._init_state()
        
    def _init_state(self):
        self.ms_to_sample = lambda x: int(x / 1000 * self.params["Fs"])
        self._xmin, self._xmax = self.ms_to_sample(self.params["xmin_ms"]), self.ms_to_sample(self.params["xmax_ms"])
        self._ymax = self.params["max_amp_mV"]

        x_shift = self._xmin
        window_dur = self._xmax - self._xmin

        n = self.params["n_plots"]
        first_time = True

        """создание оси"""
        self.ax = self.fig.add_axes([0, 0, 1, 1])   # создаём ось на всё пространство графика [left, bottom, width, height]
        self.ax.set_axis_off()                      # полностью скрываем оси
        self.ax.patch.set_visible(False)            # убираем фон осей
        for spine in self.ax.spines.values():       # убираем рамку
            spine.set_visible(False)

        """псевдоданные"""
        x = np.linspace(x_shift, window_dur+x_shift, window_dur)
        self._x = self._normalize(x, axis='x')

        x_step = 20 # ms
        n_xticks = (self.params["xmax_ms"] - self.params["xmin_ms"]) // x_step + 1

        x_ticks_orig = np.linspace(self.params["xmin_ms"], self.params["xmax_ms"], n_xticks).astype(int)
        y_ticks_orig = np.linspace(-self._ymax, self._ymax, 5)

        x_ticks = self._normalize(np.linspace(self._xmin, self._xmax, n_xticks), axis='x')
        y_ticks = self._normalize(y_ticks_orig, axis='y')

        fontsize_ticks = 10
        fontsize_axes = 12
        fontsize_title = 12

        self.lines = []                             # здесь будут накапливаться до n графиков миограммы
        self.amps = [None for _ in range(n)]
        self.lats = [None for _ in range(n)]

        """расположение графиков"""
        # --- размеры в пикселях ---
        fig_w_px, fig_h_px = self.figsize[0] * self.dpi, self.figsize[1] * self.dpi  # px
        width_px, height_px = 0.7*fig_w_px/n, 0.7*fig_h_px                           # px 
        d_width = (1-0.7-0.1) * fig_w_px / 5                                         # px : расстояние между графиками по горизонтали
        left0_px, bottom_px = 0.1*fig_w_px, 0.1*fig_h_px                             # px : положение первого графика (лево, низ)
        
        # --- отнормированные размеры ---
        width, height = width_px / fig_w_px, height_px / fig_h_px    # ширина и высота одного графика
        bottom = bottom_px / fig_h_px                                # положение нижнего края графиков

        for i in range(n):
            add_dw = 0.5 * d_width if i > 0 else 0
            left = (left0_px + add_dw + i * (width_px + d_width) )/ fig_w_px    # положение области в нормированных координатах (0–1)
            
            # создаём трансформацию для линии (разное положение)
            aff = transforms.Affine2D().scale(width, height).translate(left, bottom)
            tr = aff + self.ax.transAxes

            # --- фон области ---
            color, lw = ('black', 1.5) if i == 0 else ('gray', 1.0)

            rect = Rectangle((0, 0), 1, 1,
                            transform=tr, facecolor="#f7f7f7",
                            edgecolor=color, linewidth=lw, zorder=0)
            self.ax.add_patch(rect)

            # --- сетка ---
            for gx in x_ticks:             # вертикальные линии
                grid = Line2D([gx, gx], [0, 1],lw=0.8, color="lightgray", transform=tr, zorder=1)
                self.ax.add_line(grid)
            for gy in y_ticks:             # горизонтальные линии
                grid = Line2D([0, 1], [gy, gy],lw=0.8, color="lightgray", transform=tr, zorder=1)
                self.ax.add_line(grid)
            
            # --- оси --- 
            if i == 0:  # только на первом графике
                for j,x_t in enumerate(x_ticks):
                    tick = Line2D([x_t, x_t], [-0.03, 0], color='darkgray', lw=2, transform=tr)
                    self.ax.add_line(tick)

                    self.ax.text(x_t, -0.1,
                            str(x_ticks_orig[j]), transform=tr,
                            ha='center', va='center', fontsize=fontsize_ticks, color='darkgray')

                for j, y_t in enumerate(y_ticks):
                    tick = Line2D([-0.03, 0], [y_t, y_t], color='darkgray', lw=2, transform=tr)
                    self.ax.add_line(tick)
                    self.ax.text(-.15, y_t,
                            str(y_ticks_orig[j]), transform=tr,
                            ha='center', va='center', fontsize=fontsize_ticks, color='darkgray')
                
                self.ax.text(-.5, 1, "mV", transform=tr, fontsize=fontsize_axes, color='darkgray')
                self.ax.text(1.05, -.05, "ms", transform=tr, fontsize=fontsize_axes, color='darkgray')
            
            # --- надпись над графиком ---
            title = f"#{i+1}" if self.amps[i] is None else f"#{i+1} : amp={self.amps[i]} mV, lat={self.lats[i]} ms"
            color = 'black' if i == 0 else 'darkgray'
            self.ax.text(0, 1.1, title, transform=tr, fontsize=fontsize_title, color=color)

            # --- копилка для сигнала ---
            line = Line2D(self._x, np.full(len(self._x), np.nan), lw=1.5, color="blue", transform=tr, zorder=2)
            self.ax.draw_artist(line)
            self.lines.append(line)

        self.fig.canvas.draw()
        self.background = self.fig.canvas.copy_from_bbox(self.ax.bbox)

    def update_emg(self, emg):
        self.fig.canvas.restore_region(self.background) # восстанавливаем чистый фон

        for i in reversed(range(1, self.params["n_plots"])):
            line = self.lines[i]
            y = self.lines[i-1].get_ydata()
            line.set_ydata(y)
            self.ax.draw_artist(line)
        self.lines[0].set_ydata(self._normalize(emg, axis='y'))
        self.ax.draw_artist(self.lines[0])
        self.fig.canvas.blit()
    
    def _normalize(self, x, axis='x'):
        xmin, xmax = (self._xmin, self._xmax) if axis == 'x' else (-self._ymax, self._ymax)
        return (x - xmin) / (xmax - xmin)