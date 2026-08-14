import logging

from langgraph.constants import END
from langgraph.graph import StateGraph

from processor.import_processor.base import setup_logging
from processor.import_processor.nodes.b1_node_word_to_md import NodeWordToMD
from processor.import_processor.nodes.b_node_pdf_to_md import NodePDFToMD
from processor.import_processor.nodes.c_node_md_img import NodeMDImg
from processor.import_processor.nodes.d_node_document_split import NodeDocumentSplit
from processor.import_processor.nodes.e_node_item_name_recognition import NodeItemNameRecognition
from processor.import_processor.nodes.f_node_bge_embedding import NodeBGEEmbedding
from processor.import_processor.nodes.g_node_import_milvus import NodeImportMilvus
from processor.import_processor.state import ImportGraphState


class KBImportWorkflow:
    def __init__(self, config = None):
        self._compiled_graph = None



    #单例模式,确保图实例只创建一次
    @property
    def graph(self):
        """
           返回图实例
        """
        logging.info("返回图实例")
        if self._compiled_graph is None:
            #创建实例方法,创建图
            self._compiled_graph = self.build_graph()
        return self._compiled_graph

    @staticmethod   #静态方法,不依赖与其他任何方法
    def route_after_entry(state: ImportGraphState) -> str:
        if state.get("is_pdf_read_enabled"):
            return "b_node_pdf_to_md"
        elif state.get("is_md_read_enabled"):
            return "c_node_md_img"
        elif state.get("is_word_read_enabled"):
            return "b1_node_word_to_md"
        else:
            logging.info("a_node_entry 未指定读取模式,流程结束")
            return END

    def build_graph(self):
        """
        创建主图
        """
        graph = StateGraph(ImportGraphState)
        #注册节点
        from processor.import_processor.nodes.a_node_entry import NodeEntry
        graph.add_node("a_node_entry",NodeEntry())
        graph.add_node("b_node_pdf_to_md",NodePDFToMD())
        graph.add_node("b1_node_word_to_md",NodeWordToMD())
        graph.add_node("c_node_md_img",NodeMDImg())
        graph.add_node("d_node_bge_embedding",NodeDocumentSplit())
        graph.add_node("e_node_item_name_recognition",NodeItemNameRecognition())
        graph.add_node("f_node_bge_embedding",NodeBGEEmbedding())
        graph.add_node("g_node_import_milvus",NodeImportMilvus())

        graph.set_entry_point("a_node_entry")
        #注册边
        graph.add_conditional_edges(
            "a_node_entry",
            self.route_after_entry,
            {
                "c_node_md_img":"c_node_md_img",
                "b_node_pdf_to_md":"b_node_pdf_to_md",
                "b1_node_word_to_md":"b1_node_word_to_md",
                END:END
            }
        )

        graph.add_edge("b1_node_word_to_md","c_node_md_img")
        graph.add_edge("b_node_pdf_to_md","c_node_md_img")
        graph.add_edge("c_node_md_img","d_node_bge_embedding")
        graph.add_edge("d_node_bge_embedding","e_node_item_name_recognition")
        graph.add_edge("e_node_item_name_recognition","f_node_bge_embedding")
        graph.add_edge("f_node_bge_embedding","g_node_import_milvus")
        graph.add_edge("g_node_import_milvus",END)
        #编译图
        return graph.compile()

    def run(self, state: ImportGraphState, stream: bool = True):
        if stream:
            return self.graph.stream(state)
        else:
            return self.graph.invoke(state, stream_mode="values")

if __name__ == "__main__":
    setup_logging()
    workflow = KBImportWorkflow()
    init_state = {"import_file_path":r"F:\H3C.pdf"}
    for event in workflow.run(init_state, stream = True):
        print(f"state:{event}")



