# Contributing to AgenticWonderwall

仅在修改工作流本身时维护本仓库。开始前读取 [AGENTS.md](AGENTS.md)，并在以下两条任务路径中选择一条。

## 复杂任务

先创建 GitHub Issue，记录目标、范围、验收条件和排除项：

```bash
jj new main -m "issue #<number>: <single outcome>"
jj bookmark create codex/issue-<number>-<short-name> -r @
```

## 小型低风险任务

先在当前会话中取得明确人类授权：

```bash
jj new main -m "authorized task: <single outcome>"
jj bookmark create codex/task-<short-name> -r @
```

两条路径二选一。无 Issue 时不得伪造编号，Pull Request 必须记录授权来源、目标和范围。当前 Issue 或明确人类授权不能覆盖项目安全、隐私、合规、数据保护、受保护分支、发布、部署或破坏性操作限制。

## 实现与验证

只修改任务范围内的文件，不混入或覆盖来源不明的修改。验证入口为：

```bash
bash scripts/validate.sh
```

push 前运行：

```bash
jj status
jj diff
jj diff --stat
jj log -r "main..@"
```

阅读完整 diff，确认没有范围外变更、误删、临时文件、缓存或无关生成物。验证失败时先修正并重跑。

## Pull Request 与自审

Pull Request 应说明关联 Issue 或明确授权、实现结果、变更内容、验证证据、已知限制和未覆盖内容。

Agent 完成自审后可以 push、创建或更新 Pull Request。只有人类可以决定是否 Squash Merge；Agent 不得自行 merge 或 release。
