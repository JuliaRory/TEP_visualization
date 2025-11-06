from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import numpy as np

MICROVOLT = "\u03BC"+"V"

class TEPsSupplPlot(FigureCanvas):
    def __init__(self, parent=None, w=1000, h=700, params=None, dpi=100):
        self.figsize = (w/dpi, h/dpi)
        self.dpi = dpi
        self.params = params or {}
        
        self.fig = Figure(figsize=self.figsize, dpi=self.dpi)
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

        self._x = np.linspace(x_shift, window_dur+x_shift, window_dur)    # горизонтальная ось    

        x_step = 20 # ms
        y_ticks = 20 # uV
        n_xticks = (self.params["xmax_ms"] - self.params["xmin_ms"]) // x_step + 1
        n_yticks = 2 * self._ymax // y_ticks + 1

        x_ticks_orig = np.linspace(self.params["xmin_ms"], self.params["xmax_ms"], n_xticks).astype(int)
        y_ticks_orig = np.linspace(-self._ymax, self._ymax, n_yticks).astype(int)

        x_ticks = np.linspace(self._xmin, self._xmax, n_xticks)

        fontsize_ticks = 10
        fontsize_axes = 10
        fontsize_title = 12

        """создание оси"""
        self.ax = self.fig.add_axes([0.15, 0.1, 0.75, 0.8])   # создаём ось на всё пространство графика [left, bottom, width, height]
        self.ax.set_xlim(self._xmin, self._xmax)
        self.ax.set_ylim(-self._ymax, self._ymax)

        self.ax.set_xticks(x_ticks, x_ticks_orig)
        self.ax.set_yticks(y_ticks_orig)
        
        self.ax.text(-.15, 1, f"[{MICROVOLT}]", fontsize=fontsize_axes, color='black', transform=self.ax.transAxes)
        self.ax.text(1.05, -.05, "[ms]", fontsize=fontsize_axes, color='black', transform=self.ax.transAxes)

        self.ax.grid(True)

        # self.ax.set_axis_off()                      # полностью скрываем оси
        # self.ax.patch.set_visible(False)            # убираем фон осей
        # for spine in self.ax.spines.values():       # убираем рамку
            # spine.set_visible(False)

        # --- копилка для сигнала ---
        self.lines = []
        y_empty = np.full(len(self._x), np.nan)
        for _ in range(self.params["n_channels"]):
            line = Line2D(self._x, y_empty, lw=1.5, color="blue")
            self.ax.draw_artist(line)
            self.lines.append(line)

        self.fig.canvas.draw()
        self.background = self.fig.canvas.copy_from_bbox(self.ax.bbox)

    def update_plot(self, teps):
        self.fig.canvas.restore_region(self.background) # восстанавливаем чистый фон

        for i in range(self.params["n_channels"]):
            self.lines[i].set_ydata(teps[i])
            self.ax.draw_artist(self.lines[i])

        self.fig.canvas.blit()
    