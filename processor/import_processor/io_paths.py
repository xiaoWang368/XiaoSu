"""
本地上传/备份路径与文档 ID 规范。

上传时原文件备份到"项目外的其他磁盘目录"(由 env `LOCAL_UPLOAD_DIR` 指定,
默认 F:\\xiaosu_uploads),每个文档在 {root}/{doc_id}/ 下保存原文件。

doc_id 规范:doc_YYYYMMDD_HHMMSS_xxxxxxxx(时间戳 + 8 位随机,可读且唯一),
作为 PG 主键 / Chroma metadata / MinIO key / 本地目录名的统一标识。
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

DEFAULT_UPLOAD_DIR = r"F:\xiaosu_uploads"


def upload_root() -> Path:
    """上传备份根目录(自动创建)。"""
    root = Path(os.getenv("LOCAL_UPLOAD_DIR", DEFAULT_UPLOAD_DIR))
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_doc_id() -> str:
    """生成规范文档 ID。"""
    return f"doc_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"


def doc_dir(doc_id: str) -> Path:
    """某文档的本地备份目录(自动创建)。"""
    d = upload_root() / doc_id
    d.mkdir(parents=True, exist_ok=True)
    return d
