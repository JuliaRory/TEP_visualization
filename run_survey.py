import argparse
import os
import sys

from PyQt5.QtWidgets import QApplication

from ui.survey import DEFAULT_OUTPUT_DIR, DEFAULT_SURVEY_PATH, QuestionnaireWindow
from utils.theme_loader import load_qss


os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = r".\venv\Lib\site-packages\PyQt5\Qt5\plugins"


def parse_args():
    parser = argparse.ArgumentParser(description="Run subject questionnaire window.")
    parser.add_argument(
        "--config",
        default=DEFAULT_SURVEY_PATH,
        help="Path to survey JSON config.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where JSON and CSV responses will be saved.",
    )
    parser.add_argument(
        "--participant",
        default=None,
        help="Participant ID to prefill and restore saved answers for.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app = QApplication(sys.argv)

    try:
        style = load_qss(r"styles/theme.qss", r"styles/palette.json")
        app.setStyleSheet(style)
    except Exception:
        pass

    main = QuestionnaireWindow(
        config_path=args.config,
        output_dir=args.output_dir,
        participant_id=args.participant,
    )
    main.show()
    sys.exit(app.exec_())
