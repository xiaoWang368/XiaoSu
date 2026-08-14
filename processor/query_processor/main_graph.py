from langgraph.constants import END
from langgraph.graph import StateGraph

from processor.query_processor.nodes.a_node_item_name_confirm import NodeItemNameConfirm
from processor.query_processor.nodes.b_node_search_embedding import NodeSearchEmbedding
from processor.query_processor.nodes.c_node_search_embedding_hyde import NodeSearchEmbeddingHyde
from processor.query_processor.nodes.d_node_web_search_mcp import NodeWebSearchMcp
from processor.query_processor.nodes.e_node_rrf import NodeRrf
from processor.query_processor.nodes.f_node_rerank import NodeRerank
from processor.query_processor.nodes.g_node_answer_output import NodeAnswerOutput
from processor.query_processor.state import QueryGraphState


class KBQueryWorkflow:
    def __init__(self, config = None):
        #初始化langgraph状态图
        self.workflow = StateGraph(QueryGraphState)
        #注册节点
        self._init_nodes()
        #注册节点到到图
        self._register_nodes()
        #设置入口和路由规则
        self._setup_routers()
        #编译工作流
        self._compiled_app = None

    def _init_nodes(self):
        print("注册节点")
        self.node_item_name_confirm = NodeItemNameConfirm()
        self.node_search_embedding = NodeSearchEmbedding()
        self.node_search_embedding_hyde = NodeSearchEmbeddingHyde()
        self.node_web_search_mcp = NodeWebSearchMcp()
        self.node_rrf = NodeRrf()
        self.node_rerank = NodeRerank()
        self.node_answer_output = NodeAnswerOutput()

    def _register_nodes(self):
        print("注册节点到图")
        """注册节点到图"""
        self.workflow.add_node("node_item_name_confirm", self.node_item_name_confirm)
        self.workflow.add_node("node_search_embedding", self.node_search_embedding)
        self.workflow.add_node("node_search_embedding_hyde", self.node_search_embedding_hyde)
        self.workflow.add_node("node_web_search_mcp", self.node_web_search_mcp)
        self.workflow.add_node("node_rrf", self.node_rrf)
        self.workflow.add_node("node_rerank", self.node_rerank)
        self.workflow.add_node("node_answer_output", self.node_answer_output)

    def _setup_routers(self):
        print("设置路由规则")
        """设置路由规则"""
        #入口节点
        self.workflow.set_entry_point("node_item_name_confirm")
        self.workflow.add_conditional_edges(
            "node_item_name_confirm",
            self.route_after_item_name_confirm,
            {
                "node_search_embedding":"node_search_embedding",  #向量检索
                "node_search_embedding_hyde":"node_search_embedding_hyde",  #hyde检索(调用llm)
                "node_web_search_mcp":"node_web_search_mcp",  #web检索
                "node_answer_output": "node_answer_output"  #直接输出
            }
        )
        self.workflow.add_edge("node_search_embedding", "node_rrf")
        self.workflow.add_edge("node_search_embedding_hyde", "node_rrf")
        self.workflow.add_edge("node_web_search_mcp", "node_rrf")
        self.workflow.add_edge("node_rrf", "node_rerank")
        self.workflow.add_edge("node_rerank", "node_answer_output")
        self.workflow.add_edge("node_answer_output", END)
    def route_after_item_name_confirm(self,state:QueryGraphState) -> str:
        print("路由规则")
        if state.get("answer"):
            return "node_answer_output"
        return ["node_search_embedding","node_search_embedding_hyde","node_web_search_mcp"]

    def compile(self):
        print("编译工作流")
        """编译工作流"""
        if not self._compiled_app:
            self._compiled_app = self.workflow.compile()
        return self._compiled_app

    def run(self, initial_state: QueryGraphState, stream: bool = True):
        print("运行工作流")
        self.compile()
        if stream:
            return self._compiled_app.stream(initial_state)
        else:
            return self._compiled_app.invoke(initial_state)

if __name__ == "__main__":
    workflow = KBQueryWorkflow()
    result = workflow.run(QueryGraphState(query="你好"), stream = True)
    print(result)
    draw_ascii = workflow.compile().get_graph().draw_ascii()
    print(draw_ascii)





















