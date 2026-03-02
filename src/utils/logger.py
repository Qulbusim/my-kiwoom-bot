from datetime import datetime
from pathlib import Path

class Logger:
    def __init__(self, event_log_root):
        self.event_log_root = event_log_root

    def store_event_log(self, msg: str):
        today = datetime.now().strftime("%Y-%m-%d")
        log_path = Path(self.event_log_root) / f"{today}.log"

        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} | {msg}\n")