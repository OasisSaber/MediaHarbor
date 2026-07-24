# AgenticWonderwall 采纳记录

## 版本记录

- 来源：[OasisSaber/AgenticWonderwall](https://github.com/OasisSaber/AgenticWonderwall)
- 版本：v1.0.0
- 采用日期：2026-07-30
- 授权来源：[Issue #30](https://github.com/OasisSaber/MediaHarbor/issues/30)
- 首次演练任务：[Issue #30](https://github.com/OasisSaber/MediaHarbor/issues/30)

## 采纳映射

### 工作区

- 仓库使用 Git 与 Jujutsu colocated 工作区。
- 根部 [`AGENTS.md`](../AGENTS.md) 是唯一具有约束力的通用工作流规则来源。
- 每个任务使用一个可验证的 jj change 和短生命周期 bookmark。
- `.claude/goal/` 属于本机 Agent 运行状态，不进入版本控制。

### 项目

- [`AGENTS.md`](../AGENTS.md) 记录 MediaHarbor 的项目目标、技术栈、默认分支和验证入口。
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) 解释 Issue 与明确人类授权两条任务路径。
- [`scripts/validate.sh`](../scripts/validate.sh) 是 push 前的权威验证入口；
  [`scripts/validate.ps1`](../scripts/validate.ps1) 提供 Windows 等价验证。
- [Pull Request 模板](../.github/pull_request_template.md) 要求真实 Issue 或完整的明确人类授权二选一，并记录验证与 Agent 自审。
- [GitHub Actions](../.github/workflows/check.yml) 在 Ubuntu 和 Windows 上执行项目验证。

### GitHub 仓库

GitHub Template Repository 不会复制服务器端设置，仓库文件也不能替代它们。2026-07-30
通过 GitHub API 对服务器设置进行了只读审计：

- 默认分支是 `main`；
- active 的 `main-protection` ruleset 作用于默认分支；
- `main` 只能通过 Pull Request 修改，并要求解决 review threads；
- 严格要求 `check-ubuntu` 与 `check-windows` 两项状态检查通过；
- ruleset 禁止删除与 non-fast-forward 更新，并要求线性历史；
- ruleset 只允许 Squash Merge；
- ruleset 没有 bypass actor，当前用户不能绕过；
- auto-merge 已禁用。

仍需人类在 GitHub 中修正和核对：

- 仓库全局仍启用了 Merge Commit 与 Rebase Merge，应关闭两者，只保留 Squash Merge；
- Agent 凭据不得拥有 admin、merge 或 release 权限。

## 人工保留边界

Agent 可以在已记录范围内实现、验证、push 和创建或更新 Pull Request。merge、release、
远端数据删除、受保护分支规则与权限变更始终由人类单独决定。
