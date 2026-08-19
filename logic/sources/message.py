import json

from PyQt5.QtCore import QObject, pyqtSignal


class EpochLabelMessageSource(QObject):
    labelReady = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(self, input_stream):
        super().__init__()
        input_stream.set_callback(self._receive_message)

    def _receive_message(self, msg, timestamp=None):
        try:
            if isinstance(msg, (bytes, bytearray)):
                msg = msg.decode("utf-8")
            if isinstance(msg, str):
                payload = json.loads(msg)
            elif isinstance(msg, dict):
                payload = msg
            elif isinstance(msg, (tuple, list)) and msg:
                return self._receive_message(msg[0], timestamp=timestamp)
            else:
                raise ValueError(f"unsupported message type {type(msg).__name__}")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.warning.emit(f"Invalid epoch label message ignored: {exc}")
            return

        label = payload.get("stimulus")
        if label is None:
            self.warning.emit("Invalid epoch label message ignored: missing 'stimulus'")
            return

        label = str(label).strip()
        if not label:
            self.warning.emit("Invalid epoch label message ignored: empty 'stimulus'")
            return

        self.labelReady.emit(label)
