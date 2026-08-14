import logging
from processor.import_processor.base import BaseNode
from processor.import_processor.state import ImportGraphState


class NodeWordToMD(BaseNode):
    """
    Word 转 Markdown 节点：Word结构化解析
    """

    name = "node_word_to_md"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行")