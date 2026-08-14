# im /  # ① IM 接入层（业务逻辑，平台无关）
# __init__.py
# base.py  # 抽象接口 ChannelAdapter：收消息 / 发消息 / 发引用
# handler.py  # 【核心】统一消息处理：会话→调 query_processor→格式化引用→回发
# session.py  # 会话/多轮上下文管理（user_id+session 隔离，落 MongoDB）
# channels /  # 各平台适配器：只做"协议收发转换"，不含任何业务
# __init__.py
# dingtalk.py  # 钉钉：事件回调解密 + 机器人发消息 + 卡片引用
#
# server /  # ② HTTP 服务层（FastAPI）
# app.py  # FastAPI 实例 + uvicorn 入口
# routes /
# im_webhook.py  # POST /im/dingtalk/callback  等平台回调入口
# chat.py  # POST /chat（SSE 流式）——IM 和 Web 调试页复用