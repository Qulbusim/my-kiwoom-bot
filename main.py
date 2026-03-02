import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication
import yaml

from src.api import KiwoomAPI
from src.core import Controller, RequestQueue
from src.strategies import Semiconductor
from src.ui import KiwoomWindow
from src.utils import ScreenNumber
from src.utils import Logger
from src.utils import Discord


def main():
    with open("config/strategy.yaml", "r", encoding="utf-8") as f:
        strategy_cfg = yaml.safe_load(f) or {}
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        settings_cfg = yaml.safe_load(f) or {}
    try:
        url = Path(".env").read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        url = settings_cfg.get("WEBHOOK_URL").get("DISCORD_WEBHOOK_URL").strip()

    event_log_root = settings_cfg["paths"]["event_log_root"]

    app = QApplication(sys.argv)

    api = KiwoomAPI()
    strategy = Semiconductor(settings_cfg = settings_cfg, strategy_cfg = strategy_cfg)
    queue = RequestQueue(settings_cfg)
    window = KiwoomWindow()
    screen = ScreenNumber()
    logger = Logger(event_log_root = event_log_root)
    notifier = Discord(url)
    controller = Controller(
        settings=settings_cfg,
        api=api,
        strategy=strategy,
        queue=queue,
        ui=window,
        screen_manager=screen,
        logger=logger,
        notifier=notifier,
    )

    controller.wire()
    window.show()
    controller.login()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()