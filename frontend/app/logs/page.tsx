import { Card } from "@/components/ui";

export default function LogsPage() {
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-slate-800">对话日志</h1>
      <p className="mt-1 text-sm text-slate-500">查看员工提问 / 回答 / 工具调用 / Token 消耗（后端日志接口待接入）</p>
      <div className="mt-4">
        <Card title="最近对话">
          <p className="text-sm text-slate-400">暂无日志。对话日志接口完成后在此展示。</p>
        </Card>
      </div>
    </div>
  );
}
