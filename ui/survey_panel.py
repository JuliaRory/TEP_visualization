import os

from PyQt5.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout
from PyQt5.QtCore import Qt

from ui.survey import DEFAULT_OUTPUT_DIR, QuestionnaireWindow
from utils.ui_helpers import create_button


class SurveyPanel(QFrame):
    """Panel with buttons for opening day-specific questionnaires."""

    def __init__(self, participant_id_getter=None, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.participant_id_getter = participant_id_getter
        self._survey_windows = {}
        self._survey_configs = [
            (1, os.path.join("resources", "survey_day1.json")),
            (2, os.path.join("resources", "survey_day2.json")),
            (3, os.path.join("resources", "survey_day3.json")),
            (4, os.path.join("resources", "survey_day4.json")),
        ]

        self._setup_ui()
        self._setup_layout()
        self._setup_connections()

    def _setup_ui(self):
        self._label = QLabel("ОПРОСНИКИ", self)
        self.buttons = []
        for day, _ in self._survey_configs:
            button = create_button(text=f"День {day}", disabled=False, parent=self)
            self.buttons.append(button)

    def _setup_layout(self):
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        for button in self.buttons:
            layout.addWidget(button)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _setup_connections(self):
        for button, (day, config_path) in zip(self.buttons, self._survey_configs):
            button.clicked.connect(lambda checked=False, d=day, p=config_path: self.open_survey(d, p))

    def _participant_id(self):
        if self.participant_id_getter is None:
            return None
        participant_id = self.participant_id_getter()
        participant_id = participant_id.strip() if participant_id else ""
        return participant_id or None

    def open_survey(self, day, config_path):
        window = self._survey_windows.get(day)
        if window is not None and window.isVisible():
            window.raise_()
            window.activateWindow()
            return

        window = QuestionnaireWindow(
            config_path=config_path,
            output_dir=DEFAULT_OUTPUT_DIR,
            participant_id=self._participant_id(),
        )
        window.setAttribute(Qt.WA_DeleteOnClose, True)
        window.destroyed.connect(lambda _, d=day: self._survey_windows.pop(d, None))
        self._survey_windows[day] = window
        window.show()
