class PlotUpdater:
    def __init__(self, topo_panel, overview_panel, meps_panel, params):
        self.topo_panel = topo_panel
        self.overview_panel = overview_panel
        self.meps_panel = meps_panel
        self.params = params

    def update_plots(self, processor, update_emg=True):
        if processor.average_data:
            TEPs2plot = processor.calculate_avg_TEP()
        else:
            TEPs2plot = processor._transform(processor._epochs[-1][:-2, :] * 1e6)

        self.topo_panel.figure.update_data(TEPs2plot)
        self.overview_panel.figure_TEP.update_TEPs(TEPs2plot)

        if update_emg:
            emg = processor._baseline(processor._epochs[-1][-2:, :] * 1e3)
            emg = np.diff(emg, axis=0).flatten()
            self.meps_panel.figure.update_emg(emg) 