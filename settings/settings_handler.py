

class SettingsHandler:
    """
    «Связующее звено» между UI и логикой:
    -- Слушает изменения в UI.
    -- Обновляет соответствующие поля в Settings.
    -- Вызывает методы DataProcessor, PlotUpdater или других классов, чтобы применить новые настройки

    Args:
        settings(Settings): 
        data_processor(DataProcessor):
        plot_updater(PlotUpdater):
        ui(QWidget):

    """
    def __init__(self, settings, data_processor, plot_updater, ui):
        self.data_processor = data_processor
        self.settings = settings
        self.plot_updater = plot_updater
        self.ui = ui

    def update_averaging(self):
        self.data_processor.average_data = self.ui.check_box_averaging.isChecked()
        self.data_processor.create_full_transform()
        self.plot_updater.update_plots(self.data_processor)

    def update_baseline(self):
        apply_baseline = self.ui.check_box_baseline.isChecked()
        if apply_baseline:
            baseline_from = self.ui.spin_box_baseline_from.value()
            baseline_to = self.ui.spin_box_baseline_to.value()
            # пример расчета baseline
            self.processor._baseline = lambda x: x - x.mean(axis=1, keepdims=True)
        else:
            self.processor._baseline = lambda x: x
        self.data_processor.create_full_transform()
        self.plot_updater.update_plots(self.processor)

    def load_from_json(self):
        print('to be done')
    
    def save_to_json(self):
        # сделать сохранение настроек по закрытию программы и потом открытие последней версии настроек 
        # плюс сброс до дефолтных настроек
        print('to be done')