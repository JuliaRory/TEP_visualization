from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib import transforms
from matplotlib import colormaps as cm
from matplotlib.colors import ListedColormap
import numpy as np
import time
from copy import deepcopy

from utils.helpers import get_time_ticks, get_voltage_ticks

class TEPsPlot(FigureCanvas):
    """Класс для отрисовки графиков"""
    def __init__(self, parent=None, positions=None, single_w=300, single_h=200, w=1000, h=700, dpi=100, channels=None):
        
        figsize = (w/dpi, h/dpi)
        self.fig = Figure(figsize=figsize, dpi=100) 
        self.fig.patch.set_alpha(0.0)                          # Делаем фон холста matplolib прозрачным
        super().__init__(self.fig)

        self.setStyleSheet("background-color:transparent;")    # делаем виджет прозрачнымs
        
        self.setParent(parent)

        ## variables
        self.n_xticks = 5
        self.n_yticks = 4
        self.channels = channels

        self.ax = self.fig.add_axes([0, 0, 1, 1])   # создаём ось на всё пространство графика [left, bottom, width, height]
        
        self.refresh_plots(positions, single_w, single_h)
       
        self._xdata = []
        self._ydata = None
        self._labelled_data_by_label = None
        self._labelled_colors = {}

        self._viridisBig = cm.get_cmap('jet')
    
    def refresh_plots(self, positions, single_w, single_h):
        # self.fig.canvas.restore_region(self.background) # восстанавливаем чистый фон
        if hasattr(self, "ax"):
            self._clear_labelled_artists()

        self.ticks = []
        self.lines = []       # список с линиями
        self.axes_lines = []  # список с псевдоосями
        self.texts = []       # список с надписями (названия графиков)
        self.affines = []     # список с преобразованиями для позиционирования
        self.transforms = []

        ## axes
        self.ax.clear()
        self.ax.set_axis_off()                      # полностью скрываем оси
        self.ax.patch.set_visible(False)            # убираем фон осей
        for spine in self.ax.spines.values():       # убираем рамку
            spine.set_visible(False)

        self.create_axes(positions, single_w, single_h)

        self.fig.canvas.draw()      # отрисовка
        self.background = self.fig.canvas.copy_from_bbox(self.ax.bbox)      # сохранение фона чистого

        self._last_xlim = None  # границы по оси х не заданы
        self._last_ylim = None  # границы по оси y не заданы      


    def create_axes(self, positions, single_w, single_h, channels=None):
        fig_w_px, fig_h_px = self.fig.get_size_inches() * self.fig.dpi  # ширина и высота в пикселях
        width, height = single_w / fig_w_px, single_h / fig_h_px   # размеры для одного графика

        channels = [f"CH{i+1}" for i in range(len(positions)-1)] if self.channels is None else self.channels.tolist()
        titles = channels + ['']   # последнее без названия - для осей с указанием масштаба  

        # Создаём все линии, используя трансформации для позиционирования 
        for i, (x_px, y_px) in enumerate(positions):
            # нормализуем координаты
            left = x_px / fig_w_px
            bottom = y_px / fig_h_px
            
            # создаём трансформацию для линии (разное положение)
            aff = transforms.Affine2D().scale(width, height).translate(left, bottom)
            tr = aff + self.ax.transAxes
            self.affines.append(aff)
            self.transforms.append(tr)

            # создаём линию (изначально пустую)
            line, = self.ax.plot([], [], lw=0.8, transform=tr, color='tab:blue')
            self.lines.append(line)

            # псевдооси через (0, 0)
            x_axis, = self.ax.plot([0,1], [0.5,0.5], lw=0.6, color='black', transform=tr, alpha=0.6)
            y_axis, = self.ax.plot([0.5,0.5], [0,1], lw=0.6, color='black', transform=tr, alpha=0.6)
            self.axes_lines.append((x_axis, y_axis))

            # ряски на псевдоосях
            oneplot_xticks, oneplot_yticks = [], []
            xticks = np.linspace(0.1, 0.9, self.n_xticks)       # ряски на оси абсцисс 
            for x_t in xticks:
                tick, = self.ax.plot([x_t, x_t], [0.48, 0.52], color='gray', lw=0.5, transform=tr)
                oneplot_xticks.append(tick)

            yticks = np.linspace(0.1, 0.9, self.n_yticks)       # ряски на оси ординат 
            for y_t in yticks:
                tick, = self.ax.plot([0.48, 0.52], [y_t, y_t], color='gray', lw=0.5, transform=tr)
                oneplot_yticks.append(tick)
            self.ticks.append([oneplot_xticks, oneplot_yticks])
            
            # подпись графика
            txt = self.ax.text(left + width / 2, bottom + height * 0.8,
                               titles[i], transform=self.ax.transAxes,
                               ha='center', va='center', fontsize=8, color='gray')
            self.texts.append(txt)


    def update_position(self, positions=None, single_w=300, single_h=200, w=1000, h=700, dpi=100):
        fig_w, fig_h = self.fig.get_size_inches() * self.fig.dpi  # ширина и высота в пикселях

        def px_to_norm(x_px, y_px, w_px, h_px):
            return [x_px / fig_w, y_px / fig_h, w_px / fig_w, h_px / fig_h]

        for i, (x_px, y_px) in enumerate(positions):  # создаём оси по заданным пиксельным координатам
            self.axes[i].set_position(px_to_norm(x_px, y_px, single_w, single_h))
        
        self.fig.set_size_inches(w/dpi, h/dpi, forward=True)

        self.fig.canvas.draw_idle()
        self.backgrounds = [self.fig.canvas.copy_from_bbox(ax.bbox) for ax in self.axes]

    def set_x_shift(self, x_shift, window_dur):
        self._x = np.linspace(x_shift, window_dur+x_shift, int(window_dur))
        if self._last_xlim is not None:
            self._xdata = self._visible_x_normalized(*self._last_xlim)

    def update_axes(self, limits):
        xmin, xmax, ymin, ymax = limits

        x_changed = not hasattr(self, "_last_xlim") or (self._last_xlim != (xmin, xmax))
        y_changed = not hasattr(self, "_last_ylim") or (self._last_ylim != (ymin, ymax))

        self._last_xlim = (xmin, xmax)
        self._last_ylim = (ymin, ymax)
        labelled_data = self._labelled_data_by_label
        labelled_colors = self._labelled_colors

        self._clear_labelled_artists()
        
        if x_changed:
            self._xdata = self._visible_x_normalized(xmin, xmax)  # новая ось абсцисс

        axis_pos = (np.abs(xmin)/(xmax-xmin), np.abs(ymin)/(ymax-ymin))   # новые отнормированные позиции
        xticks_limits = [axis_pos[0]-0.02, axis_pos[0]+0.02]
        yticks_limits = [axis_pos[1]-0.02, axis_pos[1]+0.02]

        self.fig.canvas.restore_region(self.background) # восстанавливаем чистый фон

        for i in range(len(self.axes_lines)):   # пробегаемся по каждому "графику"
            if x_changed or y_changed:          # если изменились пределы, то надо перерисовать линии
                x_axis, y_axis = self.axes_lines[i]
                xticks, yticks = self.ticks[i]
                if y_changed:       # если изменился масштаб по ординате
                    x_axis.set_ydata([axis_pos[1], axis_pos[1]])
                    
                    for x_t in xticks:
                        x_t.set_ydata(yticks_limits)

                if x_changed:       # если изменился масштаб по абсциссе
                    y_axis.set_data([axis_pos[0], axis_pos[0]], [0, 1])
                    for y_t in yticks:
                        y_t.set_xdata(xticks_limits)
                    xticks_new = self._normalize(np.linspace(0, xmax+1, self.n_xticks), axis='x')
                    for i, x_t in enumerate(xticks):
                        x_t.set_xdata([xticks_new[i], xticks_new[i]])

        for line in self.lines:
            line.set_visible(False)

        self.fig.canvas.draw()
        self.background_axes = self.fig.canvas.copy_from_bbox(self.ax.bbox)  # сохраняем чистый фон без линий, только псевдооси и тики
        
        for line in self.lines:
            line.set_visible(True)

        if labelled_data is not None:
            self.update_labelled_data(labelled_data, labelled_colors)
        elif self._ydata is not None:
            self.update_data(self._ydata)

    def update_data(self, data):
        # data [MICROVOLT] - TEP

        self._clear_labelled_artists()
        self._labelled_data_by_label = None
        self._labelled_colors = {}

        assert hasattr(self, "_x"), "не установлены смещение по оси абсцисс и длина окна"

        xmin, xmax = self._last_xlim
        ymin, ymax = self._last_ylim

        self.fig.canvas.restore_region(self.background_axes) # восстанавливаем чистый фон

        for i, y_new in enumerate(data):
            y = self._visible_y(y_new, xmin, xmax)
            y[np.where((y < ymin) | (y > ymax))] = np.nan

            assert len(self._xdata) == len(y), f"widgets/teps_plot: len(x_new) = {len(self._xdata)} !=  len(y_new) = {len(y)}"
            
            y = self._normalize(y, axis='y')
            
            self.lines[i].set_data(self._xdata, y)

            self.ax.draw_artist(self.lines[i])

        self.fig.canvas.blit(self.ax.bbox)

        self._ydata = data
    
    def update_labelled_data(self, data_by_label, colors):
        data_by_label = list(data_by_label)
        self._labelled_data_by_label = data_by_label if data_by_label else None
        self._labelled_colors = dict(colors or {})
        self._clear_labelled_artists()
        if not data_by_label:
            self.refresh_plot()
            return

        assert hasattr(self, "_x"), "x axis is not initialized"
        xmin, xmax = self._last_xlim
        ymin, ymax = self._last_ylim

        background = getattr(self, "background_axes", getattr(self, "background", None))
        if background is not None:
            self.fig.canvas.restore_region(background)
        for line in self.lines:
            line.set_data([], [])

        self._labelled_artists = []
        for label, data in data_by_label:
            color = colors.get(label, "tab:blue")
            for i, y_new in enumerate(data):
                y = self._visible_y(y_new, xmin, xmax)
                y[np.where((y < ymin) | (y > ymax))] = np.nan
                y = self._normalize(y, axis='y')
                line, = self.ax.plot(
                    self._xdata,
                    y,
                    lw=0.9,
                    transform=self.transforms[i],
                    color=color,
                    alpha=0.95,
                )
                self._labelled_artists.append(line)

        proxies = [
            plt.Line2D([0], [0], color=self._labelled_colors.get(label, "tab:blue"), lw=2, label=label)
            for label, _ in data_by_label
        ]
        self._labelled_legend = self.ax.legend(
            handles=proxies,
            loc="upper left",
            fontsize=8,
            frameon=True,
            framealpha=0.85,
        )
        self.fig.canvas.draw_idle()
        self._ydata = None

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

    def draw_loaded_TEPs(self, data_all, labels):
        # data_all : list of np.arrays [n_channels, n_samples]

        self.fig.canvas.restore_region(self.background_axes) # восстанавливаем чистый фон
        
        colors = ListedColormap(self._viridisBig(np.linspace(0, 1, len(data_all))))

        colors = ["green", "orange", "darkred", "pink"]
        xmin, xmax = self._last_xlim
        ymin, ymax = self._last_ylim

        for i in range(64):    # для каждого канала
            for k, data in enumerate(data_all):
                y = self._visible_y(data[i], xmin, xmax)
                y[np.where((y < ymin) | (y > ymax))] = np.nan

                y = self._normalize(y, axis='y')
                line, = self.ax.plot(self._xdata, y, lw=0.8, transform=self.transforms[i], color=colors[k])
                self.ax.draw_artist(line)

        self.fig.canvas.blit(self.ax.bbox)

        for i, label in enumerate(labels):
            print(f">> {label} : {colors[i]}")
        
    def update_image(self):
        """Быстрое обновление всех данных"""

        self.fig.canvas.restore_region(self.background) # восстанавливаем чистый фон

        for i, line in enumerate(self.lines):
            self.ax.draw_artist(line)

        self.fig.canvas.blit(self.ax.bbox)
                
    def refresh_plot(self):
        data_size = (len(self.channels), len(self._x))
        empty_lines = np.full(shape=data_size, fill_value=np.nan)
        self.update_data(empty_lines)

    def _normalize(self, x, axis='x'):
        assert hasattr(self, "_last_xlim"), f"Границы графика ещё не заданы -> невозможно нормализовать данные по оси {axis}."
        xmin, xmax = self._last_xlim if axis == 'x' else self._last_ylim
        return (x - xmin) / (xmax - xmin)

    def _visible_mask(self, xmin, xmax):
        x = self.__dict__.get("_x")
        if x is None:
            return np.array([], dtype=bool)
        return (x > xmin) & (x < xmax)

    def _visible_x_normalized(self, xmin, xmax):
        x = self.__dict__.get("_x")
        if x is None:
            return np.array([])
        return self._normalize(x[self._visible_mask(xmin, xmax)], axis='x')

    def _fit_to_x(self, data):
        x = self.__dict__.get("_x")
        if x is None:
            return self._as_float_array(data)
        data = self._as_float_array(data)
        target_len = len(x)
        if len(data) == target_len:
            return data
        if len(data) > target_len:
            return data[:target_len]

        result = np.full(target_len, np.nan)
        result[:len(data)] = data
        return result

    def _visible_y(self, data, xmin, xmax):
        y = self._fit_to_x(deepcopy(data))
        return y[self._visible_mask(xmin, xmax)]

    @staticmethod
    def _as_float_array(data):
        data = np.asarray(data)
        if data.dtype == object:
            data = np.array([np.nan if value is None else value for value in data], dtype=float)
        else:
            data = data.astype(float, copy=False)
        return data
        
    
