from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib import colormaps as cm
from matplotlib.colors import ListedColormap
import numpy as np

from utils.helpers import get_time_ticks, get_voltage_ticks

MICROVOLT = "\u03BC"+"V"

class supplPlot(FigureCanvas):
    def __init__(self, parent=None, w=1000, h=700, params=None, Fs=5000, dpi=100):
        self._figsize = (w/dpi, h/dpi)
        self.fig = Figure(figsize=self._figsize, dpi=dpi)
        self.fig.patch.set_alpha(0.0)                          # Делаем фон холста matplolib прозрачным
        
        super().__init__(self.fig)
        self.setStyleSheet("background-color:transparent;")    # делаем виджет прозрачнымs

        self.setParent(parent)

        self._params = params or {}
        self._ms_to_sample = lambda x: int(x / 1000 * Fs)

        self._init_state()
        
    def _init_state(self):

        """создание оси"""
        # создаём ось на часть пространства графика[left, bottom, width, height]
        self._ax = self.fig.add_axes([0.15, 0.1, 0.75, 0.8])   

        y_units = self._params['units'] if self._params['units'] == 'mV' else MICROVOLT
        self._ax.text(-.15, 1, f"[{y_units}]", color='black', transform=self._ax.transAxes)
        self._ax.text(1.05, -.05, "[ms]", color='black', transform=self._ax.transAxes)

        self._ax.axvline(0)
        self._ax.axhline(0)

        self._rect = Rectangle((0, 0), width=(0), height=(0),
                    linewidth=2, edgecolor='red', facecolor='none', visible=False)
        self._ax.add_patch(self._rect)

        self._ax.set_title(self._params["title"])

        self._ax.grid(True)

        """параметры"""
        self._mean = lambda x: np.mean(x[self._params["channels_nearest_n"]], axis=0)   # функция для усреднения каналов интереса

        self._last_xlim = None  # границы по оси х не заданы
        self._last_amp = None  # границы по оси y не заданы

        self._viridisBig = cm.get_cmap('jet')
        
    def set_x_shift(self, x_shift, window_dur, signal='TEP'):
        self._x = np.linspace(x_shift, window_dur+x_shift, window_dur)
        if signal == 'TEP':
            self._create_empty_TEPs()
        elif signal == 'MEP':
            self._create_empty_MEPs()

    def _create_empty_TEPs(self):
        # --- копилка для сигнала ---
        self._lines = []
        y_empty = np.full(len(self._x), np.nan)
        n = self._params["n_channels"] + 1
        for i in range(n):
            (color, lw) = ("gray", 0.5) if i < n-1 else ("black", 1.5)
            line = Line2D(self._x, y_empty, lw=lw, color=color)
            self._ax.add_line(line)
            self._lines.append(line)
    
    def _create_empty_MEPs(self):
         # --- копилка для сигнала ---
        y_empty = np.full(len(self._x), np.nan)
        (color, lw) = ("black", 1.5)
        self._line = Line2D(self._x, y_empty, lw=lw, color=color)
        self._ax.add_line(self._line)

    def update_axes(self, xmax_ms=100, xmin_ms=-20, amp=100):
        xmin, xmax = self._ms_to_sample(xmin_ms), self._ms_to_sample(xmax_ms)

        x_changed = not hasattr(self, "_last_xlim") or (self._last_xlim != (xmin, xmax))
        y_changed = not hasattr(self, "_last_amp") or (self._last_amp != amp)

        self._last_xlim = (xmin, xmax)
        self._last_amp = amp

        if x_changed:
            self._ax.set_xlim(xmin, xmax)
            x_tick = get_time_ticks(xmax_ms)      # значение тиков по горизонтальной оси
            x_ticks_ms = np.arange(0, xmax_ms+1, x_tick).astype(int)
            x_ticks_samples = np.linspace(0, xmax, len(x_ticks_ms))
            self._ax.set_xticks(x_ticks_samples, x_ticks_ms)
            
        if y_changed:
            self._ax.set_ylim(-amp, amp)
            y_tick = get_voltage_ticks(amp, n_tick=2)      # значение тиков по вертикальной оси
            neg = np.arange(0, -amp - y_tick, -y_tick)[::-1]  # отрицательная часть
            pos = np.arange(0, amp + y_tick,  y_tick)         # положительная часть
            y_ticks = np.concatenate([neg, pos]).round(self._params["round"])              # чтобы гарантировать 0
            self._ax.set_yticks(y_ticks)
        
        self.fig.canvas.draw()
        self._background = self.fig.canvas.copy_from_bbox(self._ax.bbox)
    
    def draw_rectangle(self, xmin_ms, xmax_ms, ymin, ymax):
        self.fig.canvas.restore_region(self._background)  # восстанавливаем чистый фон

        xmin, xmax = self._ms_to_sample(xmin_ms), self._ms_to_sample(xmax_ms)
        self._rect.set_xy((xmin, ymin))
        self._rect.set_width((xmax-xmin))
        self._rect.set_height((ymax-ymin))

        if not self._rect.get_visible():
            self._rect.set_visible(True)
        
        self._ax.draw_artist(self._rect)
        self.fig.canvas.blit()

        self._background_rect = self.fig.canvas.copy_from_bbox(self._ax.bbox)

    def update_TEPs(self, teps):
        self.fig.canvas.restore_region(self._background)  # восстанавливаем чистый фон
        
        for i in range(teps.shape[0]):          # для каждого канала
            self._lines[i].set_ydata(teps[i])
            self._ax.draw_artist(self._lines[i])

        self._lines[i+1].set_ydata(self._mean(teps))     # усреднённые каналы вокруг С3
        self._ax.draw_artist(self._lines[i+1])

        self.fig.canvas.blit(self._ax.bbox)
    
    def update_MEPs(self, meps):
        self.fig.canvas.restore_region(self._background)  # восстанавливаем чистый фон

        self._line.set_ydata(meps)
        self._ax.draw_artist(self._line)

        self.fig.canvas.blit(self._ax.bbox)
    
    def draw_loaded_multiple_sessions(self, session_data, signal="TEP"):
        self.fig.canvas.restore_region(self._background)  # восстанавливаем чистый фон

        colors = ListedColormap(self._viridisBig(np.linspace(0, 1, len(session_data))))
        colors = ["green", "orange", "darkred", "pink"]

        (color, lw) = ("black", 1.5)
        for i in range(len(session_data)):          # для каждого файла
            data2plot = session_data[i]
            if signal == "TEP":
                data2plot = self._mean(data2plot)   # берём среднее от "избранных" каналов
            line, = self._ax.plot(self._x, data2plot, lw=lw, color=colors[i])
            self._ax.draw_artist(line)

        self.fig.canvas.blit(self._ax.bbox)
    
    def refresh_plot(self):
        self.fig.canvas.restore_region(self._background) # восстанавливаем чистый фон
        self.fig.canvas.blit(self._ax.bbox)
    
#fontsize_ticks = 10
# fontsize_axes = 10
# fontsize_title = 12
        
    