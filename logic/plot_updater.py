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
        self._sync_plot_timebase(processor)
        if getattr(processor, "use_eeg", True):
            self.update_topoteps(processor)
            self.update_avg_teps(processor) # ????

        self.update_avg_meps(processor)

        self.update_meps(processor)
        
        if self.do_mep_deeper_look:
            self.update_mep_deeper_look(processor)
    
    def update_topoteps(self, processor):
        self._sync_plot_timebase(processor)
        if not getattr(processor, "use_eeg", True):
            return
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
        self._sync_plot_timebase(processor)
        if not getattr(processor, "use_eeg", True):
            return
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
        self._sync_plot_timebase(processor)
        if len(processor._epochs) == 0:
            return

        if not self._show_specific_epoch:
            epoch = processor._epochs[-1]
            if hasattr(self.meps_panel, "set_channel_count"):
                self.meps_panel.set_channel_count(np.asarray(epoch).shape[0])
            emg = self._mep_from_epoch(processor, epoch, self.settings.single_meps)
            emg2plot = processor.cut_mep_epoch(emg, self.settings.single_meps.xmin_ms, self.settings.single_meps.xmax_ms)

            self.meps_panel.figure.update_emg(emg2plot)

    def update_avg_meps(self, processor):
        self._sync_plot_timebase(processor)
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
        epoch = processor._epochs[-1]
        self.mep_deeper_look_window.set_channel_count(np.asarray(epoch).shape[0])
        emg2plot = self._mep_deeper_look_epoch(processor, epoch, settings)

        self.mep_deeper_look_window.update_emg(emg2plot)

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
        ui.rebuild_from_settings(reset_history=True)

        n_plots = max(1, int(getattr(settings, "n_plots", 1)))
        for epoch in processor._epochs[-n_plots:]:
            ui.set_channel_count(np.asarray(epoch).shape[0])
            emg2plot = self._mep_deeper_look_epoch(processor, epoch, settings)
            ui.update_emg(emg2plot)

    def _mep_from_epoch(self, processor, epoch, settings=None):
        pair = getattr(settings, "channel_pair", None)
        if pair and len(pair) >= 2:
            return self._mep_from_epoch_channels(processor, epoch, int(pair[0]) - 1, int(pair[1]) - 1, settings)
        return self._mep_from_epoch_channels(processor, epoch, -2, -1, settings)

    def _mep_deeper_look_epoch(self, processor, epoch, settings):
        if not getattr(settings, "feet_mode", False):
            emg = self._mep_from_epoch(processor, epoch, settings)
            return processor.cut_mep_epoch(emg, settings.xmin_ms, settings.xmax_ms)

        rows = []
        for ch_a, ch_b in self.mep_deeper_look_window.get_feet_channel_pairs():
            emg = self._mep_from_epoch_channels(processor, epoch, ch_a - 1, ch_b - 1, settings)
            rows.append(processor.cut_mep_epoch(emg, settings.xmin_ms, settings.xmax_ms))
        return rows

    def _mep_from_epoch_channels(self, processor, epoch, ch_a, ch_b, settings=None):
        epoch = np.asarray(epoch)
        if epoch.ndim < 2:
            return self._empty_mep_signal(processor, epoch)

        n_channels = int(epoch.shape[0])
        if n_channels < 2:
            return self._empty_mep_signal(processor, epoch)

        ch_a = self._resolve_channel_index(ch_a, n_channels)
        ch_b = self._resolve_channel_index(ch_b, n_channels)
        if ch_a is None or ch_b is None:
            return self._empty_mep_signal(processor, epoch)

        emg = processor._baseline(epoch[[ch_a, ch_b], :] * 1E3)  # вычесть бейзлайн и перевести в мВ
        emg = np.diff(emg, axis=0).flatten()                     # посчитать разницу каналов
        return self._remove_mep_slow_trend(processor, emg, settings)

    @staticmethod
    def _resolve_channel_index(index, n_channels):
        index = int(index)
        if index < 0:
            index = n_channels + index
        if index < 0 or index >= n_channels:
            return None
        return index

    @staticmethod
    def _empty_mep_signal(processor, epoch):
        epoch = np.asarray(epoch)
        n_samples = int(epoch.shape[-1]) if epoch.ndim > 0 else 0
        if n_samples <= 0:
            n_samples = int(getattr(processor, "_n_samples", 0) or 0)
        return np.full(max(0, n_samples), np.nan, dtype=float)

    def _sync_plot_timebase(self, processor):
        n_samples = int(getattr(processor, "_n_samples", 0) or 0)
        if n_samples <= 0:
            return

        speed = getattr(getattr(processor, "settings", None), "speed", None)
        fs = float(getattr(speed, "Fs", 0) or 0)
        x_shift = -int(getattr(processor, "_time_shift", 0) or 0)
        signature = (fs, x_shift, n_samples)

        topo_signature = getattr(self.topo_panel, "_timebase_signature", None)
        if topo_signature != signature:
            if fs > 0:
                self.topo_panel.ms_to_sample = lambda x, _fs=fs: int(x / 1000 * _fs)
            self.topo_panel.speed_settings = speed
            self.topo_panel.n_samples = n_samples
            self.topo_panel.x_shift = -x_shift
            self.topo_panel.figure.set_x_shift(x_shift, n_samples)
            self.topo_panel._update_scale()
            self.topo_panel._timebase_signature = signature

        overview_settings = self.overview_panel.settings.butts_plot
        for figure, signal in (
            (self.overview_panel.figure_TEP, "TEP"),
            (self.overview_panel.figure_MEP, "MEP"),
        ):
            figure_signature = getattr(figure, "_timebase_signature", None)
            if figure_signature == signature:
                continue
            if fs > 0:
                figure._ms_to_sample = lambda x, _fs=fs: int(x / 1000 * _fs)
            figure.set_x_shift(x_shift, n_samples, signal=signal)
            figure.update_axes(
                xmax_ms=overview_settings.xmax_ms,
                xmin_ms=overview_settings.xmin_ms,
                amp=figure.settings.amp,
                which=f"{signal}s",
            )
            figure._timebase_signature = signature

        mep_figure = getattr(self.meps_panel, "figure", None)
        if mep_figure is not None and fs > 0:
            mep_figure.set_sampling_rate(fs)

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

    def clear_eeg_plots(self):
        self.topo_panel.figure.refresh_plot()
        self.overview_panel.figure_TEP.refresh_plot(which='TEPs')
    
    def plot_epoch(self, n_epoch, processor):
        if n_epoch < 1 or n_epoch > len(processor._epochs):
            return

        if getattr(processor, "use_eeg", True):
            TEPs2plot = processor.apply_transform(processor._epochs[n_epoch-1][:-2, :] * 1e6)
            self.topo_panel.figure.update_data(TEPs2plot)
            self.overview_panel.figure_TEP.update_TEPs(TEPs2plot)

        emg = processor._baseline(processor._epochs[n_epoch-1][-2:, :] * 1E3)  # вычесть бейзлайн и перевести в мВ
        emg = np.diff(emg, axis=0).flatten()                            # посчитать разницу каналов
        self.overview_panel.figure_MEP.update_MEPs(emg, spread=None)
    
    def set_show_epoch_mode(self, mode):
        self._show_specific_epoch = mode
