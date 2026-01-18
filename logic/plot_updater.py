import numpy as np

class PlotUpdater:
    def __init__(self, topo_panel, overview_panel, meps_panel, params):
        self.topo_panel = topo_panel
        self.overview_panel = overview_panel
        self.meps_panel = meps_panel
        self.params = params

    def update_plots(self, processor, update_emg=False):
        """TEPs"""
        if processor.average_data:
            TEPs2plot = processor.calculate_avg_TEP() # взять все сохранённые эпохи и вернуть усреднённые ТЕР
        else:
            TEPs2plot = processor.apply_transform(processor._epochs[-1][:-1, :])    # взять последнюю преобразованную эпоху

        self.topo_panel.figure.update_data(TEPs2plot)
        # self.overview_panel.figure_TEP.update_TEPs(TEPs2plot)


        # if self.params["TEP_suppl_plot"]["topoplot"]["draw"]:
        #     timestamps = self.params["TEP_suppl_plot"]["timestamps_ms"]
        #     for i, t_ms in enumerate(timestamps):
        #         t = self._ms_to_sample(t_ms)
        #         self._overview_panel.figure_topo[i].plot_topomap(TEPs2plot[:, t])
        
        # """MEPs"""
        # if update_emg:
        #     emg = self._baseline(self._epochs[-1][-2:, :] * 1E3)  # вычесть бейзлайн и перевести в мВ
        #     emg = np.diff(emg, axis=0).flatten()                # посчитать разницу каналов

        #     x_min, x_max = self._ms_to_sample(self.params["MEP_plot"]["xmin_ms"]), self._ms_to_sample(self.params["MEP_plot"]["xmax_ms"])
        #     emg2plot = emg[self._time_shift+x_min:self._time_shift+x_max] 

        #     self._meps_panel.figure.update_emg(emg2plot)

        #     emg_epochs = np.array(self._epochs)[:, -2:] * 10**3
        #     emg = np.mean(np.array([np.diff(self._baseline(emg), axis=0).flatten() for emg in emg_epochs]), axis=0)
        #     self._overview_panel.figure_MEP.update_MEPs(emg)

        # if update_emg:
        #     emg = processor._baseline(processor._epochs[-1][-2:, :] * 1e3)
        #     emg = np.diff(emg, axis=0).flatten()
        #     self.meps_panel.figure.update_emg(emg) 