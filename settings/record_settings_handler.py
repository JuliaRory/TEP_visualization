
from dataclasses import is_dataclass
import json
from dataclasses import asdict
import os

class RecordSettingsHandler:

    def __init__(self, settings, ui):
        self.settings = settings        # nvx record
        self.ui = ui                  # nvx record panel


    def load_from_json(self, path=None, default=True):
        if default:
            path = r"data/settings/record_default.json"
        
        if not os.path.exists(path):
            print(f"{path} does not exist.")
            return 
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._apply_dict_to_settings(self.settings, data)
        self.sync_ui_from_settings()

    
    def save_to_json(self, path=None, default=True):
        if default:
            path = r"data/settings/record_default.json"
        self.sync_settings_from_ui()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.settings), f, indent=4, ensure_ascii=False)
        
    
    def _apply_dict_to_settings(self, obj, data: dict):
        for key, value in data.items():
            attr = getattr(obj, key)
            if is_dataclass(attr):
                self._apply_dict_to_settings(attr, value)
            else:
                setattr(obj, key, value)


    def sync_ui_from_settings(self):
        s = self.settings

        self.ui.lineedit_folder.setText(s.records_folder)
        self.ui.lineedit_number.setText(s.number)
        self.ui.lineedit_subject.setText(s.subject)
        self.ui.lineedit_spot.setText(s.spot)
        self.ui.lineedit_yaw_angle.setText(s.yaw_angle)    
        self.ui.lineedit_power.setText(self._power_for_ui(s.power))
        self.ui.lineedit_comments.setText(s.comments)

        
        self.ui.checkbox_number.setChecked(s.use_number)
        self.ui.checkbox_subject.setChecked(s.use_subject)
        self.ui.checkbox_spot.setChecked(s.use_spot)
        self.ui.checkbox_yaw_angle.setChecked(s.use_yaw_angle)
        self.ui.checkbox_power.setChecked(s.use_power)
        self.ui.checkbox_comments.setChecked(s.use_comments)

        self.ui.update_next_record_number()

    def sync_settings_from_ui(self):
        s = self.settings

        s.number = self.ui.lineedit_number.text()
        s.subject = self.ui.lineedit_subject.text()
        s.spot = self.ui.lineedit_spot.text()
        s.coil = ""
        s.yaw_angle = self.ui.lineedit_yaw_angle.text()
        s.power = self.ui.lineedit_power.text()
        s.comments = self.ui.lineedit_comments.text()
        s.records_folder = self.ui.lineedit_folder.text()

        s.use_number = self.ui.checkbox_number.isChecked()
        s.use_subject = self.ui.checkbox_subject.isChecked()
        s.use_spot = self.ui.checkbox_spot.isChecked()
        s.use_coil = False
        s.use_yaw_angle = self.ui.checkbox_yaw_angle.isChecked()
        s.use_power = self.ui.checkbox_power.isChecked()
        s.use_comments = self.ui.checkbox_comments.isChecked()

    @staticmethod
    def _power_for_ui(value):
        value = str(value).strip()
        return value[:-3] if value.upper().endswith("MSO") else value
