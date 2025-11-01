from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

class MEPPlot(FigureCanvas):
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