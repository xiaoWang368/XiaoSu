"""钉钉 Stream 适配器:WebSocket 长连接(免公网),只做协议收发转换。

注册企业内部应用并开启 Stream 模式后,填 DINGTALK_APP_KEY/SECRET 到 .env。
群聊需 @ 机器人触发;私聊直接对话。回复用 markdown(含引用链接)。
"""

from __future__ import annotations

import logging
import os
import threading

from dingtalk_stream import (
    AckMessage,
    CallbackMessage,
    ChatbotHandler,
    ChatbotMessage,
    Credential,
    DingTalkStreamClient,
)

from im.base import ChannelAdapter

logger = logging.getLogger("im.dingtalk")


class _BotHandler(ChatbotHandler):
    """钉钉机器人消息回调:解析消息 → 交统一 handler → markdown 回复。"""

    def __init__(self, message_handler):
        super().__init__()
        self.message_handler = message_handler

    async def process(self, callback_message: CallbackMessage):
        try:
            msg = ChatbotMessage.from_dict(callback_message.data)
        except Exception:  # noqa: BLE001
            return AckMessage.STATUS_OK, "ok"

        # 只处理文本消息
        if msg.message_type != "text" or not getattr(msg.text, "content", None):
            return AckMessage.STATUS_OK, "ok"
        text = msg.text.content.strip()
        if not text:
            return AckMessage.STATUS_OK, "ok"

        reply = await self.message_handler.handle(
            "dingtalk", msg.sender_staff_id, msg.conversation_id, text
        )
        self.reply_markdown("小苏", reply, msg)
        return AckMessage.STATUS_OK, "ok"


class DingTalkAdapter(ChannelAdapter):
    """钉钉 Stream 适配器:start() 在 daemon 线程里跑 WebSocket 长连接。"""

    platform = "dingtalk"

    def __init__(self, message_handler):
        self.message_handler = message_handler
        self._client: DingTalkStreamClient | None = None
        self._thread: threading.Thread | None = None
        self._connected = False

    def start(self) -> None:
        app_key = os.getenv("DINGTALK_APP_KEY", "")
        app_secret = os.getenv("DINGTALK_APP_SECRET", "")
        if not app_key or not app_secret:
            logger.error("未配置 DINGTALK_APP_KEY/SECRET,钉钉机器人不启动")
            return

        credential = Credential(app_key, app_secret)
        self._client = DingTalkStreamClient(credential)
        bot = _BotHandler(self.message_handler)
        self._client.register_callback_handler(ChatbotMessage.TOPIC, bot)

        self._thread = threading.Thread(target=self._client.start_forever, daemon=True)
        self._thread.start()
        self._connected = True
        logger.info("钉钉 Stream 已启动(WebSocket 长连接,免公网)")

    def is_connected(self) -> bool:
        return self._connected
