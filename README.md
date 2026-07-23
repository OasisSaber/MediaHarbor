# AgenticWonderwall

A minimal single-Agent workflow for GitHub and Jujutsu.

AgenticWonderwall 是面向个人开发者的单 Agent 工作流，是 GitHub Flow 与 Jujutsu 的轻量适配层，也是可复制的规则模板与稳定版本接口。

它不是 Agent 服务、多 Agent 编排平台、Web 或 API 服务、CLI 产品、Agent 运行时、自动发布机器人或项目管理系统。

## 稳定接口

| 用途 | 入口 |
| --- | --- |
| Agent 入口 | [AGENTS.md](AGENTS.md) |
| 人类入口 | [README.md](README.md) |
| 维护入口 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 采用指南 | [docs/adoption-guide.md](docs/adoption-guide.md) |
| 验证入口 | `bash scripts/validate.sh` |
| 复制接口 | GitHub Template Repository |
| 版本接口 | Git tag / GitHub Release |

## 快速开始

1. 使用 GitHub Template Repository 创建新仓库，或只复制 `AGENTS.md`。模板只复制仓库文件，不会复制本地 `.jj` 状态。
2. 在本地初始化 Jujutsu 工作区；二选一：

   ```bash
   # 路径 A：直接使用 Jujutsu 克隆
   jj git clone <repository-url>
   cd <repository>
   ```

   ```bash
   # 路径 B：仓库已通过 Git 克隆
   git clone <repository-url>
   cd <repository>
   jj git init --colocate
   ```

   初始化后运行：

   ```bash
   jj status
   jj git remote list
   jj log -r 'main | main@origin' -n 5
   ```

3. 在 `AGENTS.md` 的“项目事实”中填写项目目标、技术栈、验证命令和默认分支。
4. 按项目需要替换验证脚本和持续集成配置，并按 [仓库设置说明](docs/repository-settings.md) 由人类配置 GitHub 保护规则。
5. 开始新任务前运行 `jj git fetch` 同步远端基线；初始化后才能使用本工作流规定的 `jj status`、`jj new` 和 bookmark 命令。
6. 复杂任务使用 GitHub Issue 记录边界；小型低风险任务使用当前会话中的明确人类授权。
7. 使用一个 jj change 完成实现、验证与 Agent 自审，通过 Pull Request 交给人类决定是否 Squash Merge。

## 本仓库验证

```bash
bash scripts/validate.sh
```

验证入口检查 Markdown 内部链接、Shell 脚本提交模式、YAML 语法和 Shell 语法。依赖说明见 [scripts/README.md](scripts/README.md)。

## 维护边界

日常采用本工作流时，不在本仓库为业务项目创建 Issue。只有修改 AgenticWonderwall 工作流本身时，才在本仓库记录维护任务。

Agent 可以在已记录范围内实现、验证、push 和维护 Pull Request，但不得自行 merge 或 release。

## 来源

AgenticWonderwall 整理自
[OasisSaber/agentic-project-workflow](https://github.com/OasisSaber/agentic-project-workflow)
的最终接受基线。

历史研发记录保留在旧仓库。

基线提交：`ee0482d08ea6859bef2d1c06f37fa97bb25a575f`

## License

This project is licensed under the [MIT License](LICENSE).
