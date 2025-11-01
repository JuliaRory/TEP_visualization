from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

class TEPsSupplPlot(FigureCanvas):
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
        self.ax_emg.set_ylim([-100, 100])
        self.ax_emg.set_xlim([-10*Fs/1000, 100*Fs/1000])
        self.ax_emg.set_xticks(np.arange(0, 101, 20) *Fs/1000, np.arange(0, 101, 20))
        #print([-10*Fs/1000, 30*Fs/1000])
        # self.ax_emg.set_xticks((np.linspace(0, 100, 20) *Fs/1000).astype(int), np.linspace(0, 100, 20))
        self.ax_emg.set_ylabel('mcV', rotation = 360, labelpad=2,  loc='top')
        self.ax_emg.set_xlabel('ms', loc='right')
        self.ax_emg.grid(True, alpha=.4, color='gray')
        self.lines = [self.ax_emg.plot([], []) for _ in range(64)]

        self.fig.canvas.draw_idle()
        self.backgrounds = [self.fig.canvas.copy_from_bbox(ax.bbox) for ax in self.axes]

    def update_plot(self, teps, x_shift=0):

        length = teps.shape[1]
        x = np.linspace(x_shift, length-x_shift, length)
        
        for i in range(teps.shape[0]):
            self.lines[i][0].set_data(x, teps[i])
            self.ax_emg.draw_artist(self.lines[i][0])
        self.fig.canvas.draw_idle()
