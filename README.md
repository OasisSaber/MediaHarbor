# MediaHarbor

MediaHarbor 是一个放入 Agent 工作区即可使用的便携式视频素材采集工具包。**不采用传统安装方式。**

## 部署

下载完整 Release，将整个 `MediaHarbor/` 文件夹放入 Agent 工作区。

## Agent 入口

让 Agent 按顺序读取：

1. [`AGENT_READ_ME_FIRST.md`](AGENT_READ_ME_FIRST.md)
2. [`skill/mediaharbor/SKILL.md`](skill/mediaharbor/SKILL.md)
3. [`download-tools/tools.json`](download-tools/tools.json)

首次执行时在 MediaHarbor 根目录自动创建 `output/`，所有素材产物写入 `output/<project-name>/`。

## 工作流

已有文案 → Agent 分析人物、事件、年份、地点和视觉需求 → Agent 跨互联网搜索候选页面 → Agent 将候选 URL 交给 MediaHarbor → MediaHarbor 选择并调用本地下载工具 → 下载视频、字幕、缩略图和元数据 → ffprobe 验证 → 重命名、归档和生成素材清单 → 人工剪辑

## 三方角色

- **Agent**：理解文案、生成检索词、搜索和筛选候选 URL、调用 Skill
- **MediaHarbor**：发现工具、受控调用、有限容灾、验证、整理和报告
- **人工**：判断镜头是否合适并完成剪辑

## 能力与限制

参见 [`skill/mediaharbor/references/capability-matrix.md`](skill/mediaharbor/references/capability-matrix.md)

## Development

开发本仓库的编码 Agent 和贡献者参见 [`AGENTS.md`](AGENTS.md) 和 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

## License

This project is licensed under the [MIT License](LICENSE).
