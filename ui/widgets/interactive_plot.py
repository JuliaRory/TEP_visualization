from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
import plotly.graph_objects as go
import plotly.io as pio
import tempfile, os

from PyQt5.QtCore import QUrl

class PlotWindow(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.web = QWebEngineView()
        layout.addWidget(self.web)

        fig = go.Figure(data=go.Scatter(x=[1,2,3], y=[3,1,2]))
        html = pio.to_html(fig, include_plotlyjs='cdn', full_html=False)

        tmp = os.path.join(tempfile.gettempdir(), "plot.html")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(html)

        self.web.load(QUrl.fromLocalFile(tmp))
        