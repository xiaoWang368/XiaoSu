"""
PDF 转 Markdown 节点:使用 MinerU 在线解析(共享 utils.mineru_utils)。
"""

import logging
from pathlib import Path

from processor.import_processor.base import BaseNode
from processor.import_processor.exceptions import FileProcessingError, StateFieldError
from processor.import_processor.state import ImportGraphState
from utils.mineru_utils import download_and_extract, upload_and_poll


class NodePDFToMD(BaseNode):
    """
    PDF 转 Markdown 节点:PDF结构化解析(使用 MinerU 在线解析)。
    """

    name = "node_pdf_to_md"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行")
        pdf_path_obj, output_dir_obj = self._step_1_validate_paths(state)

        # MinerU:上传 → 轮询 → 下载解压出 md
        zip_url = upload_and_poll(pdf_path_obj)
        md_path = download_and_extract(zip_url, output_dir_obj, pdf_path_obj.stem)

        with open(md_path, "r", encoding="utf-8") as f:
            state["md_content"] = f.read()
        state["md_path"] = str(md_path)
        return state

    def _step_1_validate_paths(self, state):
        pdf_path = state.get("pdf_path")
        if not pdf_path:
            raise StateFieldError(field_name="pdf_path", expected_type=str)
        file_dir = state.get("file_dir")
        if not file_dir:
            raise StateFieldError(field_name="file_dir", expected_type=str)
        pdf_path_obj = Path(pdf_path)
        output_dir_obj = Path(file_dir)
        if not pdf_path_obj.is_file():
            raise FileProcessingError(message=f"文件路径不存在:{pdf_path_obj}")
        if not output_dir_obj.is_dir():
            raise FileProcessingError(message=f"输出目录不存在:{output_dir_obj}")
        return pdf_path_obj, output_dir_obj
