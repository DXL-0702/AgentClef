<div align="center">

# AgentClef

**音频是证据，乐谱是状态。**

一个 AI Agent 辅助扒谱审校工作台：将音频转化为可编辑乐谱初稿，并帮助用户围绕每一个不确定片段进行推理、修正与确认。

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-TypeScript-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vite.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![Status](https://img.shields.io/badge/Status-v0.1_Planning-blue?style=flat-square)](./docs/v0.1/)

[English](README.md) · [简体中文](README.zh-CN.md) · [文档](./docs/README.md) · [架构](./docs/technical-architecture.md) · [v0.1](./docs/v0.1/)

</div>

---

## 为什么需要 AgentClef？

AI 扒谱工具正在越来越擅长生成第一份初稿。真正困难的是：如何把这份不完美的初稿，修成音乐人可以信任的乐谱。

AgentClef 围绕初稿之后的审校流程设计：听、看、问、比较、编辑、确认。

| 问题 | 一次性 AI 扒谱工具 | AgentClef |
| :--- | :--- | :--- |
| 节奏不确定 | 隐藏在生成结果里 | 显示为局部审校目标 |
| 音符时值错误 | 用户手动猜测并修改 | Agent 基于音频证据和节拍上下文辅助判断 |
| AI 修改 | 不透明，可能直接破坏结果 | 生成 CandidateEdit，用户确认后才应用 |
| 乐谱状态 | 导出文件或模型输出 | 结构化 DraftScore 作为系统真相 |
| 正确率目标 | 第一次生成结果的准确率 | 用户最终确认乐谱的正确率 |

## 核心理念

- **先有证据，再有记谱** — 每个音乐事件都应能追踪到音频时间与节拍位置。
- **初稿是结构化状态** — 系统内部不是 PDF、图片或临时 MIDI，而是可编辑的 DraftScore。
- **Agent 是审校助手，不是状态拥有者** — Agent 负责解释和提出修改建议，系统维护乐谱状态，用户确认最终修改。
- **局部推理优先于全局猜测** — 用户选择音符、小节、和弦或时间片段，Agent 围绕该局部上下文进行分析。
- **通过审校提高正确率** — AgentClef 关注用户多快能得到正确终稿，而不只关注第一次生成结果。

## 系统架构

这里展示的是高层架构快照。完整系统设计以 [docs/technical-architecture.md](./docs/technical-architecture.md) 为准。

```
┌─────────────────────────────────────────────────────────────────┐
│                         音乐人工作流                             │
│   上传音频 → 乐谱初稿 → 局部审校 → 用户确认后的可用乐谱           │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │     React + Vite 工作台      │
              │ waveform · note timeline ·   │
              │ Agent panel · edit preview   │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │       FastAPI 后端服务       │
              │ project · task · draft ·     │
              │ Agent context · edit engine  │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │     PostgreSQL + Redis       │
              │ DraftScore · revisions ·     │
              │ job queue · task state       │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │       Celery Worker          │
              │ FFmpeg → librosa → Basic     │
              │ Pitch → postprocess          │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │      LLM Provider Adapter    │
              │ local context → structured   │
              │ CandidateEdit proposals      │
              └─────────────────────────────┘
```

## 技术栈

完整技术栈职责说明以 [docs/technology-stack.md](./docs/technology-stack.md) 为准。

| 模块 | 技术选型 |
| :--- | :--- |
| **工作台** | React + TypeScript + Vite |
| **前端状态** | TanStack Query + Zustand |
| **后端** | Python 3.12+ + FastAPI + Pydantic |
| **持久化** | PostgreSQL + SQLAlchemy + Alembic |
| **任务** | Redis + Celery |
| **音频 / Agent** | FFmpeg + librosa + Basic Pitch + LLM provider adapter |

## 工作流预览

```text
1. 上传本地音频
   → AgentClef 创建 Project、AudioAsset 和 TranscriptionJob

2. 生成结构化初稿
   → worker 构建 BeatGrid、NoteEvent、可选 ChordEvent 和不确定点标记

3. 在工作台中审校
   → waveform 与可编辑 note timeline 围绕同一个 DraftScore 对齐

4. 向 Agent 询问局部问题
   → “这里的高音应该给几拍？”

5. 确认 CandidateEdit
   → Edit Engine 校验修改建议，更新 DraftScore，并写入 Revision
```

## 项目结构

v0.1 目标结构：

```
AgentClef/
├── docs/        # 产品、架构、模型与里程碑文档
├── server/      # FastAPI 后端
├── worker/      # Celery tasks 与音频 pipeline
├── web/         # React + Vite 工作台
├── shared/      # 共享 schema contract 或生成类型
└── tests/       # 后端、pipeline、contract 与 E2E 测试
```

`AGENTS.md` 是本地协作规范文件，不作为公开项目文档的一部分。

## 路线图

| 里程碑 | 状态 | 核心内容 |
| :--- | :--- | :--- |
| **v0.1** | 规划中 | 本地音频上传、异步初稿生成、时间线审校、Agent CandidateEdit 确认 |
| **v0.2** | 计划中 | 音频-谱面同步、循环播放、不确定点导航、候选对比 |
| **v0.3** | 计划中 | 正确率 fixture、模型 adapter 评测、节拍与量化后处理增强 |
| **v0.4** | 计划中 | 项目生命周期、Revision 浏览、MIDI 与 MusicXML 导出基线 |
| **v0.5** | 计划中 | 和弦时间线、移调、乐器模式、分轨辅助审校研究 |
| **v1.0** | 计划中 | 稳定的 AI Agent 辅助扒谱审校工作台 |

## 本地开发

> AgentClef 当前处于 v0.1 规划到实现前的阶段。以下命令描述 `project-foundation` 完成后的目标本地开发流程。

```bash
# 后端
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn server.main:app --reload

# Worker
celery -A worker.app:celery_app worker --loglevel=info

# 前端
cd web
npm install
npm run dev
```

质量闸门：

```bash
# 后端
pytest
ruff check .

# 前端
npm run test
npm run build

# E2E
npx playwright test
```

## 文档

- [产品定位](./docs/product-positioning.md)
- [技术架构](./docs/technical-architecture.md)
- [技术栈](./docs/technology-stack.md)
- [数据模型](./docs/data-model.md)
- [Agent 编辑协议](./docs/agent-edit-protocol.md)
- [正确率策略](./docs/accuracy-strategy.md)
- [竞品启发](./docs/competitive-insights.md)
- [v0.1 架构](./docs/v0.1/architecture.md)

## 开发流程

AgentClef 采用 issue 级开发流程。本地协作规范保存在 `AGENTS.md` 中，该文件不作为公开文档发布。

1. 编码前确认 issue 目标、范围、实现要点、测试计划和验收标准。
2. 只在已确认 issue 边界内实现。
3. 交付前运行本地质量闸门。
4. 遵循 Conventional Commits。
5. `git commit` 和 `git push` 由开发者亲自执行。

## 当前开发版本

AgentClef 当前处于 **v0.1**：最小扒谱审校闭环。

- [v0.1 文档](./docs/v0.1/)
- [v0.1 架构](./docs/v0.1/architecture.md)

---

<div align="center">

**AgentClef** — 让每一个不确定音符都可被审校。

</div>
