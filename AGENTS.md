# MediaHarbor Agent Workflow

> 本文件是本仓库唯一入口：定义加载顺序与分域权威，不复制规则正文。
> 规则分布：
> - 任务来源、工作区检查、验证真实性、diff 审阅、自审与交接：[core/workflow.md](core/workflow.md)
> - 权限与聚合授权、外部写操作边界、人类审批门、发布事务、安全停止条件：[core/policy.md](core/policy.md)
> - Git 发布执行命令：[profiles/git.md](profiles/git.md)
> - Harness 映射：[adapters/generic.md](adapters/generic.md)
> 各层通过链接引用，不复制同一规则。README、CONTRIBUTING、采用指南和其他
> 材料只能解释或辅助执行，不能覆盖本文件及其引用的规则。

## 项目事实

- 项目名：MediaHarbor
- 项目目标：维护一个工作区内便携式 Agent Skill 工具包，帮助 Agent 根据已有文案检索、下载、验证并整理视频素材
- 技术栈：Python 3.11+、外部下载工具 CLI、FFmpeg/ffprobe、JSON/JSONL、Markdown
- 默认分支：`main`
- 工具基线：Git `2.34.0` 或更高版本
- 平台状态：正式支持 Windows x64；Ubuntu GitHub Actions 仅表示纯 Python 测试可运行，不是 Linux 平台支持声明
- 验证入口：
  ```bash
  bash scripts/validate.sh
  ```
  PowerShell 等价入口（独立实现相同检查）：
  ```powershell
  pwsh -NoProfile -File scripts/validate.ps1
  ```
- 合并方式：只接受人类决定的 Squash Merge
- 工作流来源：TheMasterplan v3.0.0（https://github.com/OasisSaber/TheMasterplan）
- 采用日期：2026-08-03
- GitHub Actions 消费者接口：`.github/workflows/check.yml` 的 `aw-check` job 通过
  `uses: OasisSaber/TheMasterplan/.github/workflows/aw-check.yml@v1` 调用中央可重用
  工作流，`project-check-path` 固定为 `scripts/ci-check.sh`（CI 入口：先安装
  pytest/ruff 验证依赖——中央接口不安装调用方依赖——再调用权威验证入口
  `scripts/validate.sh`）

采用时本文件与 `core/`、`profiles/`、`adapters/` 组成 TheMasterplan 采用集；
验证入口、平台声明与消费者接口按本项目实际情况记录，不复制 TheMasterplan
仓库自身的发布与版本通道治理内容。

## 权威顺序

1. 系统安全、法律与平台权限
2. 项目安全、隐私、合规和数据保护要求
3. 受保护分支、发布、部署和破坏性操作限制（授权语义见 [core/policy.md](core/policy.md)）
4. 根部 `AGENTS.md` 及其引用的 `core/` 规则
5. 当前 Issue 或明确人类授权
6. 项目架构、测试和交付资料
7. README、CONTRIBUTING、采用指南和其他辅助材料

当前 Issue 或明确人类授权只能定义任务目标、范围和验收条件，不能覆盖安全、隐私、合规、数据保护、受保护分支、发布、部署或破坏性操作限制。

## 加载顺序

开始工作前按以下顺序加载：

1. 根部 `AGENTS.md`（本文件）；
2. [core/workflow.md](core/workflow.md)（任务来源、工作区、验证、自审）；
3. [core/policy.md](core/policy.md)（授权与发布）；
4. 项目采用的 [profiles/git.md](profiles/git.md)（Git 命令）与
   [adapters/generic.md](adapters/generic.md)（Harness 映射）；
5. 当前 Issue 或明确人类授权。

## 任务路径

复杂任务与小型低风险任务的路径、适用范围与授权记录要求见
[core/workflow.md](core/workflow.md) §1。无 Issue 时不得伪造编号；实现需要
扩大范围时必须停止，向人类说明原因并转为 Issue 路径。

## 验证与交付

工作区检查、任务 change 卫生、权威验证、完整 diff 审阅与 Agent 自审要求见
[core/workflow.md](core/workflow.md) §2-§6。每次 push 前必须运行权威验证
入口：

```bash
bash scripts/validate.sh
```

PowerShell 等价入口独立实现相同检查（Ruff format/lint + pytest + 冒烟测试）：

```powershell
pwsh -NoProfile -File scripts/validate.ps1
```

验证失败时必须修正并重跑，不得把失败或未验证状态表述为成功。fetch 后发现
`main`、`main@origin` 或任务 bookmark 冲突时必须停止，不得猜测目标、自动
解决或 push。审查意见只使用三类表述：合并前必须修复、建议本次修复、可以
后续处理。

## 人工批准与聚合授权

人类保留最终决定权，不表示人类必须亲自操作。Agent 不得未经批准执行
merge、release、删除远端数据、破坏性操作或扩大范围；取得人类明确批准后，
Agent 可在批准范围内连续执行，不得把可由自身工具完成的操作转交人类手工
执行。

发布采用单一最终授权门，聚合授权的定义、审核要素、失效条件、部分失败处理
与术语对照见 [core/policy.md](core/policy.md)；Git 下的安全执行方式见
[profiles/git.md](profiles/git.md)。

Agent 不得把允许 push 或创建 Pull Request 解释为允许 merge 或 release。

## 安全与卫生

- 不提交密钥、访问令牌或明显的私人数据。
- 不提交本机绝对路径、缓存、临时文件或无关生成物。
- `main` 只接受经 Pull Request 的人类决定 Squash Merge。
- 发现当前操作违反已记录规则、权限或范围时，必须在产生外部影响前停止并请求人类修正或明确授权。
