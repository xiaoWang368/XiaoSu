import json
import logging
import re
from pathlib import Path
from typing import Dict, List

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError
from processor.import_processor.import_config import get_config
from processor.import_processor.state import ImportGraphState

from langchain_text_splitters import RecursiveCharacterTextSplitter


class NodeDocumentSplit(BaseNode):
    """
    文档切分节点：智能文档切片
    """

    #切_new.md,大小为2000左右
    name = "node_document_split"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行")
        #1. 处理参数:从state中获取md_path,md_content等参数
        #文本内容 文件名(文件标题)
        content, file_title = self._step_1_get_inputs(state)
        #2.标题切块
        #sections实际上是一个字典类型的列表
        sections, title_count, lines_count = self._step_2_split_by_title(content, file_title)

        #3. 无标题兜底
        sections = self._step_3_handle_no_title(content,sections, title_count, file_title)

        #4. 精细化处理(长切短合)
        sections = self._step_4_refine_chunks(sections)

        #4.1 追加引用定位元数据(doc_id / chunk_index / char_start / char_end)
        sections = self._add_location_meta(sections, content, state)

        #5. 备份更新,打印日志
        self._step_5_print_status(sections, lines_count)
        self._step_6_backup(state, sections)

        #更新state
        state["chunks"] = sections

        return state

    #1. 处理参数: 从state中获取文档内容,文档标题
    def _step_1_get_inputs(self, state):
        logging.info("node_document_split步骤一,参数处理")
        content = state.get("md_content")
        file_title = state.get("file_title")
        if not file_title:
            raise StateFieldError(field_name = "file_title", expected_type = str)
        if not content:
            logging.info("状态错误,md_content为空")
            raise StateFieldError(field_name = "md_content", expected_type = str)

        #回车+换行符替换为换行符,回车替换成换行符
        content = content.replace("\r\n", "\n").replace("\r", "\n")

        return content, file_title

    #标题切块
    def _step_2_split_by_title(self, content, file_title):
        #传入文档内容,文档标题,返回切分后的段落列表,标题数量,总行数
        #每个段落是一个字典,包含标题,content,title_content,parent_title,part,file_title
        # 其中parent_title是只有在长切后才会有的值,所以在step_4里第一次被赋值
        logging.info("node_document_split步骤二,标题切块")
        sections: List[Dict[str, str]] = []
        title_count = 0
        lines = content.split("\n")
        current_lines = []
        current_title = ""
        in_code_block = False
        title_pattern = r'^\s*#{1,6}\s+.+'

        def _flush_section():
            # 刷新当前段落
            #如果当前段落为空,不刷新(第一次进入不刷新)
            if not current_lines:
                return
            # 标题处理
            sections.append({
                "title": current_title,
                "content": "\n".join(current_lines),
                "title_content": "",
                "file_title": file_title
            })

        for line in lines:
            if line.startswith("~~~") or line.startswith("```"):
                in_code_block = not in_code_block
                current_lines.append(line)
                continue

            if (not in_code_block) and (re.match(title_pattern, line)):
                #标题处理
                _flush_section()
                current_title = line.strip()
                current_lines = [current_title]
                title_count += 1

            else:
                    current_lines.append(line)

        _flush_section()
        print("切分后的段落列表:", sections)

        return sections, title_count, len(lines)




    #无标题兜底
    def _step_3_handle_no_title(self, content: str, sections: List[Dict[str, str]],
                                title_count: int, file_title: str):
        logging.info("node_document_split步骤三, 无标题兜底")
        if title_count == 0:
            return [{"title": "无标题", "content": content, "file_title": file_title}]
        return sections

    #细化处理(长切短合)
    def _step_4_refine_chunks(self, sections) -> List[Dict[str, str]]:
        logging.info("node_document_split 步骤四, 精细化处理")
        refined_split = []
        for sec in sections:
            #长切
            refined_split.extend(self.split_long_section(sec))
        #短合
        final_sections = self.merge_short_sections(refined_split)

        for sec in final_sections:
            if not sec.get("parent_title"):
                sec["parent_title"] = sec["title"] or ""
        return final_sections

    # 追加引用定位元数据:相对原文 md_content 的字符偏移 + doc_id/chunk_index
    def _add_location_meta(self, sections, content: str, state) -> List[Dict[str, str]]:
        doc_id = state.get("doc_id") or ""
        doc_name = state.get("doc_name") or state.get("file_title") or ""
        cursor = 0
        for idx, sec in enumerate(sections):
            text = sec.get("content", "")
            start = content.find(text, cursor)
            if start < 0:
                start = cursor  # 未精确命中时用游标兜底(近似位置,够高亮用)
            sec["doc_id"] = doc_id
            sec["doc_name"] = doc_name
            sec["chunk_index"] = idx
            sec["char_start"] = start
            sec["char_end"] = start + len(text)
            cursor = start + len(text)
        return sections

    #5. 打印日志
    def _step_5_print_status(self, sections, lines_count):
        chunk_num = len(sections)
        self.logger.info("-" * 50 + "文档切分统计信息" + "-" * 50)
        self.logger.info(f"md原始文本总行数: {lines_count}")
        self.logger.info(f"最终生成chunk数量: {chunk_num}")



    #6. 备份更新(尽力而为,失败不中断)
    def _step_6_backup(self, state, sections):
        """
        【步骤6】Chunk结果本地JSON备份（便于调试/问题排查，保留处理结果）
        备份到 file_dir 下;目录不存在或写入失败仅记日志,不终止流程。
        """
        try:
            file_dir = state.get("file_dir") or "data/uploads"
            # 备份到 {file_dir}/{file_title}/ 子目录,与转换出的 md 同层
            backup_dir = Path(file_dir) / (state.get("file_title") or "")
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"{state.get('file_title')}_chunk.json"
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(
                    sections,
                    f,
                    ensure_ascii=False,  # 保留中文，不转义为\u编码
                    indent=2             # 格式化缩进，便于阅读
                )
            self.logger.info(f"步骤6：Chunk结果备份成功，备份文件路径：{backup_path}")
        except Exception as e:
            # 备份失败仅记录日志，不终止主流程
            self.logger.error(f"步骤6：Chunk结果备份失败，错误信息：{str(e)}", exc_info=False)



    def split_long_section(self, sections):
        content = sections.get("content", "")
        content_len = len(content)
        # 长度合标,直接返回
        if content_len <= get_config().max_content_length:
            return [sections]

        title = sections.get("title", "")  # 没有换行符的title
        # 计算可用长度
        prefix = f"{title}\n\n" if title else ""  #标题 + 2个换行符
        available_len = get_config().max_content_length - len(prefix)#标题长度

        # 去重标题
        if title and content.lstrip().startswith(title):
            content = content[content.find(title) + len(title):]

        # 切分器
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=available_len,
            chunk_overlap=0,
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],        )
        sub_sections = []
        for index, chunk in enumerate(splitter.split_text(content), start=1):
            text = chunk.strip()
            if not text:  # 空行,跳过
                continue
            full_text = (prefix + text).strip()
            sub_sections.append(
                {
                    "title": f"{title} - {index}" if title else f"chunk - {index}",  # 标题 - 1
                    "content": full_text,
                    "parent_title": title,
                    "part": index,
                    "file_title": sections.get("file_title")
                }
            )
        return sub_sections

    def merge_short_sections(self, sections):
        #属于同一个parent_title的段落才能被合并
        if not sections:
            self.logger.debug("待合并chunk列表为空,直接返回")
            return []

        merged_sections = []
        current_chunk = None

        for section in sections:
            #初始化,直接将第一个section加入current_chunk
            if not current_chunk:
                current_chunk =section
                continue
            #条件: 1.当前chunk的parent_title与下一个相同,2.content_len < min_content_len
            #仅"长切出的子块"(parent_title 非空)允许合并;顶层标题章节各自独立,不合并
            is_current_length = len(current_chunk["content"]) < self.config.min_content_length
            is_same_parent = bool(current_chunk.get("parent_title")) and \
                current_chunk.get("parent_title") == section.get("parent_title")
            if is_same_parent and is_current_length:
                #条件符合,合并当前chunk和next_chunk
                #合并前清理,去掉下一块开头重复的parent,避免内容冗余
                parent_title = section.get("parent_title", "")
                next_content = section.get("content", "")
                if parent_title and next_content.startswith(parent_title):
                    next_content = next_content[len(parent_title):].lstrip()
                current_chunk["content"] += "\n\n" + next_content
                #合并后,要更新chunk的part,保留最新序号
                current_chunk["part"] = section.get("part")
                self.logger.debug(
                    f"合并chunk: {current_chunk.get('part')} -> {section.get('part')}"
                )
            else:
                #不满足合并条件,直接替换current_chunk
                merged_sections.append(current_chunk)
                current_chunk = section
        if current_chunk:
            merged_sections.append(current_chunk)
        return merged_sections

if __name__ == "__main__":
    node = NodeDocumentSplit()
    #开启日志记录
    setup_logging()
    with open("F:\output\B530\B530-result_new.md", "r", encoding="utf-8") as f:
        md_content = f.read()
    state = {
        "md_path": "F:\output\B530\B530-result_new.md",
        "md_content": md_content,
        "file_title": "B530-result_new"
    }
    d = node(state)
    print(d)
    #备份路径: "F:/doc / {state.get('file_title')} / chunks.json"




    