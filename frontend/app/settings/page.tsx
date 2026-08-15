import { Card, Badge } from "@/components/ui";

export default function SettingsPage() {
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-slate-800">设置</h1>
      <p className="mt-1 text-sm text-slate-500">模型配置 / IM 接入状态（后端设置接口待接入）</p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Card title="模型">
          <div className="text-sm text-slate-400">模型切换功能待接入</div>
        </Card>
        <Card title="IM 接入状态">
          <div className="flex items-center gap-2 text-sm">
            <Badge text="未配置" tone="gray" />
            <span className="text-slate-500">钉钉 Stream（待接入）</span>
          </div>
        </Card>
      </div>
    </div>
  );
}
