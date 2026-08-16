import logging
import shutil
from pathlib import Path

from processor.import_processor.base import BaseNode
from processor.import_processor.exceptions import StateFieldError, FileProcessingError
from processor.import_processor.io_paths import doc_dir, new_doc_id
from processor.import_processor.state import ImportGraphState

# 支持格式
SUPPORTED_EXTS = {".md", ".txt", ".pdf", ".docx"}


class NodeEntry(BaseNode):
    """
    入口节点：任务分发。

    按扩展名分派：
      .md/.txt → 直接读纯文本到 state["md_content"],走分块
      .pdf     → 置 pdf_path + is_pdf_read_enabled,走 b_node_pdf_to_md(PyMuPDF)
      .docx    → 置 word_path + is_word_read_enabled,走 b1_node_word_to_md(mammoth)
    """

    name = "node_entry"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行")
        import_file_path = state.get("import_file_path")
        if not import_file_path:
            raise StateFieldError(field_name="import_file_path", expected_type=str)

        path_obj = Path(import_file_path)
        if not path_obj.exists():
            raise FileProcessingError(message=f"文件不存在: {import_file_path}")

        ext = path_obj.suffix.lower()
        if ext not in SUPPORTED_EXTS:
            raise FileProcessingError(message=f"不支持的文件格式: {ext}")

        # 文档唯一标识(引用定位/增量更新用):优先用调用方传入的 doc_id
        doc_id = state.get("doc_id") or new_doc_id()
        file_title = path_obj.stem
        doc_name = state.get("doc_name") or (file_title + ext)

        # 输出目录:项目外的其他磁盘目录 {LOCAL_UPLOAD_DIR}/{doc_id}(规范命名)
        file_dir = state.get("file_dir") or str(doc_dir(doc_id))
        Path(file_dir).mkdir(parents=True, exist_ok=True)

        # 确保原文件在备份目录(源已在 file_dir 时跳过,避免自我复制 WinError 32)
        dst = Path(file_dir) / path_obj.name
        if path_obj.resolve() != dst.resolve():
            shutil.copy2(path_obj, dst)

        state["doc_id"] = doc_id
        state["doc_name"] = doc_name
        state["file_title"] = file_title
        state["file_dir"] = file_dir

        if ext == ".md" or ext == ".txt":
            # 纯文本直接读入,跳过解析节点;编码探测:utf-8 失败回退 gbk(BUG-6)
            raw = path_obj.read_bytes()
            try:
                state["md_content"] = raw.decode("utf-8")
            except UnicodeDecodeError:
                state["md_content"] = raw.decode("gbk", errors="replace")
            state["is_md_read_enabled"] = True
            state["md_path"] = str(path_obj)
        elif ext == ".pdf":
            state["pdf_path"] = import_file_path
            state["is_pdf_read_enabled"] = True
        elif ext == ".docx":
            state["word_path"] = import_file_path
            state["is_word_read_enabled"] = True

        return state

if __name__ == "__main__":
    from processor.import_processor.base import setup_logging
    from processor.import_processor.state import create_default_state

    setup_logging()

    TEST_FILE = r"F:\数据\新人入职指南.md"

    init_state = create_default_state(
        import_file_path=TEST_FILE,
    )

    node = NodeEntry()
    result = node(init_state)

    print(f"文件名: {result.get('doc_name')}")
    print(f"标题: {result.get('file_title')}")
    print(f"输出目录: {result.get('file_dir')}")
    print(f"md_path: {result.get('md_path')}")
    print(f"md_content 前100字: {str(result.get('md_content', '')[:100])}...")
    print(f"is_md_read_enabled: {result.get('is_md_read_enabled')}")
    print(f"is_pdf_read_enabled: {result.get('is_pdf_read_enabled')}")
    print(f"is_word_read_enabled: {result.get('is_word_read_enabled')}")