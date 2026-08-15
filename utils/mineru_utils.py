"""
MinerU 在线解析(MinerU API):上传文件 → 轮询解析 → 下载 zip 解压出 md。
b_node(PDF)/ b1_node(Word) 共用。
"""

from __future__ import annotations

import logging
import time
import zipfile
from pathlib import Path

import requests

from config.mineru_config import mineru_config
from processor.import_processor.exceptions import FileProcessingError, PdfConversionError, StateFieldError

logger = logging.getLogger(__name__)

POLL_TIMEOUT_S = 60 * 5
POLL_INTERVAL_S = 3


def upload_and_poll(file_path: Path) -> str:
    """上传文件到 MinerU,轮询直到解析完成,返回 zip 下载地址。"""
    api_token = mineru_config.api_token
    base_url = mineru_config.base_url
    if not api_token:
        raise StateFieldError(field_name="api_token", expected_type=str)
    if not base_url:
        raise StateFieldError(field_name="base_url", expected_type=str)

    headers = {
        "Content-Type": "application/json",  # 注意:Content-Type(连字符),不是 Content_Type
        "Authorization": f"Bearer {api_token}",
    }

    # 1. 申请上传地址
    upload_url = f"{base_url}/file-urls/batch"
    data = {"files": [{"name": file_path.name}], "model_version": "vlm"}
    resp = requests.post(url=upload_url, headers=headers, json=data)
    if resp.status_code != 200:
        raise FileProcessingError(message=f"申请上传文件失败:{resp.text}")
    result = resp.json()
    if result.get("code") != 0:
        raise FileProcessingError(message=f"申请上传文件失败:{result.get('message')}")
    batch_id = result["data"]["batch_id"]
    signed_url = result["data"]["file_urls"][0]

    # 2. 上传文件本体
    with open(file_path, "rb") as f:
        res_upload = requests.put(signed_url, data=f)
        if res_upload.status_code != 200:
            raise PdfConversionError(f"文件上传失败:状态码:{res_upload.status_code},响应:{res_upload.text}")
        logger.info(f"文件上传成功:状态码:{res_upload.status_code}")

    # 3. 轮询解析结果
    poll_url = f"{base_url}/extract-results/batch/{batch_id}"
    start_time = time.time()
    while True:
        if time.time() - start_time > POLL_TIMEOUT_S:
            raise FileProcessingError(message="获得下载地址超时")

        try:
            res_poll = requests.get(url=poll_url, headers=headers, timeout=10)
        except Exception as e:  # noqa: BLE001
            logger.error(f"获取下载地址失败:{e}")
            time.sleep(POLL_INTERVAL_S)
            continue

        if res_poll.status_code != 200:
            raise FileProcessingError(message=f"获取下载地址失败:{res_poll.status_code}")

        poll_data = res_poll.json()
        if poll_data.get("code") != 0:
            raise FileProcessingError(message=f"获取下载地址失败:{poll_data.get('message')}")

        extract_results = poll_data.get("data", {}).get("extract_result", [])
        if not extract_results:
            time.sleep(POLL_INTERVAL_S)
            continue

        extract_result = extract_results[0]
        state = extract_result.get("state")  # done / failed / 处理中
        if state == "done":
            return extract_result["full_zip_url"]
        if state == "failed":
            # 注意:err_msg 在 extract_result 上,不在 state(字符串)上
            err_msg = extract_result.get("err_msg", "未知错误,无具体信息")
            raise PdfConversionError(f"[任务轮询]解析任务失败! batch_id:{batch_id},错误信息:{err_msg}")

        logger.info(f"[任务轮询]处理中... 已耗时{int(time.time() - start_time)}s,状态:{state}")
        time.sleep(POLL_INTERVAL_S)


def download_and_extract(zip_url: str, output_dir: Path, stem: str) -> Path:
    """下载解析结果 zip,解压出 full.md 并重命名为 {stem}.md,返回该路径。"""
    resp = requests.get(url=zip_url, stream=True)
    if resp.status_code != 200:
        raise FileProcessingError(message=f"下载文件失败:{resp.status_code}")

    # zip 放在 {output_dir}/{stem}.zip(doc_id 根目录)
    zip_save = output_dir / f"{stem}.zip"
    zip_save.write_bytes(resp.content)

    # 解压出同名目录 {output_dir}/{stem}/,json 等后续产物都在该子目录
    extract_dir = output_dir / stem
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_save, "r") as zf:
        zf.extractall(path=extract_dir)

    full_md = extract_dir / "full.md"
    if not full_md.exists():
        raise FileProcessingError(message=f"MinerU 结果中未找到 full.md:{extract_dir}")
    new_md = full_md.with_name(f"{stem}.md")
    full_md.rename(new_md)
    return new_md
