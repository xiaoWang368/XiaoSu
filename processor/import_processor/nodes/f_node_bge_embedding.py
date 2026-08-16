import json
import logging
from pathlib import Path
from typing import List, Dict

from processor.import_processor.base import BaseNode
from processor.import_processor.exceptions import StateFieldError
from processor.import_processor.state import ImportGraphState


class NodeBGEEmbedding(BaseNode):
    """
    混合向量化节点：使用 BGE-M3 模型将文本转换为向量
    """

    name = "node_bge_embedding"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行")
        # 步骤1：输入数据校验
        chunks = self._step_1_validate_input(state)

        # 步骤2：批量生成双向量，为切片绑定向量字段
        output_data = self._step_2_generate_embeddings(chunks)
        # 输出一下向量结果
        for item in output_data:
            #print(item.get("dense_embedding"))
            print(item.get("sparse_embedding"))
        # 备份
        self._step_3_backup(state, output_data)

        # 步骤3：更新全局状态，将带向量的chunks回传下游
        state['chunks'] = output_data

        return state

    def _step_1_validate_input(self, state):
        chunks = state.get("chunks")
        if not chunks:
            raise StateFieldError(field_name="chunks", message="输入数据中必须包含chunks字段")
        if not isinstance(chunks, list):
            raise StateFieldError(field_name="chunks", message="chunks数据类型不正确", expected_type=list)
        return chunks

    def _step_2_generate_embeddings(self, chunks: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """批量生成向量,为每个chunks新增向量字段"""
        batch_size = 5    # 每次处理5个切片
        output_data = []  # 存储处理后的chunks
        for i in range(0, len(chunks), batch_size):
            batch_data = chunks[i: i + batch_size]
            to_embedding_texts = []
            for doc in batch_data:
                item_name = doc.get("item_name")
                content = doc.get("content")
                to_embedding_texts.append(f"{item_name} \n {content}" if item_name else content)

            embeddings = self._embed(to_embedding_texts)
            for i, doc in enumerate(batch_data):
                item = doc.copy()
                item["dense_embedding"] = embeddings.get("dense")[i]
                item["sparse_embedding"] = embeddings.get("sparse")[i]
                output_data.append(item)
        return output_data

    def _embed(self, texts: List[str]) -> dict:
        """
        生成向量。与查询共用 processor.embed.embed_dense(DashScope → 确定性),
        保证导入/查询向量空间一致。
        """
        from processor.embed import embed_dense
        dense = embed_dense(texts)
        return {"dense": dense, "sparse": [{}] * len(texts)}

    def _step_3_backup(self, state, output_data):
        """备份更新状态(尽力而为,失败不中断)。备份到 {file_dir}/{file_title}/ 子目录,与 md 同层。"""
        try:
            from pathlib import Path
            file_dir = state.get("file_dir") or "data/uploads"
            backup_dir = Path(file_dir) / (state.get("file_title") or "")
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f"{state.get('file_title')}_f_chunk.json"
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(
                    output_data,
                    f,
                    ensure_ascii=False,  # 保留中文，不转义为\u编码
                    indent=2  # 格式化缩进，便于阅读
                )
        except Exception:
            logging.warning(f"{self.name} 备份失败,跳过")



if __name__ == "__main__":
    node = NodeBGEEmbedding()
    with open("F:\output\B530\联想B530笔记本电脑_e_chunks.json", "r", encoding = "utf-8") as f:
        chunks_content = f.read()
    #加载成json格式
    json_state = json.loads(chunks_content)
    state = {
        "chunks": json_state,
        "file_title": "B530"
    }
    response = node(state)
    #print(response)


