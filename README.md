# MediaHarbor

MediaHarbor 是一个本地、单用户、Windows x64 优先的 Agent Skill 源码仓库，用于从已有文案采集视频素材。

## 定位

- 当前只正式支持 **Windows x64**（Ubuntu CI 仅验证纯 Python 测试可运行，不代表 Linux 平台支持）。
- 运行要求：Windows x64、**Python 3.11+**，以及按 `download-tools/tools.json` 配置的本地第三方工具。
- 面向操作者控制的本地单用户实验性工作区；不是公共任意 URL 下载服务。
- 便携部署：克隆整个仓库即可使用，不采用传统安装方式。

## 部署

1. 将整个仓库克隆到 Agent 工作区。
2. 运行 `python scripts/fetch_tools.py` 从项目 Release 获取已验证工具（下载 → sha256 校验 → 解压到 `download-tools/`）。也可 `python scripts/fetch_tools.py --check` 查看状态、`--check-updates` 查询上游新版本。
3. 无需 `pip install`，直接运行 `skill/mediaharbor/scripts/` 下的脚本或 `python mediaharbor.py`。

工具清单与哈希见 [`tools-manifest.json`](tools-manifest.json)；工具更新流程见 [`docs/tool-update-process.md`](docs/tool-update-process.md)。无官方独立 Windows 二进制的工具（yutto / streamlink / gallery-dl）不作为发布资产，按 fetch 脚本指引 pip 安装。

## Agent 入口

1. [`AGENT_READ_ME_FIRST.md`](AGENT_READ_ME_FIRST.md)
2. [`skill/mediaharbor/SKILL.md`](skill/mediaharbor/SKILL.md) — 唯一权威 Skill 文档（触发条件、工作流、工具检查、状态码、安全边界、失败处理）

首次执行时在仓库根目录自动创建 `output/`，所有素材产物写入 `output/<project-name>/`，报告位于 `output/<project-name>/reports/`。

统一 Agent 面向 CLI（Windows x64 本地工作区）：`python mediaharbor.py`，命令包括 `check-tools`、`project-create <name>`、`candidate-add <project> <url>`（候选先 probe 并做 provenance 评分，低于阈值时挂起，可用 `--override` 强制入队）、`process <project>`、`status <project>`、`run --project <name> --url <url>`；全部输出固定 JSON 结构（`ok` / `status` / `data` / `error`）。`skill/mediaharbor/scripts/` 下的内部脚本为兼容/内部入口，不属于正常 Skill 工作流（其中 `download.py` 为 legacy/internal，`probe.py` 为内部诊断入口）。

## 主要限制

- 只正式支持 Windows x64；Linux/macOS 路径不做承诺。
- 无内置搜索引擎（搜索由 Agent 完成）、无视频内容理解、无自动剪辑/时间线。
- 不保存凭据；不绕过 DRM、付费墙、登录或区域限制；不修改 `download-tools/` 中的文件或二进制。
- 真实下载能力取决于本机第三方工具、网站状态和路由配置；下载成功不代表素材适合剪辑，版权与最终剪辑由人工负责。

## Development

开发本仓库的编码 Agent 和贡献者参见 [`AGENTS.md`](AGENTS.md) 和 [`CONTRIBUTING.md`](CONTRIBUTING.md)。
验证入口：`scripts/validate.sh`（Windows 等价：`scripts/validate.ps1`）。

## License

This project is licensed under the [MIT License](LICENSE).
