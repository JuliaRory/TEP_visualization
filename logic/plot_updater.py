import numpy as np

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

    def update_plots(self, processor):
        self.update_teps(processor)
        self.update_meps(processor)
        if self.do_mep_deeper_look:
            self.update_mep_deeper_look(processor)
    
    def update_teps(self, processor):
        """TEPs"""
        if processor.average_data:
            TEPs2plot = processor.calculate_avg_TEP() # взять все сохранённые эпохи и вернуть усреднённые ТЕР
        else:
            TEPs2plot = processor.apply_transform(processor._epochs[-1][:-2, :] * 1e6)    # взять последнюю преобразованную эпоху

        self.topo_panel.figure.update_data(TEPs2plot)
        self.overview_panel.figure_TEP.update_TEPs(TEPs2plot)


        # if self.params["TEP_suppl_plot"]["topoplot"]["draw"]:
        #     timestamps = self.params["TEP_suppl_plot"]["timestamps_ms"]
        #     for i, t_ms in enumerate(timestamps):
        #         t = self._ms_to_sample(t_ms)
        #         self._overview_panel.figure_topo[i].plot_topomap(TEPs2plot[:, t])
    
    def update_meps(self, processor):
        """MEPs"""
        emg = processor._baseline(processor._epochs[-1][-2:, :] * 1E3)  # вычесть бейзлайн и перевести в мВ
        emg = np.diff(emg, axis=0).flatten()                            # посчитать разницу каналов
        emg2plot = processor.cut_mep_epoch(emg, self.settings.single_meps.xmin_ms, self.settings.single_meps.xmax_ms)

        self.meps_panel.figure.update_emg(emg2plot)


        # emg_epochs = np.array(self._epochs)[:, -2:] * 10**3
        # emg = np.mean(np.array([np.diff(self._baseline(emg), axis=0).flatten() for emg in emg_epochs]), axis=0)
        # self._overview_panel.figure_MEP.update_MEPs(emg)

        # emg = processor._baseline(processor._epochs[-1][-2:, :])
        # emg = np.diff(emg, axis=0).flatten()
        # self.meps_panel.figure.update_emg(emg) 

        # emg_epochs = np.array(self._epochs)[:, -2:] 
        # emg = np.mean(np.array([np.diff(self._baseline(emg), axis=0).flatten() for emg in emg_epochs]), axis=0)
        # self._overview_panel.figure_MEP.update_MEPs(emg)

    def add_mep_deeper_look(self, ui):
        print(ui)
        self.mep_deeper_look_window = ui
        self.do_mep_deeper_look = True

    def update_mep_deeper_look(self, processor):
        """MEPs in DeeperLook Window"""
        emg = processor._baseline(processor._epochs[-1][-2:, :] * 1E3)  # вычесть бейзлайн и перевести в мВ
        emg = np.diff(emg, axis=0).flatten()                            # посчитать разницу каналов
        emg2plot = processor.cut_mep_epoch(emg, self.settings.single_meps.xmin_ms, self.settings.single_meps.xmax_ms)

        # self.mep_deeper_look_window.update_emg(emg2plot)
        self.mep_deeper_look_window.figure_1.update_emg(emg2plot)