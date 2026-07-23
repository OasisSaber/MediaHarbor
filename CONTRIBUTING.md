# Contributing to MediaHarbor

开始前读取 [AGENTS.md](AGENTS.md)。Agent 操作遵循 AgenticWonderwall 工作流。

## 两条任务路径

### 复杂任务

创建一个 GitHub Issue 记录目标、范围、验收条件和排除项，然后：

```bash
jj git fetch
jj new main -m "issue #<number>: <single outcome>"
jj bookmark create codex/issue-<number>-<short-name> -r @
```

### 小型低风险任务

在当前会话中取得明确人类授权后：

```bash
jj new main -m "authorized task: <single outcome>"
jj bookmark create codex/task-<short-name> -r @
```

## 实现与验证

只修改任务范围内的文件。验证入口：

```bash
bash scripts/validate.sh
```

Windows 等价：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate.ps1
```

push 前运行：

```bash
jj status
jj diff
jj diff --stat
jj log -r "main..@"
```

## Pull Request

Reader 阅读完整 diff 确认无范围外变更、误删、临时文件、缓存或无关生成物。验证失败时修正并重跑。

创建 Draft PR，正文包含关联 Issue、实现结果、变更内容、验证证据、已知限制和未覆盖内容。

Agent 完成自审后可 push 和创建/更新 Pull Request。只有人类可以决定是否 Squash Merge。

Agent 不得自行 merge 或 release。
