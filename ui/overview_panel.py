from PyQt5.QtWidgets import QFrame,  QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer

from utils.ui_helpers import create_spin_box, create_button, create_check_box
from utils.layout_utils import create_hbox

from ui.widgets.butt_plots import buttPlot
from ui.widgets.topoplot_plot import TopoPlot, ColorBar

MICROVOLT = "\u03BC"+"V"

class overviewPanel(QFrame):
    """
    Для чего нужен
    Args: - параметры входные

    Attributes: - что можно использовать извне

    """
    def __init__(self, parent=None, settings=None, Fs=5000, init_size=[600, 800]):
        super().__init__(parent)
        """Внешний вид виджета"""
        self.resize(init_size[0], init_size[1])
        
        """Параметры"""
        self.settings = settings # plot_settings.overview_panel
        
        self.Fs = Fs
        
        self._init_state()
      
        """Визуальная часть виджета"""
        self._setup_ui()
        self._setup_layout()
        
        """Связи"""
        self._setup_connections()

        """Финализация"""
        self._post_init()

    def _init_state(self):
        self.h = self.height()
        self.w = self.width()
        
        self.setObjectName("tep_suppl_panel")    # для привязки стиля
        self.ms_to_sample = lambda x: int(x / 1000 * self.Fs)

        self._ratio = self.settings.topo_butt_ratio
        self._butt_plot_height = int((1-self._ratio)*self.h//2)

        
    def _setup_ui(self):
        self.figure_TEP = self._create_butt_plot(settings=self.settings.butts_plot.TEP)
        self.figure_MEP = self._create_butt_plot(settings=self.settings.butts_plot.MEP)

        if self.settings.topoplot.draw:     
            self._create_topoplots()        # --> create self.figure_topo [list]
        
        self._setup_settings_widgets()

    def _create_butt_plot(self, settings):
        figure = buttPlot(self, 
                            w=self.w, h=self._butt_plot_height, 
                            settings=settings,
                            Fs=self.Fs)
        figure.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return figure

    def _create_topoplots(self):
        n = self.settings.topoplot.n_plots
        w_available = 0.8 * self.width()
        w_topo = int(w_available // n)
        self.figure_topo = [TopoPlot(self, w=w_topo, timestamp=self.settings.topoplot.timestamps_ms[i], settings=self.settings.topoplot) for i in range(n)]
        
        self.colorbar = ColorBar(self, image=self.figure_topo[0].im)

    def _setup_settings_widgets(self):
        # time range
        self._spinbox_min_time = create_spin_box(-300, 0, self.settings.butts_plot.xmin_ms, parent=self, w=50, step=5)
        self._spinbox_max_time = create_spin_box(0, 500, self.settings.butts_plot.xmax_ms, parent=self, w=50, step=5)
    
        # TEPs
        self._spinbox_max_amp_tep = create_spin_box(0, 10000, self.settings.butts_plot.TEP.amp, parent=self, w=50, step=10)
        self._button_interactive_plot = create_button(text="Интерактив", disabled=True)
        self.checkbox_average_teps = create_check_box(self.settings.butts_plot.TEP.do_averaging, text="Усреднение", parent=self)

        # MEPs 
        self.checkbox_average_meps = create_check_box(self.settings.butts_plot.MEP.do_averaging, text="Усреднение", parent=self)

        # Для топоплотов
        if self.settings.topoplot.draw:   
            ts = self.settings.topoplot.timestamps_ms
            
            self.spinbox_ts_1 = create_spin_box(-20, 1000, ts[0], parent=self, w=50, step=1)
            self.spinbox_ts_2 = create_spin_box(-20, 1000, ts[1], parent=self, w=50, step=1)
            self.spinbox_ts_3 = create_spin_box(-20, 1000, ts[2], parent=self, w=50, step=1)
            self.spinbox_ts = [self.spinbox_ts_1, self.spinbox_ts_2, self.spinbox_ts_3]

        # self._button_apply = create_button('Применить', checkable=True, parent=self, w=150)

        self._frame_settings = QFrame(self)
    
    def _setup_layout(self):

        if self.settings.topoplot.draw:
            n = self.settings.topoplot.n_plots
            d_width = (1-0.8-0.1) * self.w / n
            left = int(0.1 * self.w)
            for i, topoplot in enumerate(self.figure_topo):
                left_new = int(left+(topoplot.width() + d_width)*i)
                topoplot.move(left_new, left)
                self.spinbox_ts[i].move(left_new + topoplot.width()//2-25, left-30)
            
            self.colorbar.move(0, 0)

        TEP_plot_pos_y = int((1-self._ratio)*self.h) - self.figure_TEP.height()
        MEP_plot_pos_y = TEP_plot_pos_y + self._butt_plot_height + 10
        settings_pos_y = MEP_plot_pos_y + self._butt_plot_height + 10

        aver_pos_x = int(0.65* self.w)

        # TEP plot
        self.figure_TEP.move(0, TEP_plot_pos_y)
        self.checkbox_average_teps.move(aver_pos_x, TEP_plot_pos_y)
 
        # MEP plot
        self.figure_MEP.move(0, MEP_plot_pos_y)
        self.checkbox_average_meps.move(aver_pos_x, MEP_plot_pos_y)

        # Settings
        self._setup_settings_frame()
        # self._button_interactive_plot.move(20, butt_pos - 20)
        self._frame_settings.move(0, settings_pos_y)

    def _setup_settings_frame(self):
        self._max_amp = create_hbox([QLabel("Макс:", self), self._spinbox_max_amp_tep, QLabel(MICROVOLT, self)])
        self._time_range = create_hbox([QLabel("от:   ", self), self._spinbox_min_time,  
                                        QLabel("до:   ", self), self._spinbox_max_time, 
                                        QLabel("мс", self)])
        layout_settings = QVBoxLayout(self._frame_settings)
        for layout in [self._max_amp,self._time_range]:
            layout_settings.addLayout(layout)
        # layout_settings.addWidget(self._button_apply)
        

    # --- Сигналы ---
    def _setup_connections(self):
        for spin_box in [self._spinbox_min_time, self._spinbox_max_time, self._spinbox_max_amp_tep]:
            spin_box.valueChanged.connect(self._update_scale)
        
        self._button_interactive_plot.clicked.connect(self._on_interactive_plot_button_clicked)
    
    # --- Логика ---
    def _update_scale(self):
        xmax = self._spinbox_max_time.value()
        xmin = self._spinbox_min_time.value()
        ymax = self._spinbox_max_amp_tep.value()

        self.figure_TEP.update_axes(xmax, xmin, ymax)
        self.figure_MEP.update_axes(xmax, xmin, self.settings.butts_plot.MEP.amp, which='MEPs')

        

    def _on_interactive_plot_button_clicked(self):
        if False:
            print('skip')
    #     self.inter_plot = PlotWindow()
        
    #     self.inter_plot.show()

    # --- Финализация ---
    def _post_init(self):
        self._update_scale()
        QTimer.singleShot(0, self._update_inner_sizes)
        QTimer.singleShot(50, self._update_inner_sizes)

    # --- События ---
    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._update_inner_sizes)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_inner_sizes()

    def _update_inner_sizes(self):
        if not hasattr(self, "figure_TEP"):
            return

        self.w = max(1, self.width())
        self.h = max(1, self.height())
        self._butt_plot_height = max(1, int((1-self._ratio)*self.h//2))

        self._resize_butt_plot(self.figure_TEP, self.w, self._butt_plot_height)
        self._resize_butt_plot(self.figure_MEP, self.w, self._butt_plot_height)

        if self.settings.topoplot.draw:
            self._place_topoplots()

        self._place_butt_plots()
        self._update_scale()

    def _resize_butt_plot(self, figure, width, height):
        figure.resize(width, height)
        figure.fig.set_size_inches(
            width / figure.fig.dpi,
            height / figure.fig.dpi,
            forward=True
        )

    def _place_topoplots(self):
        n = self.settings.topoplot.n_plots
        w_available = 0.8 * self.w
        w_topo = max(1, int(w_available // n))
        d_width = (1-0.8-0.1) * self.w / n
        left = int(0.1 * self.w)

        for i, topoplot in enumerate(self.figure_topo):
            topoplot.resize(w_topo, w_topo)
            left_new = int(left+(topoplot.width() + d_width)*i)
            topoplot.move(left_new, left)
            self.spinbox_ts[i].move(left_new + topoplot.width()//2-25, left-30)

    def _place_butt_plots(self):
        TEP_plot_pos_y = int((1-self._ratio)*self.h) - self.figure_TEP.height()
        MEP_plot_pos_y = TEP_plot_pos_y + self._butt_plot_height + 10
        settings_pos_y = MEP_plot_pos_y + self._butt_plot_height + 10
        aver_pos_x = int(0.65* self.w)

        self.figure_TEP.move(0, TEP_plot_pos_y)
        self.checkbox_average_teps.move(aver_pos_x, TEP_plot_pos_y)
        self.figure_MEP.move(0, MEP_plot_pos_y)
        self.checkbox_average_meps.move(aver_pos_x, MEP_plot_pos_y)
        self._frame_settings.move(0, settings_pos_y)
