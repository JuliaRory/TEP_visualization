from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import transforms
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtCore import pyqtSignal

import numpy as np
from collections import deque

class MEPPlot(FigureCanvas):
    """
    Figure с прорисованными n графиками друг за другом. 

    Args:
        w (int): width of the figure
        h (int): height of the figure
        Fs (int): sample rate
        settings: settings of the mep plot
        dpi (int): dpi of the figure
    
    Attributes:


    Private Attributes:
        _start_amp, _end_amp (int, ind): the start and the end point for amplitude calculation in samples
        _xmin, _xmax (int, int): range of the x axes in samples
        _ymax (int): range of the y axes in samples (-_ymax, y_max)
        _x (ndarray): x axes values


    Signals:
        stimuliFinished (pyqtSignal): срабатывает после окончания всего воспроизведения
    """

    amp_counter = pyqtSignal(int)

    """Класс для отрисовки графиков"""
    def __init__(self, parent=None, w=1000, h=700,  Fs=5000, settings=None, titles=None, emphasize_first=True, dpi=100):
        
        self.figsize = (w/dpi, h/dpi)
        self.dpi = dpi
        self.settings = settings        # settings_plot single_mep
        self.titles_label = titles
        self.emphasize_first = emphasize_first

        self.Fs = Fs
        self.ms_to_sample = lambda x: int(x / 1000 * Fs)
        
        self.fig = Figure(figsize=self.figsize, dpi=dpi) 
        self.fig.patch.set_alpha(0.0)                          # Делаем фон холста matplolib прозрачным
        
        super().__init__(self.fig)
        self.setParent(parent)

        self.setFixedSize(int(w), int(h))   # !!! временные меры

        self.setStyleSheet("background-color:transparent;")    # делаем виджет прозрачнымs

        self._init_state()
        
    def _init_state(self):
        self._sync_settings()

        """Прорисовка осей"""
        self.ax = self.fig.add_axes([0, 0, 1, 1])   # создаём ось на всё пространство графика [left, bottom, width, height]

        self.amps = [None for _ in range(self.n_plots)]        # amplitudes
        self.lats = [None for _ in range(self.n_plots)]        # latencies

        self.refresh_plots()

    def _sync_settings(self):
        self._xmin = self.ms_to_sample(self.settings.xmin_ms)
        self._xmax = self.ms_to_sample(self.settings.xmax_ms)
        if self._xmax <= self._xmin:
            self._xmax = self._xmin + 1

        self._ymax = max(float(self.settings.max_amp_mV), 1e-9)
        self.n_plots = max(int(self.settings.n_plots), 1)

        window_dur = max(self._xmax - self._xmin, 1)
        x = np.arange(self._xmin, self._xmax)
        if len(x) != window_dur:
            x = np.linspace(self._xmin, self._xmax, window_dur, endpoint=False)
        self._x = self._normalize(x, axis='x')

        self._start_amp = max(0, self.ms_to_sample(self.settings.amp_start_ms) - self._xmin)
        self._end_amp = min(window_dur, self.ms_to_sample(self.settings.amp_end_ms) - self._xmin)
        if self._end_amp <= self._start_amp:
            self._end_amp = min(window_dur, self._start_amp + 1)

    def refresh_plots(self):
        """Перерисовка всех осей для обновления размеров"""

        self.ax.clear()
        self.lines = []                             # здесь будут накапливаться до n графиков миограммы
        self.titles = []
        self.ax.set_axis_off()                      # полностью скрываем оси
        self.ax.patch.set_visible(False)            # убираем фон осей
        for spine in self.ax.spines.values():       # убираем рамку
            spine.set_visible(False)

        self.create_axes()

        # сохранение изображения пустых осей 
        self.fig.canvas.draw()
        self.background = self.fig.canvas.copy_from_bbox(self.ax.bbox)

    def rebuild_from_settings(self, reset_history=True):
        self._sync_settings()
        if reset_history or len(self.amps) != self.n_plots:
            self.amps = [None for _ in range(self.n_plots)]
            self.lats = [None for _ in range(self.n_plots)]
        else:
            self.amps = list(self.amps[:self.n_plots]) + [None] * max(0, self.n_plots - len(self.amps))
            self.lats = list(self.lats[:self.n_plots]) + [None] * max(0, self.n_plots - len(self.lats))
        self.refresh_plots()
        self.emit_threshold_count()

    def set_sampling_rate(self, Fs):
        if Fs == self.Fs:
            return
        self.Fs = Fs
        self.ms_to_sample = lambda x: int(x / 1000 * Fs)
        self.rebuild_from_settings(reset_history=True)


    def create_axes(self):
        """Создаёт оси со всеми нужными параметрами"""
        # Перенести все одноразово создаваесые параметры в _init_state!!!!!!!!!!!!


        x_step = 20 # ms
        n_xticks = max((self.settings.xmax_ms - self.settings.xmin_ms) // x_step + 1, 2)

        x_ticks_orig = np.linspace(self.settings.xmin_ms, self.settings.xmax_ms, n_xticks).astype(int)
        y_ticks_orig = np.linspace(-self._ymax, self._ymax, 5)

        x_ticks = self._normalize(np.linspace(self._xmin, self._xmax, n_xticks), axis='x')
        y_ticks = self._normalize(y_ticks_orig, axis='y')

        fontsize_ticks = 10
        fontsize_axes = 12
        fontsize_title = 10

        """расположение графиков"""
        # --- размеры в пикселях ---
        fig_w_px, fig_h_px = self.fig.get_size_inches() * self.fig.dpi                # px
        width_px, height_px = 0.7*fig_w_px/self.n_plots, 0.7*fig_h_px                           # px 
        d_width = (1-0.7-0.1) * fig_w_px / self.n_plots                                       # px : расстояние между графиками по горизонтали
        left0_px, bottom_px = 0.1*fig_w_px, 0.1*fig_h_px                             # px : положение первого графика (лево, низ)
        
        # --- отнормированные размеры ---
        width, height = width_px / fig_w_px, height_px / fig_h_px    # ширина и высота одного графика
        bottom = bottom_px / fig_h_px                                # положение нижнего края графиков

        for i in range(self.n_plots):
            add_dw = 0.5 * d_width if i > 0 else 0
            left = (left0_px + add_dw + i * (width_px + d_width) )/ fig_w_px    # положение области в нормированных координатах (0–1)
            
            # создаём трансформацию для линии (разное положение)
            aff = transforms.Affine2D().scale(width, height).translate(left, bottom)
            tr = aff + self.ax.transAxes

            # --- фон области ---
            color, lw = ('black', 1.5) if (i == 0) and self.emphasize_first else ('gray', 1.0)

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
            if (i == 0) and self.emphasize_first:  # только на первом графике
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
                            self._format_axis_value(y_ticks_orig[j]), transform=tr,
                            ha='center', va='center', fontsize=fontsize_ticks, color='darkgray')
                
                self.ax.text(-.5, 1, "mV", transform=tr, fontsize=fontsize_axes, color='darkgray')
                self.ax.text(1.05, -.05, "ms", transform=tr, fontsize=fontsize_axes, color='darkgray')
            
            # --- надпись над графиком ---
            title = self._title_for_index(i)
            color = 'black' if (i == 0) and self.emphasize_first else 'darkgray'
            text_title = self.ax.text(-0.1, 1.1, title, transform=tr, fontsize=fontsize_title, color=color)
            self.titles.append(text_title)

            # --- копилка для сигнала ---
            line = Line2D(self._x, np.full(len(self._x), np.nan), lw=1.5, color="blue", transform=tr, zorder=2)
            self.ax.draw_artist(line)
            self.lines.append(line)
      
    def update_emg(self, emg, normalize=True):
        self._clear_labelled_legend()
        emg = np.asarray(emg, dtype=float).flatten()
        if len(emg) != len(self._x):
            n = min(len(emg), len(self._x))
            padded = np.full(len(self._x), np.nan)
            if n > 0:
                padded[:n] = emg[:n]
            emg = padded

        self.fig.canvas.restore_region(self.background) # восстанавливаем чистый фон

        if sum(np.isfinite(emg)) != 0:
            self._calcalate_MEP(emg)

        for i in reversed(range(1, self.n_plots)):
            line = self.lines[i]
            y = self.lines[i-1].get_ydata()
            line.set_ydata(y)
            self.ax.draw_artist(line)

        new_data = self._normalize(emg, axis='y') if normalize else emg
        self.lines[0].set_ydata(new_data)
        self.ax.draw_artist(self.lines[0])
        
        self.fig.canvas.blit(self.ax.bbox)

    def update_emg_history(self, entries, colors):
        self._clear_labelled_legend()
        self.fig.canvas.restore_region(self.background)

        entries = list(entries)[-self.n_plots:]
        entries = list(reversed(entries))
        self.amps = [None for _ in range(self.n_plots)]
        self.lats = [None for _ in range(self.n_plots)]

        for i, line in enumerate(self.lines):
            if i < len(entries):
                label, emg = entries[i]
                emg = np.asarray(emg, dtype=float).flatten()
                if len(emg) != len(self._x):
                    n = min(len(emg), len(self._x))
                    padded = np.full(len(self._x), np.nan)
                    if n > 0:
                        padded[:n] = emg[:n]
                    emg = padded
                if sum(np.isfinite(emg)) != 0:
                    self._calculate_mep_at_index(i, emg)
                line.set_ydata(self._normalize(emg, axis='y'))
                line.set_color(colors.get(label, "tab:blue"))
                if self.amps[i] is None:
                    self.titles[i].set_text(label)
                else:
                    self.titles[i].set_text(f"{label}: {self.amps[i]} mV, {self.lats[i]} ms")
            else:
                line.set_ydata(np.full(len(self._x), np.nan))
                line.set_color("gray")
                self.titles[i].set_text(self._title_for_index(i))
            self.ax.draw_artist(line)
            self.ax.draw_artist(self.titles[i])

        labels = []
        handles = []
        for label, _emg in entries:
            if label in labels:
                continue
            labels.append(label)
            handles.append(Line2D([0], [0], color=colors.get(label, "tab:blue"), lw=2, label=label))
        self._labelled_legend = self.ax.legend(handles=handles, loc="upper left", fontsize=8, framealpha=0.85) if handles else None
        self.emit_threshold_count()
        self.fig.canvas.draw_idle()

    def _calculate_mep_at_index(self, index, data):
        x = data[self._start_amp:self._end_amp]
        x = x[np.isfinite(x)]
        if len(x) == 0:
            return
        min_ind = int(np.argmin(x))
        max_ind = int(np.argmax(x))
        self.amps[index] = round(float(x[max_ind] - x[min_ind]), 2)
        peak_sample = self._start_amp + max_ind
        self.lats[index] = round(self.settings.xmin_ms + peak_sample * 1000 / self.Fs)
        title_n = self._title_for_index(index)
        self.titles[index].set_text(f"{title_n} : {self.amps[index]} mV, {self.lats[index]} ms")

    def _clear_labelled_legend(self):
        legend = getattr(self, "_labelled_legend", None)
        if legend is not None:
            try:
                legend.remove()
            except ValueError:
                pass
        self._labelled_legend = None

    def _normalize(self, x, axis='x'):
        xmin, xmax = (self._xmin, self._xmax) if axis == 'x' else (-self._ymax, self._ymax)
        return (x - xmin) / (xmax - xmin)

    def _calcalate_MEP(self, data):
        self.amps = [None] + list(self.amps[:-1])
        self.lats = [None] + list(self.lats[:-1])

        x = data[self._start_amp:self._end_amp]
        x = x[np.isfinite(x)]
        if len(x) == 0:
            self.emit_threshold_count()
            return
        
        # Индексы глобального минимума/максимума 
        min_ind = int(np.argmin(x))
        max_ind = int(np.argmax(x))

        self.amps[0] = round(float(x[max_ind] - x[min_ind]), 2)
        peak_sample = self._start_amp + max_ind
        self.lats[0] = round(self.settings.xmin_ms + peak_sample * 1000 / self.Fs)

        self.emit_threshold_count()

        for i in range(self.n_plots):
            title_n = self._title_for_index(i)
            title = title_n if self.amps[i] is None else f"{title_n} : {self.amps[i]} mV, {self.lats[i]} ms"
            # title = f"#{i+1}" if self.amps[i] is None else f"#{i+1} : {self.amps[i]} mV, {self.lats[i]} ms"
            self.titles[i].set_text(title)
            self.ax.draw_artist(self.titles[i])

    def _title_for_index(self, i):
        if self.titles_label is not None and i < len(self.titles_label):
            return self.titles_label[i]
        return f"#{i+1}"

    @staticmethod
    def _format_axis_value(value):
        value = round(float(value), 2)
        if value == 0:
            value = 0.0
        return f"{value:.2f}"


    def _calculate_above_thr(self):
        thr = float(getattr(self.settings, "thr", 0.5))
        n_thr = int(getattr(self.settings, "n_plots_thr", self.n_plots))
        n_thr = max(1, min(n_thr, self.n_plots))
        amps = np.asarray([
            np.nan if amp is None else float(amp)
            for amp in self.amps[:n_thr]
        ], dtype=float)
        amps_clean = amps[np.isfinite(amps)]
        return int(np.sum(amps_clean >= thr))

    def emit_threshold_count(self):
        self.amp_counter.emit(self._calculate_above_thr())

        
    def refresh_plot(self):
        self._clear_labelled_legend()
        self.fig.canvas.restore_region(self.background) # восстанавливаем чистый фон
        self.fig.canvas.blit(self.ax.bbox)
