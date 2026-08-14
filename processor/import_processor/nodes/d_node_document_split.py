
import logging
from processor.import_processor.base import BaseNode
from processor.import_processor.state import ImportGraphState



class NodeDocumentSplit(BaseNode):
    """
    文档切分节点：智能文档切片
    """

    #切_new.md,大小为2000左右
    name = "node_document_split"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行")

    