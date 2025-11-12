from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import numpy as np

MICROVOLT = "\u03BC"+"V"

class MEPsSupplPlot(FigureCanvas):
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
        # self._xmin, self._xmax = self.ms_to_sample(self.params["xmin_ms"]), self.ms_to_sample(self.params["xmax_ms"])
        # self._ymax = self.params["max_amp_mV"]

        self._mean = lambda x: np.mean(x[self.params["channels_nearest_n"]], axis=0)

        x_shift = self.ms_to_sample(self.params["xmin_ms"])
        window_dur = self.ms_to_sample(self.params["xmax_ms"]) - self.ms_to_sample(self.params["xmin_ms"])

        self._x = np.linspace(x_shift, window_dur+x_shift, window_dur)    # горизонтальная ось    

        self.x_step = 20 # ms
        self.y_ticks = 20 # uV

        # n_xticks = (self.params["xmax_ms"] - self.params["xmin_ms"]) // x_step + 1
        # n_yticks = 2 * self._ymax // y_ticks + 1

        # x_ticks_orig = np.linspace(self.params["xmin_ms"], self.params["xmax_ms"], n_xticks).astype(int)
        # y_ticks_orig = np.linspace(-self._ymax, self._ymax, n_yticks).astype(int)

        # x_ticks = np.linspace(self._xmin, self._xmax, n_xticks)

        fontsize_ticks = 10
        fontsize_axes = 10
        fontsize_title = 12

        """создание оси"""
        self.ax = self.fig.add_axes([0.15, 0.1, 0.75, 0.8])   # создаём ось на всё пространство графика [left, bottom, width, height]
        # self.ax.set_xlim(self._xmin, self._xmax)
        # self.ax.set_ylim(-self._ymax, self._ymax)

        # self.ax.set_xticks(x_ticks, x_ticks_orig)
        # self.ax.set_yticks(y_ticks_orig)
        
        self.update_limits(self.params["xmax_ms"], self.params["xmin_ms"], self.params["max_amp_emg_mV"] )

        self.ax.text(-.15, 1, f"[mV]", fontsize=fontsize_axes, color='black', transform=self.ax.transAxes)
        self.ax.text(1.05, -.05, "[ms]", fontsize=fontsize_axes, color='black', transform=self.ax.transAxes)

        self.ax.set_title("Averaged MEP")

        self.ax.grid(True)

        # --- копилка для сигнала ---
        # self.lines = []
        y_empty = np.full(len(self._x), np.nan)
        (color, lw) = ("black", 1.5)
        # (color, lw) = ("gray", 0.5) if i < n-1 else ("black", 1.5)
        line = Line2D(self._x, y_empty, lw=lw, color=color)
        self.ax.add_line(line)
        self.line = line

        self.fig.canvas.draw()
        self.background = self.fig.canvas.copy_from_bbox(self.ax.bbox)

    def update_plot(self, teps):
        self.fig.canvas.restore_region(self.background)  # восстанавливаем чистый фон
        self.line.set_ydata(teps)
        self.ax.draw_artist(self.line)

        self.fig.canvas.blit(self.ax.bbox)
    
    def compare_plot(self, teps):
        self.fig.canvas.restore_region(self.background)  # восстанавливаем чистый фон
        # colors = ListedColormap(self._viridisBig(np.linspace(0, 1, len(teps))))
        colors = ["green", "orange", "darkred", "pink"]
        # for i in range(teps.shape[0]):          # для каждого канала
        #     self.lines[i].set_ydata(teps[i])
        #     self.ax.draw_artist(self.lines[i])

        # self.lines[-1].set_ydata(self._mean(teps))     # усреднённые каналы вокруг С3
        # self.ax.draw_artist(self.lines[-1])
        (color, lw) = ("black", 1.5)
        for i in range(len(teps)):
            
            y = teps[i]
            # print(y)
            # print(y.shape)
            # print(self._x.shape)
            line, = self.ax.plot(self._x, y, lw=lw, color=colors[i])
            self.ax.draw_artist(line)

        self.fig.canvas.blit(self.ax.bbox)
    
    def update_limits(self, xmax_ms=100, xmin_ms=-20, ymax=100):
    
        xmin, xmax = self.ms_to_sample(xmin_ms), self.ms_to_sample(xmax_ms)

        self.ax.set_xlim(xmin, xmax)
        self.ax.set_ylim(-ymax, ymax)

        n_xticks = (xmax_ms - xmin_ms) // self.x_step + 1
        n_yticks = 5#2 * ymax / self.y_ticks + 1

        x_ticks_orig = np.linspace(xmin_ms, xmax_ms, n_xticks).astype(int)
        y_ticks_orig = np.linspace(-ymax, ymax, n_yticks).round(2)

        x_ticks = np.linspace(xmin, xmax, n_xticks)

        self.ax.set_xticks(x_ticks, x_ticks_orig)
        self.ax.set_yticks(y_ticks_orig)

        self.fig.canvas.draw_idle()

        
    