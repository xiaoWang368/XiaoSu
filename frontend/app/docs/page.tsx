import { Card } from "@/components/ui";

export default function DocsPage() {
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-slate-800">文档管理</h1>
      <p className="mt-1 text-sm text-slate-500">上传 / 列表 / 删除知识库文档（后端文档接口待接入）</p>
      <div className="mt-4">
        <Card title="已上传文档">
          <p className="text-sm text-slate-400">暂无文档。上传功能将在文档知识库接口完成后开放。</p>
        </Card>
      </div>
    </div>
  );
}
