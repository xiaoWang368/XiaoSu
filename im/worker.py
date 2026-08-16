"""IM worker 独立进程:启动钉钉 Stream 长连接(WebSocket)。

用法: uv run python -m im.worker
日志: logs/dingtalk.log
"""

from __future__ import annotations

import logging
import os
import time
from logging.handlers import RotatingFileHandler

from im.channels.dingtalk import DingTalkAdapter
from im.handler import MessageHandler


def setup_logging() -> None:
    log_dir = os.getenv("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    root = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return
    root.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        os.path.join(log_dir, "dingtalk.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    root.addHandler(handler)


def main() -> None:
    setup_logging()
    logger = logging.getLogger("im.worker")
    handler = MessageHandler()
    adapter = DingTalkAdapter(handler)
    adapter.start()
    if not adapter.is_connected():
        logger.error("钉钉未启动:请检查 .env 中的 DINGTALK_APP_KEY / DINGTALK_APP_SECRET")
        return
    logger.info("小苏 IM worker 运行中(钉钉 Stream 长连接)…")
    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("退出 IM worker")


if __name__ == "__main__":
    main()
