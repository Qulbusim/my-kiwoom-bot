from datetime import datetime

from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from PyQt5 import uic


form_class = uic.loadUiType("src/ui/resources/main.ui")[0]

class KiwoomWindow(QMainWindow, form_class):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowIcon(QIcon("src/ui/resources/icon.ico"))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

    def connection_state(self, state: bool):
        if state:
            self.lbl_conn_status.setText("CONNECTED")
            self.lbl_conn_dot.setStyleSheet("background-color: #16a34a; border-radius: 6px;")
        else:
            self.lbl_conn_status.setText("DISCONNECTED")
            self.lbl_conn_dot.setStyleSheet("background-color: #dc3545; border-radius: 6px;")

    def queue_state(self, name: str, num: int):
        if name == "order":
            self.lbl_order_queue_value.setText(str(num))
        elif name == "tr":
            self.lbl_tr_queue_value.setText(str(num))

    def _append_log(self, widget, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        widget.appendPlainText(f"[{ts}] {msg}")

    def show_api_message(self, msg: str):
        self._append_log(self.api_txt_logs, str(msg))

    def show_app_message(self, msg: str):
        self._append_log(self.app_txt_logs, str(msg))

    def toggle_ctrl(self, is_enabled: bool):
        if is_enabled:
            self.btn_auto_trade.setText("자동매매 STOP")
        else:
            self.btn_auto_trade.setText("자동매매 START")