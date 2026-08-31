import numpy as np

from scipy.ndimage import median_filter
from logic.data_processor import LABEL_ALL


LABEL_COLORS = [
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#ff7f0e",
    "#9467bd",
    "#8c564b",
    "#17becf",
    "#e377c2",
]

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
        if self._use_label_overlay(processor):
            data_by_label, colors = self._labelled_tep_data(processor, averaged=processor.average_data)
            self.topo_panel.figure.update_labelled_data(data_by_label, colors)
            return
        eeg_epoch = processor.get_eeg_epoch_by_index(-1, filter_by_label=True)
        if eeg_epoch is None:
            return

        if not self._show_specific_epoch:
            """TEPs"""
            if processor.average_data:
                TEPs2plot = processor.calculate_avg_TEP() # взять все сохранённые эпохи и вернуть усреднённые ТЕР
            else:
                TEPs2plot = processor.transform_eeg_epoch(eeg_epoch)    # взять последнюю преобразованную эпоху
            
            self.topo_panel.figure.update_data(TEPs2plot)

    def update_avg_teps(self, processor):
        self._sync_plot_timebase(processor)
        if not getattr(processor, "use_eeg", True):
            return
        if self._use_label_overlay(processor):
            data_by_label, colors = self._labelled_tep_data(
                processor,
                averaged=self.settings.overview_panel.butts_plot.TEP.do_averaging,
            )
            self.overview_panel.figure_TEP.update_labelled_TEPs(data_by_label, colors)
            return
        eeg_epoch = processor.get_eeg_epoch_by_index(-1, filter_by_label=True)
        if eeg_epoch is None:
            return

        if not self._show_specific_epoch:
            if self.settings.overview_panel.butts_plot.TEP.do_averaging:
                processor._ensure_average_functions(which="TEPs")
                TEPs2plot = processor.calculate_avg_TEP() # взять все сохранённые эпохи и вернуть усреднённые ТЕР
            else:
                TEPs2plot = processor.transform_eeg_epoch(eeg_epoch)    # взять последнюю преобразованную эпоху

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
        if self._use_label_overlay(processor):
            entries, colors = self._labelled_mep_history(processor, self.settings.single_meps)
            self.meps_panel.figure.update_emg_history(entries, colors)
            return
        epoch = processor.get_other_epoch(-1, filter_by_label=True)
        if epoch is None:
            return

        if not self._show_specific_epoch:
            if hasattr(self.meps_panel, "set_channel_count"):
                self.meps_panel.set_channel_count(np.asarray(epoch).shape[0])
            emg = self._mep_from_epoch(processor, epoch, self.settings.single_meps)
            emg2plot = processor.cut_mep_epoch(emg, self.settings.single_meps.xmin_ms, self.settings.single_meps.xmax_ms)

            self.meps_panel.figure.update_emg(emg2plot)

    def update_avg_meps(self, processor):
        self._sync_plot_timebase(processor)
        if self._use_label_overlay(processor):
            data_by_label, colors = self._labelled_mep_overview_data(
                processor,
                averaged=self.settings.overview_panel.butts_plot.MEP.do_averaging,
            )
            self.overview_panel.figure_MEP.update_labelled_MEPs(data_by_label, colors)
            return
        if processor.get_other_epoch(-1, filter_by_label=True) is None:
            return

        if not self._show_specific_epoch:
            if self.settings.overview_panel.butts_plot.MEP.do_averaging:
                emg_epochs = self._mep_epochs(processor, filter_by_label=True)
                if emg_epochs.size == 0:
                    return
                emg_epochs = processor._mep_average_window(emg_epochs)
                ddof = 1 if emg_epochs.shape[0] > 1 else 0
                emg = np.nanmean(emg_epochs, axis=0)
                emg_std = np.nanstd(emg_epochs, axis=0, ddof=ddof)

            else:
                emg = self._mep_from_epoch(
                    processor,
                    processor.get_other_epoch(-1, filter_by_label=True),
                    self.settings.single_meps,
                )
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
        if processor.get_other_epoch(-1, filter_by_label=True) is None:
            return
        if not getattr(self, "mep_deeper_look_window", None):
            return
        if not self.mep_deeper_look_window.isVisible():
            return

        settings = self.mep_deeper_look_window.settings
        epoch = processor.get_other_epoch(-1, filter_by_label=True)
        self.mep_deeper_look_window.set_channel_count(np.asarray(epoch).shape[0])
        emg2plot = self._mep_deeper_look_epoch(processor, epoch, settings)

        self.mep_deeper_look_window.update_emg(emg2plot)

    def _refresh_mep_deeper_look(self):
        if self._latest_processor is not None:
            self._redraw_mep_deeper_look_history(self._latest_processor)

    def _redraw_mep_deeper_look_history(self, processor):
        if processor.get_other_epoch(-1, filter_by_label=True) is None:
            return
        if not getattr(self, "mep_deeper_look_window", None):
            return
        if not self.mep_deeper_look_window.isVisible():
            return

        ui = self.mep_deeper_look_window
        settings = ui.settings
        ui.rebuild_from_settings(reset_history=True)

        n_plots = max(1, int(getattr(settings, "n_plots", 1)))
        for epoch in processor._filtered_other_epochs()[-n_plots:]:
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

        emg = np.diff(epoch[[ch_a, ch_b], :] * 1E3, axis=0).flatten()
        return self._remove_mep_slow_trend(processor, emg, settings)

    def _use_label_overlay(self, processor):
        filters = list(getattr(processor, "epoch_label_filters", [LABEL_ALL]))
        return LABEL_ALL not in filters and len(filters) > 1

    def _label_colors(self, labels):
        return {
            label: LABEL_COLORS[i % len(LABEL_COLORS)]
            for i, label in enumerate(labels)
        }

    def _labelled_tep_data(self, processor, averaged=True):
        labels = list(getattr(processor, "epoch_label_filters", [LABEL_ALL]))
        colors = self._label_colors(labels)
        data_by_label = []
        for label in labels:
            epochs = processor.get_eeg_epochs(filter_by_label=True, labels=[label])
            if epochs.size == 0:
                continue
            data = np.nanmean(epochs, axis=0) if averaged or epochs.shape[0] > 1 else epochs[-1]
            data_by_label.append((label, data))
        return data_by_label, colors

    def _labelled_mep_overview_data(self, processor, averaged=True):
        labels = list(getattr(processor, "epoch_label_filters", [LABEL_ALL]))
        colors = self._label_colors(labels)
        data_by_label = []
        for label in labels:
            epochs = self._mep_epochs(processor, filter_by_label=True, labels=[label])
            if epochs.size == 0:
                continue
            data = np.nanmean(processor._mep_average_window(epochs), axis=0) if averaged else epochs[-1]
            data_by_label.append((label, data))
        return data_by_label, colors

    def _labelled_mep_history(self, processor, settings):
        labels = list(getattr(processor, "epoch_label_filters", [LABEL_ALL]))
        selected = set(labels)
        colors = self._label_colors(labels)
        entries = []
        for label, epoch in zip(getattr(processor, "epoch_labels", []), getattr(processor, "_other_epochs", [])):
            if label not in selected:
                continue
            if int(np.asarray(epoch).shape[-1]) != int(getattr(processor, "_other_n_samples", 0) or 0):
                continue
            emg = self._mep_from_epoch(processor, epoch, settings)
            emg = processor.cut_mep_epoch(emg, settings.xmin_ms, settings.xmax_ms)
            entries.append((label, emg))
        return entries, colors

    def _mep_epochs(self, processor, filter_by_label=True, labels=None):
        epochs = processor._current_length_other_epochs(filter_by_label=filter_by_label, labels=labels)
        if not epochs:
            return np.empty((0, int(getattr(processor, "_other_n_samples", 0) or 0)))
        return np.stack([
            self._mep_from_epoch(processor, epoch, self.settings.single_meps)
            for epoch in epochs
        ], axis=0)

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
            n_samples = int(getattr(processor, "_other_n_samples", 0) or 0)
        return np.full(max(0, n_samples), np.nan, dtype=float)

    def _sync_plot_timebase(self, processor):
        n_samples = int(getattr(processor, "_n_samples", 0) or 0)
        fs = float(getattr(processor, "_sampling_rate_Hz", 0) or 0)
        x_shift = -int(getattr(processor, "_time_shift", 0) or 0)
        tep_signature = (fs, x_shift, n_samples)

        topo_signature = getattr(self.topo_panel, "_timebase_signature", None)
        if n_samples > 0 and topo_signature != tep_signature:
            if fs > 0:
                self.topo_panel.ms_to_sample = lambda x, _fs=fs: int(x / 1000 * _fs)
            self.topo_panel.n_samples = n_samples
            self.topo_panel.x_shift = -x_shift
            self.topo_panel.figure.set_x_shift(x_shift, n_samples)
            self.topo_panel._update_scale()
            self.topo_panel._timebase_signature = tep_signature

        overview_settings = self.overview_panel.settings.butts_plot
        figure = self.overview_panel.figure_TEP
        figure_signature = getattr(figure, "_timebase_signature", None)
        if n_samples > 0 and figure_signature != tep_signature:
            if fs > 0:
                figure._ms_to_sample = lambda x, _fs=fs: int(x / 1000 * _fs)
            figure.set_x_shift(x_shift, n_samples, signal="TEP")
            figure.update_axes(
                xmax_ms=overview_settings.xmax_ms,
                xmin_ms=overview_settings.xmin_ms,
                amp=figure.settings.amp,
                which="TEPs",
            )
            figure._timebase_signature = tep_signature

        mep_samples = int(getattr(processor, "_other_n_samples", 0) or 0)
        mep_fs = float(getattr(processor, "mep_sampling_rate_Hz", 0) or 0)
        mep_x_shift = -int(getattr(processor, "_other_time_shift", 0) or 0)
        mep_signature = (mep_fs, mep_x_shift, mep_samples)

        figure = self.overview_panel.figure_MEP
        figure_signature = getattr(figure, "_timebase_signature", None)
        if mep_samples > 0 and figure_signature != mep_signature:
            if mep_fs > 0:
                figure._ms_to_sample = lambda x, _fs=mep_fs: int(x / 1000 * _fs)
            figure.set_x_shift(mep_x_shift, mep_samples, signal="MEP")
            figure.update_axes(
                xmax_ms=overview_settings.xmax_ms,
                xmin_ms=overview_settings.xmin_ms,
                amp=figure.settings.amp,
                which="MEPs",
            )
            figure._timebase_signature = mep_signature

        mep_figure = getattr(self.meps_panel, "figure", None)
        if mep_fs > 0 and hasattr(self.meps_panel, "Fs"):
            self.meps_panel.Fs = mep_fs
        if mep_figure is not None and mep_fs > 0:
            mep_figure.set_sampling_rate(mep_fs)

        mep_deeper = getattr(self, "mep_deeper_look_window", None)
        if mep_deeper is not None and mep_fs > 0 and hasattr(mep_deeper, "set_sampling_rate"):
            mep_deeper.set_sampling_rate(mep_fs)

    def _remove_mep_slow_trend(self, processor, emg, settings):
        if settings is None or not getattr(settings, "remove_slow_trend", True):
            return emg

        emg = np.asarray(emg, dtype=float)
        if emg.size < 3:
            return emg

        fs = float(
            getattr(
                processor,
                "mep_sampling_rate_Hz",
                getattr(processor, "_other_sampling_rate_Hz", 0),
            )
            or 0
        )
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
        if n_epoch < 1 or n_epoch > processor._n_epoch:
            return

        eeg_epoch = processor.get_eeg_epoch_by_index(n_epoch - 1)
        if getattr(processor, "use_eeg", True) and eeg_epoch is not None:
            TEPs2plot = processor.transform_eeg_epoch(eeg_epoch)
            self.topo_panel.figure.update_data(TEPs2plot)
            self.overview_panel.figure_TEP.update_TEPs(TEPs2plot)

        other_epoch = processor.get_other_epoch(n_epoch - 1)
        if other_epoch is None:
            return
        emg = self._mep_from_epoch(processor, other_epoch, self.settings.single_meps)
        self.overview_panel.figure_MEP.update_MEPs(emg, spread=None)
    
    def set_show_epoch_mode(self, mode):
        self._show_specific_epoch = mode
