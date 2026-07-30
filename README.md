# MediaHarbor

MediaHarbor 是一个放入 Agent 工作区即可使用的便携式视频素材采集工具包。它面向本地、单用户的实验性 Agent 工作流，**不采用传统安装方式**。

## 部署

### Shell package / 源码目录

将整个 `MediaHarbor/` 文件夹放入 Agent 工作区，并按 `download-tools/tools.json` 配置所需的第三方下载工具。

### Full package

Full package 可以包含第三方下载工具，但在 [Issue #27](https://github.com/OasisSaber/MediaHarbor/issues/27) 完成前，不应宣称其中二进制的来源、版本、哈希和许可证已经过完整供应链验证。

## Agent 入口

让 Agent 按顺序读取：

1. [`AGENT_READ_ME_FIRST.md`](AGENT_READ_ME_FIRST.md)
2. [`skill/mediaharbor/SKILL.md`](skill/mediaharbor/SKILL.md)
3. [`download-tools/tools.json`](download-tools/tools.json)

首次执行时在 MediaHarbor 根目录自动创建 `output/`，所有素材产物写入 `output/<project-name>/`。

## 默认工作流与信任模型

- 上层搜索 Harness 默认搜索 Bilibili 和 YouTube 的公开页面。
- Agent 可以无人值守提交候选并自动下载，不要求对每条 URL 逐项人工确认。
- Bilibili 和 YouTube 是默认搜索范围，不是 MediaHarbor 下载内核的强制域名白名单。
- MediaHarbor 仍可依据 `routing.json`、backend 和本地配置处理明确支持的其他 URL。
- MediaHarbor 仅面向操作者控制的本地单用户环境，不提供面向陌生用户的公共任意 URL 下载 API。
- 版权授权、素材使用范围和最终发布责任由实际使用方判断。

## 工作流

已有文案 → Agent 分析人物、事件、年份、地点和视觉需求 → Agent 默认从 Bilibili、YouTube 等已配置来源搜索候选页面 → Agent 将候选 URL 交给 MediaHarbor → MediaHarbor 选择并调用本地下载工具 → 下载视频、字幕、缩略图和元数据 → ffprobe 验证 → 重命名、归档和生成素材清单 → 人工审核与剪辑

## 三方角色

- **Agent / Harness**：理解文案、生成检索词、搜索和筛选候选 URL、调用 Skill，并在支持范围内自动提交下载任务。
- **MediaHarbor**：发现工具、受控调用、有限容灾、验证、整理和报告。
- **人工**：判断素材相关性、质量和版权适用性，并完成最终剪辑；人工审核不是每次下载前的安全审批门禁。

## 当前阶段

MediaHarbor 目前是实验性项目。核心的候选入队、多后端下载、媒体验证、素材归档、项目状态和报告链路已经实现，但稳定 CLI、跨平台工具解析、重试治理和部分可靠性收尾仍在迭代。

当前推荐优先使用本地 Windows 工作流。真实下载能力取决于本机第三方工具、网站状态和路由配置。实验稳定化路线见 [Issue #18](https://github.com/OasisSaber/MediaHarbor/issues/18)。

## 能力与限制

参见 [`skill/mediaharbor/references/capability-matrix.md`](skill/mediaharbor/references/capability-matrix.md)。

## Development

开发本仓库的编码 Agent 和贡献者参见 [`AGENTS.md`](AGENTS.md) 和 [`CONTRIBUTING.md`](CONTRIBUTING.md)。
本项目的 AgenticWonderwall 采纳范围、版本和仓库设置门禁记录在
[`docs/agenticwonderwall-adoption.md`](docs/agenticwonderwall-adoption.md)。

## License

This project is licensed under the [MIT License](LICENSE).
