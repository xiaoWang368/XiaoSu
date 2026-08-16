# 小苏 · 公司内部 AI 助手

> 员工在 IM / Web 里提问,小苏从公司知识库找答案(带原文出处),或调用内部系统 API 查数据、算汇总。
> 全栈 AI Coding 工程笔试作品。基于 RAG + 函数调用(Agent) 双路径,核心引擎为 LangGraph 状态机工作流。

---

## 一、项目介绍

「小苏」是给公司员工用的内部 AI 助手,解决两类问题:

1. **知识类问题** —— 比如「我每年有几天年假?」「报销发票需要什么材料?」
   → 小苏从上传到知识库的**员工手册 / 入职指南 / FAQ** 里检索,给出**带引用**的答案(哪个文件、哪一段原文),检索不到时明确说"文档里没找到",绝不瞎编。
2. **数据类问题** —— 比如「员工 001 是哪个部门的?」「上周一共多少订单?」
   → 小苏**自主决定**调用内部系统 Mock API(员工 / 考勤 / 订单)或通用工具(当前时间),把结果整理成答案。

核心特点:

- **模型自主决策**:不写死 if-else,由 LLM 判断问题是走"查知识库""调工具"还是"直接拒答"。
- **流式输出**:答案边生成边下发(SSE),不憋一坨再返回。
- **引用溯源**:答案标注【N】引用,附文件 + 原文片段 + 字符定位元数据,支持跳转原文。
- **知识库增量更新**:上传同名文档按 sha256 去重 / 替换,不重复处理。
- **工程规范**:uv 管理 Python 依赖、pnpm 管理前端、配置全走环境变量、日志落 `logs/` 目录、`.env` 不入库。

> **开发进度**:核心问答引擎(检索 / 工具调用 / 流式)与文档导入管线已可用;钉钉 IM 接入与 Web 管理后台(文档管理 / 对话日志 / 设置)正在开发,详见 [Roadmap](#roadmap)。

---

## 二、架构图

### 2.1 系统总览

```
┌───────────────────────────┐         ┌────────────────────────────────┐
│      员工 (入口)            │         │       管理员 (Web 后台,开发中)     │
│  ┌─────────┐  ┌─────────┐  │         │   /docs  文档管理(待接入)          │
│  │ 钉钉 IM  │  │ Web 聊天  │  │         │   /logs  对话日志(待接入)          │
│  │(开发中)  │  │ 页(可用) │  │         │   /settings 设置(待接入)          │
│  └────┬────┘  └────┬────┘  │         └───────────────┬────────────────┘
└───────┼────────────┼────────┘                         │
        │            │  POST /api/chat (SSE)           │ REST(待接入)
        │            ▼                                ▼
┌───────┴───────────────────────────────────────────────────────────────┐
│                          FastAPI 后端 (server/, :8000)                  │
│   ┌───────────────┐   ┌────────────────────────────────────────────┐   │
│   │ QueryService  │──▶│   LangGraph 查询工作流 (processor/query)     │   │
│   │  (SSE 门面)    │   │  路由 → 检索 → 融合 → 重排 → 生成/拒答/工具    │   │
│   └───────┬───────┘   └───────────────┬────────────────────────────┘   │
│           │                            │                               │
│   ┌───────▼───────┐   ┌───────────────▼────────────────────────────┐   │
│   │  导入门面       │   │  LangGraph 导入工作流 (processor/import)     │   │
│   │  import_doc    │──▶│  解析 → 切片 → 向量化 → 入库                  │   │
│   │  种子灌库 seed  │   └────────────────────────────────────────────┘   │
└───────┬───────────┴──────────────────────────────────────────────────────┘
        │
        │  调用
        ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ Mock 内部系统    │   │ PostgreSQL     │   │ Chroma        │   │ MinIO         │
│ (mock_api,:8001)│   │ (:5432)       │   │ (向量库,进程内) │   │ (:9000)       │
│ 员工/考勤/订单   │   │ documents/     │   │ data/chroma    │   │ 原始文件存储    │
│ + 当前时间工具    │   │ chunks/chat_logs│   │               │   │               │
└───────────────┘   └───────────────┘   └───────────────┘   └───────────────┘
```

### 2.2 查询工作流

```
用户消息
   │
   ▼
node_route ──LLM 判断意图:knowledge / tool / refuse──▶ refuse → 硬拒答
   │                                                   ("文档里没找到…")
   │ knowledge(并行两路检索)
   ├──────────────┬────────────────┐
   ▼              ▼                │
向量检索(dense)   HyDE 检索         │  (web 通道已下线)
   │              │                │
   └──────┬───────┘                │
          ▼                        │
node_rrf(RRF 融合) ────────────────┼─── node_tool_agent(bind_tools,模型自主决策)
          │                        │        员工 / 考勤 / 订单 / 当前时间
          ▼                        │
node_rerank(截断重排, TOP_K)        │
          │                        │
          ▼                        ▼
node_answer_output ────── LLM 生成带引用答案(流式) ◀─── 工具结果
          │
          ▼
SSE 事件流:status / delta / citation / done / error
```

### 2.3 文档导入工作流

```
上传(md/txt/pdf/docx)
   │
   ▼
node_entry ──校验扩展名 / 写入本地备份 / MinIO──▶ 按扩展名路由
   │
   ├── pdf  ──▶ node_pdf_to_md   ─┐
   ├── docx ─▶ node_word_to_md   ─┼──▶ node_document_split(按标题智能切片,带字符定位)
   └── md/txt ──────────────────▶ ┘
                                          │
                                          ▼
                              node_bge_embedding(确定性稠密向量,1024 维)
                                          │
                                          ▼
                              node_import_milvus(PG 落 chunk + Chroma 落向量)
                                          │
                                          ▼
                              状态机:indexing → indexed / failed
```

---

## 三、目录结构

```
XiaoSu/
├── server/                  # FastAPI 后端
│   ├── app.py               #   应用入口(日志落盘、CORS、路由挂载)
│   └── routes/
│       ├── chat.py          #   POST /api/chat —— SSE 流式问答
│       └── im_webhook.py    #   IM 回调入口(钉钉,开发中)
├── im/                      # IM 集成(平台无关适配层,开发中)
│   ├── handler.py           #   统一消息处理(平台无关)
│   ├── session.py           #   会话存储(用户 ID + 会话维度隔离)
│   └── channels/
│       └── dingtalk.py      #   钉钉机器人适配器
├── processor/               # 核心处理逻辑
│   ├── db.py                #   PostgreSQL 数据层(documents/chunks/chat_logs/settings)
│   ├── embed.py             #   确定性稠密向量(1024 维,jieba + bigram)
│   ├── settings.py          #   全局配置
│   ├── import_processor/    #   文档导入管线(LangGraph)
│   │   ├── ingest.py        #     导入门面:去重/替换/状态机/种子灌库
│   │   ├── io_paths.py      #     doc_id 与本地路径管理
│   │   ├── main_graph.py    #     导入工作流编排
│   │   └── nodes/           #     entry / pdf→md / word→md / split / embed / import
│   └── query_processor/     #   查询管线(LangGraph)
│       ├── service.py       #     SSE 门面 + 引用解析 + 异常归一
│       ├── retrieval.py     #     向量检索
│       ├── main_graph.py    #     查询工作流编排
│       ├── prompt/          #     answer / item_name_recognition 提示词
│       └── nodes/           #     route / search / hyde / rrf / rerank / answer / tool_agent
├── mock_api/                # 内部系统 Mock 服务(:8001)
│   └── app.py               #   员工 / 考勤 / 订单,确定性生成
├── frontend/                # 管理后台(Next.js 15 + React 19 + Tailwind 4)
│   └── app/
│       ├── page.tsx         #   对话页(可用)
│       ├── docs/            #   文档管理(待接入)
│       ├── logs/            #   对话日志(待接入)
│       ├── settings/        #   设置(待接入)
│       └── doc/[id]/        #   引用原文页(待接入)
├── config/                  # 各模块配置单例(llm / chroma / minio / mineru / embedding)
├── utils/                   # 通用工具(llm / chroma / minio / mineru / embedding)
├── tool/                    # 日志工具
├── data/                    # 运行时数据(seed 种子文档 / chroma 向量库)
├── logs/                    # 运行日志
├── test/                    # 测试脚本
├── docker-compose.yml       # 基础设施编排(PostgreSQL + MinIO)
├── pyproject.toml           # Python 依赖(uv)
└── .env.example             # 环境变量模板
```

---

## 四、技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 语言 / 运行时 | Python ≥ 3.12 · TypeScript | 后端 uv 管理,前端 pnpm 管理 |
| 后端框架 | FastAPI · Uvicorn | SSE 流式问答接口 |
| 工作流编排 | LangGraph(LangChain) | 导入 / 查询两条状态机工作流 |
| 大模型 | Qwen(阿里云百炼 DashScope,OpenAI 兼容) | `qwen-plus`,温度/模型可配置 |
| 向量库 | Chroma(进程内持久化) | 稠密向量检索,`data/chroma` |
| 元数据库 | PostgreSQL 16 | documents / chunks / chat_logs / settings |
| 对象存储 | MinIO | 原始文件存储(pdf/docx/md/txt) |
| 文档解析 | MinerU 在线 API | PDF / Word → Markdown |
| 向量化 | 确定性稠密向量(1024 维) | jieba 词级 + 字符 bigram,L2 归一化,可离线复现 |
| 前端 | Next.js 15 · React 19 · Tailwind 4 | 管理后台 + 调试聊天页 |
| 容器编排 | Docker Compose | 一键起 PostgreSQL + MinIO |
| 文本处理 | jieba · langchain-text-splitters · pypdf · mammoth | 切片与格式解析 |

---

## 五、快速开始(安装)

### 5.1 环境要求

- Python ≥ 3.12,且已安装 [uv](https://docs.astral.sh/uv/)
- Node.js ≥ 20,且已安装 [pnpm](https://pnpm.io/)
- Docker(用于 PostgreSQL + MinIO 基础设施)

### 5.2 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`,至少配置:

| 变量 | 说明 |
|---|---|
| `OPENAI_API_KEY` | 模型 API Key(百炼 DashScope 等 OpenAI 兼容服务) |
| `OPENAI_API_BASE` | 兼容模式 Base URL |
| `POSTGRES_*` | PostgreSQL 连接信息(与 docker-compose 默认值一致即可) |
| `MINIO_*` | MinIO 连接信息 |
| `DINGTALK_APP_KEY/SECRET` | 钉钉机器人凭据(IM 接入完成前可留空) |

> ⚠️ `.env` 已被 `.gitignore` 忽略,**严禁提交到仓库**。

### 5.3 启动基础设施

```bash
docker compose up -d
# 启动 PostgreSQL(:5432)与 MinIO(:9000 / :9001),首次会自动建桶
```

### 5.4 安装依赖

```bash
uv sync                 # Python 后端依赖(使用项目内 .venv)
cd frontend && pnpm install && cd ..
```

### 5.5 灌入种子文档

知识库为空时,一键灌入 `data/seed/` 下的示例文档(员工手册 / 新人入职指南 / FAQ):

```bash
uv run python -c "from processor.import_processor.ingest import seed_from_directory; print(seed_from_directory())"
```

> 已实现"同名同内容去重、同名不同内容替换",重复执行不会重复导入。

### 5.6 启动服务

```bash
# 终端 1:后端(SSE 问答接口)
uv run uvicorn server.app:app --host 0.0.0.0 --port 8000

# 终端 2:Mock 内部系统(员工 / 考勤 / 订单)
uv run uvicorn mock_api.app:app --host 0.0.0.0 --port 8001

# 终端 3:前端管理后台(对话页可用;文档管理/日志/设置待接入)
cd frontend && pnpm dev    # http://localhost:3000
```

### 5.7 验证服务

```bash
curl http://localhost:8000/api/health        # 后端 {"status":"ok"}
curl http://localhost:8001/api/health        # Mock  {"status":"ok"}
curl http://localhost:8001/api/employee/001  # Mock 员工数据
```

---

## 六、使用

### 6.1 Web 端对话

浏览器打开 `http://localhost:3000`,在对话页提问:

- 知识类(需先灌种子文档):「员工每年有几天年假?」「报销发票需要什么材料?」
- 工具类:「员工 001 是哪个部门的?」「现在几点?」「上周一共多少订单?」
- 多轮:「再详细讲讲」「换种方式说」

答案以流式呈现,引用以【N】链接展示(原文页待接入)。

### 6.2 后端 API

**`POST /api/chat`** —— SSE 流式问答,IM 与 Web 复用同一查询门面。

请求:

```json
{
  "session_id": "demo-001",
  "user_id": "web",
  "platform": "web",
  "message": "员工每年有几天年假?",
  "history": []
}
```

响应为 `text/event-stream`,事件类型:

| 事件 | 数据 | 说明 |
|---|---|---|
| `status` | `{message}` | 阶段状态(理解中 / 执行 node) |
| `delta` | `{text}` | 流式生成的分片 |
| `citation` | `{citations}` | 引用列表(文件 / 原文片段 / 定位) |
| `done` | `{answer, citations, usage}` | 完成,含 token 消耗 |
| `error` | `{message, kind}` | 友好错误(auth / rate / timeout / engine),HTTP 200 |

> 异常一律归一为 `event: error` 并返回 HTTP 200,绝不裸 500。

### 6.3 Mock 内部系统

| 接口 | 说明 |
|---|---|
| `GET /api/employee/{emp_id}` | 员工信息(姓名 / 部门 / 职位) |
| `GET /api/attendance?emp_id=001&start=&end=` | 考勤,返回 `work_days` 汇总 |
| `GET /api/orders?start=&end=` | 订单,返回 `count` / `total_amount` |

数据由「日期 + 员工 ID」确定性生成,同一天重复查询结果一致;缺省时间取最近一周,方便验证"上周/本周"类问题。

### 6.4 自动化测试

```bash
uv run python test/_tmp_test_b1.py   # Word 转换流程自测(临时脚本)
uv run python chroma_test.py          # Chroma 增删查自测
```

> 结构化 pytest 用例(含 Mock LLM)在 Roadmap 中。

---

## 七、Roadmap

按笔试题验收清单排序,已实现 / 进行中 / 计划:

**✅ 已完成**

- [x] 文档知识库数据层:md / txt / pdf / docx 导入管线,索引状态机 `pending / indexing / indexed / failed`
- [x] 同名去重与替换(sha256),替换时清理旧向量与元数据
- [x] 智能问答:RAG 路由 + 双路检索(向量 / HyDE)+ RRF 融合 + 重排 + 带引用生成
- [x] 流式输出(SSE 逐分片)
- [x] 拒答机制(路由拒答 + 相关性阈值硬拒答 + 提示词兜底)
- [x] 工具调用:模型自主决策,4 个工具(员工 / 考勤 / 订单 / 当前时间)+ Mock 内部系统
- [x] 配置外置(环境变量 + `.env.example`)、日志落 `logs/`、`.env` 不入库

**🚧 进行中**

- [ ] Web 管理后台:文档上传 / 列表 / 删除(`/api/docs`),打通 `import_document`
- [ ] Web 管理后台:对话日志落库(`insert_chat_log`)+ 查询接口 + `/logs` 页(含 token / 工具调用)
- [ ] 引用原文页:`/doc/{doc_id}` 后端接口 + 前端高亮定位

**📋 计划**

- [ ] 钉钉 Stream 机器人接入:消息收发、验签、群 @ / 私聊、引用卡片、错误兜底
- [ ] 会话管理:按 `user_id + session_id` 隔离上下文,服务端持久化(IM 与 Web 共用)
- [ ] 一键启动脚本 `scripts/start.sh` + `docker-compose` 纳入应用服务
- [ ] 自动化测试:≥3 条 pytest,其中 ≥1 条 Mock LLM 不依赖真实 API
- [ ] 模型超时 / 重试 / 降级兜底
- [ ] 设置页:运行时切换模型、查看 IM 接入状态
- [ ] 加分项:Token / 成本展示、多模型适配、MCP Server、Evals 评测脚本、可观测性

---

## 八、工程规范

- Python 依赖用 **uv** 管理,虚拟环境 `.venv`,禁止 `pip install`
- 前端用 **pnpm**,ESM(`"type": "module"`),禁止 CommonJS
- 数据结构强类型:Pydantic / TypedDict(后端),TypeScript 类型契约(前端,不使用 `any`)
- 单文件 ≤ 500 行,单目录 ≤ 8 个文件
- 启动 / 测试 / 部署命令统一收敛到 `scripts/*.sh`(规划中)

---

## 九、License

开源协议见 [LICENSE](LICENSE)(未选择前默认保留所有权利)。

---

*「小苏」—— 让公司知识触手可及。*
