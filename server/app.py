"""
FastAPI 应用入口：CORS + 路由挂载 + 健康检查 + 日志落盘。

启动：uv run uvicorn server.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from processor.db import init_db
from processor.import_processor.ingest import seed_from_directory
from server.routes.admin import router as admin_router
from server.routes.chat import router as chat_router
from server.routes.doc import router as doc_router

LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging() -> None:
    """日志输出到 logs/server.log（滚动），同时保留 console。"""
    root = logging.getLogger()
    if root.handlers and any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return  # 避免重复挂 handler
    root.setLevel(logging.INFO)
    file_handler = RotatingFileHandler(
        LOG_DIR / "server.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    root.addHandler(file_handler)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动初始化:建表 + 文档库为空时自动灌入 data/seed。"""
    try:
        await asyncio.to_thread(init_db)
        seed = await asyncio.to_thread(seed_from_directory)
        if seed.get("seeded"):
            logging.getLogger("server").info(f"自动灌库完成: {seed.get('results')}")
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("server").warning(f"启动初始化失败(可稍后手动): {exc}")
    yield


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="小苏 · 管理后台 API", version="0.1.0", lifespan=lifespan)

    cors_origins = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(doc_router)  # /doc/{id} 查看页(无 /api 前缀)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
