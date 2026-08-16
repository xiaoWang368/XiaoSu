import logging

from langgraph.constants import END
from langgraph.graph import StateGraph

from processor.query_processor.nodes.b_node_search_embedding import NodeSearchEmbedding
from processor.query_processor.nodes.c_node_search_embedding_hyde import NodeSearchEmbeddingHyde
from processor.query_processor.nodes.e_node_rrf import NodeRrf
from processor.query_processor.nodes.f_node_rerank import NodeRerank
from processor.query_processor.nodes.g_node_answer_output import NodeAnswerOutput
from processor.query_processor.nodes.h_node_route import NodeRoute
from processor.query_processor.nodes.i_node_tool_agent import NodeToolAgent
from processor.query_processor.state import QueryGraphState


class KBQueryWorkflow:
    """
    查询工作流:
      entry → route(LLM 判断 knowledge/tool/refuse)
        knowledge → search/hyde/web(并行)→ rrf → rerank → answer
        tool      → tool_agent → answer
        refuse    → answer(硬拒答)
    """

    def __init__(self, config=None, on_token=None):
        self._on_token = on_token
        self._compiled_app = None
        self.workflow = StateGraph(QueryGraphState)
        self._init_nodes()
        self._register_nodes()
        self._setup_routers()

    def _init_nodes(self):
        self.node_route = NodeRoute()
        self.node_search_embedding = NodeSearchEmbedding()
        self.node_search_embedding_hyde = NodeSearchEmbeddingHyde()
        self.node_rrf = NodeRrf()
        self.node_rerank = NodeRerank()
        self.node_answer_output = NodeAnswerOutput(on_token=self._on_token)
        self.node_tool_agent = NodeToolAgent()

    def _register_nodes(self):
        self.workflow.add_node("node_route", self.node_route)
        self.workflow.add_node("node_search_embedding", self.node_search_embedding)
        self.workflow.add_node("node_search_embedding_hyde", self.node_search_embedding_hyde)
        self.workflow.add_node("node_rrf", self.node_rrf)
        self.workflow.add_node("node_rerank", self.node_rerank)
        self.workflow.add_node("node_answer_output", self.node_answer_output)
        self.workflow.add_node("node_tool_agent", self.node_tool_agent)

    def _setup_routers(self):
        self.workflow.set_entry_point("node_route")
        self.workflow.add_conditional_edges(
            "node_route",
            self.route_after_route,
            {
                "node_search_embedding": "node_search_embedding",
                "node_search_embedding_hyde": "node_search_embedding_hyde",
                "node_tool_agent": "node_tool_agent",
                "node_answer_output": "node_answer_output",
            },
        )
        self.workflow.add_edge("node_search_embedding", "node_rrf")
        self.workflow.add_edge("node_search_embedding_hyde", "node_rrf")
        self.workflow.add_edge("node_rrf", "node_rerank")
        self.workflow.add_edge("node_rerank", "node_answer_output")
        self.workflow.add_edge("node_tool_agent", "node_answer_output")
        self.workflow.add_edge("node_answer_output", END)

    @staticmethod
    def route_after_route(state: QueryGraphState):
        intent = state.get("intent", "knowledge")
        if intent == "tool":
            return "node_tool_agent"
        if intent == "refuse":
            return "node_answer_output"
        # knowledge:并行进入三路检索
        return ["node_search_embedding", "node_search_embedding_hyde"]

    def compile(self):
        if not self._compiled_app:
            self._compiled_app = self.workflow.compile()
        return self._compiled_app

    def run(self, initial_state, stream: bool = True):
        self.compile()
        if stream:
            return self._compiled_app.stream(initial_state)
        return self._compiled_app.invoke(initial_state, stream_mode="values")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    workflow = KBQueryWorkflow()
    result = workflow.run(QueryGraphState(original_query="员工入职需要提前准备哪些材料"), stream=False)
    print(result.get("answer"))
