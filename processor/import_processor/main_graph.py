import logging

from langgraph.constants import END
from langgraph.graph import StateGraph

from processor.import_processor.base import setup_logging
from processor.import_processor.io_paths import new_doc_id
from processor.import_processor.nodes.b1_node_word_to_md import NodeWordToMD
from processor.import_processor.nodes.b_node_pdf_to_md import NodePDFToMD
from processor.import_processor.nodes.d_node_document_split import NodeDocumentSplit
from processor.import_processor.nodes.f_node_bge_embedding import NodeBGEEmbedding
from processor.import_processor.nodes.g_node_import_milvus import NodeImportMilvus
from processor.import_processor.state import ImportGraphState


class KBImportWorkflow:
    def __init__(self, config=None):
        self._compiled_graph = None

    @property
    def graph(self):
        """
        返回图实例(单例:只编译一次)
        """
        logging.info("返回图实例")
        if self._compiled_graph is None:
            self._compiled_graph = self.build_graph()
        return self._compiled_graph

    @staticmethod
    def route_after_entry(state: ImportGraphState) -> str:
        """
        按扩展名路由:
          pdf  → b_node_pdf_to_md(PyMuPDF)
          docx → b1_node_word_to_md(mammoth)
          md/txt → d_node_document_split(入口已读入纯文本,直接分块)
        """
        if state.get("is_pdf_read_enabled"):
            return "b_node_pdf_to_md"
        if state.get("is_word_read_enabled"):
            return "b1_node_word_to_md"
        if state.get("is_md_read_enabled"):
            return "d_node_document_split"
        logging.info("a_node_entry 未指定读取模式,流程结束")
        return END

    def build_graph(self):
        """
        创建主图:entry →(parse)→ split → embed → store → END
        """
        graph = StateGraph(ImportGraphState)
        from processor.import_processor.nodes.a_node_entry import NodeEntry

        graph.add_node("a_node_entry", NodeEntry())
        graph.add_node("b_node_pdf_to_md", NodePDFToMD())
        graph.add_node("b1_node_word_to_md", NodeWordToMD())
        graph.add_node("d_node_document_split", NodeDocumentSplit())
        graph.add_node("f_node_bge_embedding", NodeBGEEmbedding())
        graph.add_node("g_node_import_milvus", NodeImportMilvus())

        graph.set_entry_point("a_node_entry")
        graph.add_conditional_edges(
            "a_node_entry",
            self.route_after_entry,
            {
                "b_node_pdf_to_md": "b_node_pdf_to_md",
                "b1_node_word_to_md": "b1_node_word_to_md",
                "d_node_document_split": "d_node_document_split",
                END: END,
            },
        )
        graph.add_edge("b_node_pdf_to_md", "d_node_document_split")
        graph.add_edge("b1_node_word_to_md", "d_node_document_split")
        graph.add_edge("d_node_document_split", "f_node_bge_embedding")
        graph.add_edge("f_node_bge_embedding", "g_node_import_milvus")
        graph.add_edge("g_node_import_milvus", END)

        return graph.compile()

    def run(self, state: ImportGraphState, stream: bool = True):
        if stream:
            return self.graph.stream(state)
        return self.graph.invoke(state, stream_mode="values")


if __name__ == "__main__":
    setup_logging()
    workflow = KBImportWorkflow()
    init_state = {"import_file_path": r"F:\数据\新人入职指南.md",
                  "doc_id": new_doc_id()}
    for event in workflow.run(init_state, stream=True):
        print(event)
    # result = workflow.run(init_state, stream=True)
    # print(result)

