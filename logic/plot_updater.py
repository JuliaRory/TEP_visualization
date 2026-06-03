import numpy as np

from scipy.ndimage import median_filter

class PlotUpdater:
    def __init__(self, topo_panel, overview_panel, meps_panel, settings):
        """
        settings: settings_plot
        """
        self.topo_panel = topo_panel
        self.overview_panel = overview_panel
        self.meps_panel = meps_panel
        self.settings = settings

        self.do_mep_deeper_look = False
        self._show_specific_epoch = False
        self._latest_processor = None

    def update_plots(self, processor):
        self._latest_processor = processor
        self.update_topoteps(processor)

        self.update_avg_teps(processor) # ????
        self.update_avg_meps(processor)

        self.update_meps(processor)
        
        if self.do_mep_deeper_look:
            self.update_mep_deeper_look(processor)
    
    def update_topoteps(self, processor):
        if len(processor._epochs) == 0:
            return

        if not self._show_specific_epoch:
            """TEPs"""
            if processor.average_data:
                TEPs2plot = processor.calculate_avg_TEP() # взять все сохранённые эпохи и вернуть усреднённые ТЕР
            else:
                TEPs2plot = processor.apply_transform(processor._epochs[-1][:-2, :] * 1e6)    # взять последнюю преобразованную эпоху
                # TEPs2plot = processor.apply_transform(processor._epochs[-1][:-1, :])    # взять последнюю преобразованную эпоху
            
            self.topo_panel.figure.update_data(TEPs2plot)

    def update_avg_teps(self, processor):
        if len(processor._epochs) == 0:
            return

        if not self._show_specific_epoch:
            if self.settings.overview_panel.butts_plot.TEP.do_averaging:
                processor._ensure_average_functions(which="TEPs")
                TEPs2plot = processor.calculate_avg_TEP() # взять все сохранённые эпохи и вернуть усреднённые ТЕР
            else:
                TEPs2plot = processor.apply_transform(processor._epochs[-1][:-2, :] * 1e6)    # взять последнюю преобразованную эпоху
                # TEPs2plot = processor.apply_transform(processor._epochs[-1][:-1, :])    # взять последнюю преобразованную эпоху

            self.overview_panel.figure_TEP.update_TEPs(TEPs2plot)

            # if self.params["TEP_suppl_plot"]["topoplot"]["draw"]:
            #     timestamps = self.params["TEP_suppl_plot"]["timestamps_ms"]
            #     for i, t_ms in enumerate(timestamps):
            #         t = self._ms_to_sample(t_ms)
            #         self._overview_panel.figure_topo[i].plot_topomap(TEPs2plot[:, t])
    
    def update_meps(self, processor):
        """MEPs"""
        self._latest_processor = processor
        if len(processor._epochs) == 0:
            return

        if not self._show_specific_epoch:
            emg = self._mep_from_epoch(processor, processor._epochs[-1], self.settings.single_meps)
            emg2plot = processor.cut_mep_epoch(emg, self.settings.single_meps.xmin_ms, self.settings.single_meps.xmax_ms)

            self.meps_panel.figure.update_emg(emg2plot)

    def update_avg_meps(self, processor):
        if len(processor._epochs) == 0:
            return

        if not self._show_specific_epoch:
            if self.settings.overview_panel.butts_plot.MEP.do_averaging:
                if not processor.average_mep_data:
                    processor.update_avg_mep(True)
                emg, emg_std = processor.calculate_avg_MEP_stats()

            else:
                emg = processor._baseline(processor._epochs[-1][-2:, :] * 1E3)  # вычесть бейзлайн и перевести в мВ
                emg = np.diff(emg, axis=0).flatten()                            # посчитать разницу каналов
                emg_std = None
            
            #emg2plot = processor.cut_mep_epoch(emg, self.settings.single_meps.xmin_ms, self.settings.single_meps.xmax_ms)
            self.overview_panel.figure_MEP.update_MEPs(emg, spread=emg_std)

    def add_mep_deeper_look(self, ui):
        self.mep_deeper_look_window = ui
        self.do_mep_deeper_look = True
        if hasattr(ui, "settingsChanged"):
            ui.settingsChanged.connect(self._refresh_mep_deeper_look)
        self._refresh_mep_deeper_look()

    def update_mep_deeper_look(self, processor):
        """MEPs in DeeperLook Window"""
        self._latest_processor = processor
        if len(processor._epochs) == 0:
            return
        if not getattr(self, "mep_deeper_look_window", None):
            return
        if not self.mep_deeper_look_window.isVisible():
            return

        settings = self.mep_deeper_look_window.settings
        emg = self._mep_from_epoch(processor, processor._epochs[-1], settings)
        emg2plot = processor.cut_mep_epoch(emg, settings.xmin_ms, settings.xmax_ms)

        # self.mep_deeper_look_window.update_emg(emg2plot)
        self.mep_deeper_look_window.figure.update_emg(emg2plot)

    def _refresh_mep_deeper_look(self):
        if self._latest_processor is not None:
            self._redraw_mep_deeper_look_history(self._latest_processor)

    def _redraw_mep_deeper_look_history(self, processor):
        if len(processor._epochs) == 0:
            return
        if not getattr(self, "mep_deeper_look_window", None):
            return
        if not self.mep_deeper_look_window.isVisible():
            return

        ui = self.mep_deeper_look_window
        settings = ui.settings
        ui.figure.rebuild_from_settings(reset_history=True)

        n_plots = max(1, int(getattr(settings, "n_plots", 1)))
        for epoch in processor._epochs[-n_plots:]:
            emg = self._mep_from_epoch(processor, epoch, settings)
            emg2plot = processor.cut_mep_epoch(emg, settings.xmin_ms, settings.xmax_ms)
            ui.figure.update_emg(emg2plot)

    def _mep_from_epoch(self, processor, epoch, settings=None):
        emg = processor._baseline(epoch[-2:, :] * 1E3)  # вычесть бейзлайн и перевести в мВ
        emg = np.diff(emg, axis=0).flatten()           # посчитать разницу каналов
        return self._remove_mep_slow_trend(processor, emg, settings)

    def _remove_mep_slow_trend(self, processor, emg, settings):
        if settings is None or not getattr(settings, "remove_slow_trend", True):
            return emg

        emg = np.asarray(emg, dtype=float)
        if emg.size < 3:
            return emg

        speed = getattr(getattr(processor, "settings", None), "speed", None)
        fs = float(getattr(speed, "Fs", 0) or 0)
        if fs <= 0:
            return emg

        window_ms = max(float(getattr(settings, "trend_window_ms", 100.0)), 1000.0 / fs * 3)
        kernel = max(3, int(round(window_ms / 1000.0 * fs)))
        if kernel % 2 == 0:
            kernel += 1
        if kernel >= emg.size:
            kernel = emg.size - 1 if emg.size % 2 == 0 else emg.size
        if kernel < 3:
            return emg

        trend = median_filter(emg, size=kernel, mode="nearest")
        return emg - trend
    
    def clear_plots(self):
        self.topo_panel.figure.refresh_plot()
        self.overview_panel.figure_TEP.refresh_plot(which='TEPs')
        self.overview_panel.figure_MEP.refresh_plot(which='MEPs')
        self.meps_panel.figure.refresh_plot()
    
    def plot_epoch(self, n_epoch, processor):
        if n_epoch < 1 or n_epoch > len(processor._epochs):
            return

        TEPs2plot = processor.apply_transform(processor._epochs[n_epoch-1][:-2, :] * 1e6)
        self.topo_panel.figure.update_data(TEPs2plot)
        self.overview_panel.figure_TEP.update_TEPs(TEPs2plot)

        emg = processor._baseline(processor._epochs[n_epoch-1][-2:, :] * 1E3)  # вычесть бейзлайн и перевести в мВ
        emg = np.diff(emg, axis=0).flatten()                            # посчитать разницу каналов
        self.overview_panel.figure_MEP.update_MEPs(emg, spread=None)
    
    def set_show_epoch_mode(self, mode):
        self._show_specific_epoch = mode
