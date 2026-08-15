import { Card } from "@/components/ui";

/** 引用跳转目标页：展示文档原文并按 chunk 参数高亮（后端 /doc/{id} 待接入）。 */
export default async function DocPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ chunk?: string }>;
}) {
  const { id } = await params;
  const { chunk } = await searchParams;
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-slate-800">文档原文</h1>
      <p className="mt-1 text-sm text-slate-500">
        文档 ID：{id}
        {chunk ? ` · 定位到第 ${chunk} 个片段` : ""}
      </p>
      <div className="mt-4">
        <Card title="原文">
          <p className="text-sm text-slate-400">
            原文查看与高亮功能将在文档知识库接口（/api/docs/{id}/text）完成后接入。
          </p>
        </Card>
      </div>
    </div>
  );
}
