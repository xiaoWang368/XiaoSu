
import logging
from processor.import_processor.base import BaseNode
from processor.import_processor.state import ImportGraphState


#node c: 图片理解
#1. 从state中获取md_path,md_content,images_dir等参数
#2. 扫描图片路径和上下文,将图片名称作为key,另两个作为value
#3. 模型图片摘要: 通过滑动窗口限速,用llm对模型图片进行摘要,返回图片摘要字典(以图片名称为key,摘要为value)
#4. 上传到minio,(192.168.100,128:9000/桶名/项目名/md名/图片名), 用正则匹配将url 图片摘要替换到md_content中
#5. 设置备份_new.md,保存在md_path同级目录;  最后更新state中的md_path, md_content

class NodeMDImg(BaseNode):
    """
    MarkDown图片处理节点：多模态图片理解
    """

    name = "node_md_img"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行...")

