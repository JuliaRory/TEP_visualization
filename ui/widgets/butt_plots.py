from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib import colormaps as cm
from matplotlib.colors import ListedColormap
import numpy as np

from PyQt5.QtWidgets import QLabel

from utils.helpers import get_time_ticks, get_voltage_ticks

MICROVOLT = "\u03BC"+"V"

class buttPlot(FigureCanvas):
    def __init__(self, parent=None, w=1000, h=700, settings=None, Fs=5000, dpi=100):
        self._figsize = (w/dpi, h/dpi)

        self.fig = Figure(figsize=self._figsize, dpi=dpi)
        self.fig.patch.set_alpha(0.0)                          # Делаем фон холста matplolib прозрачным
        super().__init__(self.fig)

        self.setStyleSheet("background-color:transparent;")    # делаем виджет прозрачнымs
        self.setMinimumWidth(int(300))   # !!! временные меры

        self.setParent(parent)

        self.settings = settings or {}
        self._ms_to_sample = lambda x: int(x / 1000 * Fs)

        self._init_state()
        
    def _init_state(self):
        """создание осей"""
        # создаём ось на часть пространства графика[left, bottom, width, height]
        self._ax = self.fig.add_axes([0.15, 0.1, 0.75, 0.8])
        self._ax.grid(True)

        # подписываем оси
        y_units = self.settings.units if self.settings.units == 'mV' else MICROVOLT
        self._ax.text(-.20, 1, f"[{y_units}]", color='black', transform=self._ax.transAxes)
        self._ax.text(1.05, -.05, "[ms]", color='black', transform=self._ax.transAxes)
        # название графика
        self._ax.set_title(self.settings.title) 
        
        self._ax.axvline(0) # рисуем момент 0 
        self._ax.axhline(0) # рисуем амплитуду 0

        # прямоугольник для синхронизации масштаба на основных графиках и этом
        self._rect = Rectangle((0, 0), width=(0), height=(0),
                    linewidth=2, edgecolor='red', facecolor='none', visible=False)
        self._ax.add_patch(self._rect)

        self.fig.canvas.draw()
        self._background = self.fig.canvas.copy_from_bbox(self._ax.bbox)
        
        """параметры"""
        self._mean = lambda x: np.mean(x[self.settings.channels_nearest_n], axis=0)   # функция для усреднения каналов интереса

        self._last_xlim = None      # границы по оси х не заданы
        self._last_amp = None       # границы по оси y не заданы
        self._labelled_kind = None
        self._labelled_data_by_label = None
        self._labelled_colors = {}

        self._viridisBig = cm.get_cmap('jet')       # палитра для разноцветных графиков

        self._setup_tools_for_interaction()
        
    def _setup_tools_for_interaction(self):
        # Подключаем события мыши
        self.mpl_connect("motion_notify_event", self.on_mouse_move)
        # self.mpl_connect("button_press_event", self.on_mouse_click)

        # QLabel для всплывающих координат
        self.coord_label = QLabel("", self)
        self.coord_label.setStyleSheet("background-color: white; border: 1px solid black;")
        self.coord_label.setVisible(False)

        # флаг, показывать ли координаты
        self.show_coords = False
        
    def set_x_shift(self, x_shift, window_dur, signal='TEP'):
        """Задать смещение для оси х и на основе этого пустышки для накопления сигнала"""
        self._x = np.linspace(x_shift, window_dur+x_shift, window_dur)
        if signal == 'TEP':
            if hasattr(self, "_lines"):
                for line in self._lines:
                    line.set_xdata(self._x)
                    line.set_ydata(self._fit_to_x(line.get_ydata()))
            else:
                self._create_empty_TEPs()
        elif signal == 'MEP':
            if getattr(self, "_mep_shadow", None) is not None:
                self._mep_shadow.remove()
                self._mep_shadow = None
            if hasattr(self, "_line"):
                self._line.set_xdata(self._x)
                self._line.set_ydata(self._fit_to_x(self._line.get_ydata()))
            else:
                self._create_empty_MEPs()

    def _create_empty_TEPs(self):
        # --- копилка для сигнала ---
        self._lines = []
        y_empty = np.full(len(self._x), np.nan)
        n = self.settings.n_channels + 1
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
        self._mep_shadow = None
        self._mep_spread = None

    def update_axes(self, xmax_ms=100, xmin_ms=-20, amp=100, which='TEPs'):
        # self.fig.canvas.restore_region(self._background)  # восстанавливаем чистый фон
        """Обновить масштаб"""
        amp = max(abs(float(amp)), 1e-12)
        xmin, xmax = self._ms_to_sample(xmin_ms), self._ms_to_sample(xmax_ms)
        labelled_kind = self._labelled_kind
        labelled_data = self._labelled_data_by_label
        labelled_colors = self._labelled_colors
        if labelled_kind == which:
            self._clear_labelled_artists()

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
            y_ticks = np.concatenate([neg, pos]).round(self.settings.round)              # чтобы гарантировать 0
            self._ax.set_yticks(y_ticks)
            self._ax.set_ylim(-amp, amp)
        
        if hasattr(self, "_lines"):
            for line in self._lines:
                line.set_visible(False)
        if hasattr(self, "_line"):
            self._line.set_visible(False)
        if getattr(self, "_mep_shadow", None) is not None:
            self._mep_shadow.remove()
            self._mep_shadow = None

        self.fig.canvas.draw()
        self._background_clear = self.fig.canvas.copy_from_bbox(self._ax.bbox)
        self._background = self.fig.canvas.copy_from_bbox(self._ax.bbox)

        if hasattr(self, "_lines"):
            for line in self._lines:
                line.set_visible(True)
            if labelled_kind == "TEPs" and labelled_data is not None:
                self.update_labelled_TEPs(labelled_data, labelled_colors)
            else:
                self.redraw("TEPs")
        if hasattr(self, "_line"):
            self._line.set_visible(True)
            if labelled_kind == "MEPs" and labelled_data is not None:
                self.update_labelled_MEPs(labelled_data, labelled_colors)
            else:
                self.redraw("MEPs")
    
    def draw_rectangle(self, xmin_ms, xmax_ms, ymin, ymax):
        """Нарисовать прямоугольник для синхронизации масштабов"""
        self.fig.canvas.restore_region(self._background_clear)  # восстанавливаем чистый фон

        xmin, xmax = self._ms_to_sample(xmin_ms), self._ms_to_sample(xmax_ms)
        self._rect.set_xy((xmin, ymin))
        self._rect.set_width((xmax-xmin))
        self._rect.set_height((ymax-ymin))

        if not self._rect.get_visible():
            self._rect.set_visible(True)
        
        self._ax.draw_artist(self._rect)
        self.fig.canvas.blit()

        self._background = self.fig.canvas.copy_from_bbox(self._ax.bbox)
        if self._labelled_kind == "TEPs" and self._labelled_data_by_label is not None:
            self.update_labelled_TEPs(self._labelled_data_by_label, self._labelled_colors)
        elif hasattr(self, "_lines"):
            self.redraw("TEPs")

    def update_TEPs(self, teps):
        self._clear_labelled_artists()
        self._clear_labelled_cache()
        """Нарисовать новые TEPs"""
        self.fig.canvas.restore_region(self._background)  # восстанавливаем чистый фон
        teps = np.asarray([self._fit_to_x(row) for row in np.asarray(teps)])
        
        for i in range(teps.shape[0]):          # для каждого канала
            self._lines[i].set_ydata(teps[i])
            self._ax.draw_artist(self._lines[i])
        
        self._lines[i+1].set_ydata(self._mean(teps))     # усреднённые каналы вокруг С3
        self._ax.draw_artist(self._lines[i+1])

        self.fig.canvas.blit(self._ax.bbox)
    
    def update_MEPs(self, meps, spread=None):
        self._clear_labelled_artists()
        self._clear_labelled_cache()
        """Нарисовать новые MEPs"""
        self.fig.canvas.restore_region(self._background)  # восстанавливаем чистый фон

        if getattr(self, "_mep_shadow", None) is not None:
            self._mep_shadow.remove()
            self._mep_shadow = None

        meps = self._fit_to_x(meps)
        if spread is not None:
            spread = self._fit_to_x(spread)
            self._mep_shadow = self._ax.fill_between(
                self._x,
                meps - spread,
                meps + spread,
                color="black",
                alpha=0.16,
                linewidth=0,
            )
            self._ax.draw_artist(self._mep_shadow)
        self._mep_spread = spread

        self._line.set_ydata(meps)
        self._ax.draw_artist(self._line)

        self.fig.canvas.blit(self._ax.bbox)
    
    def update_labelled_TEPs(self, data_by_label, colors):
        data_by_label = list(data_by_label)
        self._labelled_kind = "TEPs" if data_by_label else None
        self._labelled_data_by_label = data_by_label if data_by_label else None
        self._labelled_colors = dict(colors or {})
        self._clear_labelled_artists()
        if not data_by_label:
            self.refresh_plot(which="TEPs")
            return
        self.fig.canvas.restore_region(self._background)
        if hasattr(self, "_lines"):
            for line in self._lines:
                line.set_ydata(np.full(len(self._x), np.nan))

        self._labelled_artists = []
        for label, teps in data_by_label:
            teps = np.asarray([self._fit_to_x(row) for row in np.asarray(teps)])
            line, = self._ax.plot(self._x, self._mean(teps), lw=1.8, color=self._labelled_colors.get(label, "tab:blue"), label=label)
            self._labelled_artists.append(line)
        self._labelled_legend = self._ax.legend(loc="upper right", fontsize=8, framealpha=0.85)
        self.fig.canvas.draw_idle()

    def update_labelled_MEPs(self, data_by_label, colors):
        data_by_label = list(data_by_label)
        self._labelled_kind = "MEPs" if data_by_label else None
        self._labelled_data_by_label = data_by_label if data_by_label else None
        self._labelled_colors = dict(colors or {})
        self._clear_labelled_artists()
        if not data_by_label:
            self.refresh_plot(which="MEPs")
            return
        self.fig.canvas.restore_region(self._background)
        if hasattr(self, "_line"):
            self._line.set_ydata(np.full(len(self._x), np.nan))

        self._labelled_artists = []
        for label, meps in data_by_label:
            line, = self._ax.plot(self._x, self._fit_to_x(meps), lw=1.8, color=self._labelled_colors.get(label, "tab:blue"), label=label)
            self._labelled_artists.append(line)
        self._labelled_legend = self._ax.legend(loc="upper right", fontsize=8, framealpha=0.85)
        self.fig.canvas.draw_idle()

    def _clear_labelled_artists(self):
        for artist in getattr(self, "_labelled_artists", []):
            try:
                artist.remove()
            except (ValueError, NotImplementedError):
                pass
        self._labelled_artists = []
        legend = getattr(self, "_labelled_legend", None)
        if legend is not None:
            try:
                legend.remove()
            except (ValueError, NotImplementedError):
                pass
        self._labelled_legend = None

    def _clear_labelled_cache(self):
        self._labelled_kind = None
        self._labelled_data_by_label = None
        self._labelled_colors = {}

    def redraw(self, which="TEPs", empty=False):
        
        if which=='TEPs':
            teps = np.array([self._lines[i].get_ydata() for i in range(len(self._lines)-1)]) 
            if empty:
                teps = np.full_like(teps, fill_value=np.nan)
            self.update_TEPs(teps)
        else:
            meps = self._line.get_ydata()
            spread = getattr(self, "_mep_spread", None)
            if empty:
                meps = np.full_like(meps, fill_value=np.nan)
                spread = None
            self.update_MEPs(meps, spread=spread)

    def _fit_to_x(self, data):
        data = self._as_float_array(data)
        target_len = len(self._x)
        if len(data) == target_len:
            return data
        if len(data) > target_len:
            return data[:target_len]

        result = np.full(target_len, np.nan)
        result[:len(data)] = data
        return result

    @staticmethod
    def _as_float_array(data):
        data = np.asarray(data)
        if data.dtype == object:
            data = np.array([np.nan if value is None else value for value in data], dtype=float)
        else:
            data = data.astype(float, copy=False)
        return data


    def draw_loaded_multiple_sessions(self, session_data, signal="TEP"):
        """Загрузить данные"""
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
    
    def refresh_plot(self, which='TEPs'):
        self.redraw(which=which, empty=True)
    
    # === события ===
    def on_mouse_move(self, event):
        if self.show_coords and event.inaxes:
            text = f"x: {event.xdata:.2f}, y: {event.ydata:.2f}"
            # перемещаем QLabel рядом с курсором
            self.coord_label.setText(text)
            # координаты QLabel в координатах окна
            x_win, y_win = self.canvas.mouseEventCoords(event)
            self.coord_label.move(int(x_win + 10), int(y_win + 10))
            self.coord_label.setVisible(True)

    def mouseMoveEvent(self, event):
        
        if event.button == 3:  # правая кнопка мыши
            self.show_coords = not self.show_coords
            if not self.show_coords:
                self.coord_label.setVisible(False)

# fontsize_ticks = 10
# fontsize_axes = 10
# fontsize_title = 12
        
    
