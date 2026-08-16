"""IM 平台适配器抽象:收消息 / 发消息 / 发引用。平台无关的业务在 handler。"""

from abc import ABC


class ChannelAdapter(ABC):
    """各平台适配器只做「协议收发转换」,不含任何业务逻辑。"""

    platform: str = "base"

    def start(self) -> None:
        """启动长连接(钉钉为 WebSocket Stream)。"""

    def is_connected(self) -> bool:
        return False

    def send_markdown(self, to: str, title: str, markdown: str) -> None:
        """发送 Markdown(答案+引用)。默认空实现,各平台按自身机制覆盖
        (钉钉在回调里用 incoming_message 的 session_webhook 回复)。"""
