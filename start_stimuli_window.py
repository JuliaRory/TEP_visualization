import sys

from PyQt5.QtWidgets import QApplication

from ui.stimuli_window import StimuliCreation

if __name__ == '__main__':
    app = QApplication(sys.argv) 
    main = StimuliCreation()         # открыть Qt-окно приложения
    main.show()

    sys.exit(app.exec_())
