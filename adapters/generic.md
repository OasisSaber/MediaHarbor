# Generic Adapter：Harness 映射

> 本文件规定 TheMasterplan 核心规则到任意 Agent Harness 的通用映射，
> 是 `adapters/` 层的基线与参考实现。`adapters/trellis.md` 等具体 Adapter
> 按本文件的映射键实现；Harness 特有内容只进 Adapter，不进 Core。
>
> Core 不依赖任何特定 Harness；Harness 不复制 Core 规则，只映射。

## 1. 映射键

AW 核心概念与 Harness 生命周期元素的对应关系：

| AW 核心（core/） | Harness 通用元素 |
|---|---|
| 复杂任务（Issue） | 任务文档 / PRD（含目标、范围、验收条件、排除项） |
| 任务 change + bookmark | 任务分支 / 任务工作区（不维护长期开发分支） |
| 权威验证入口 | 门控验证步骤（lint / typecheck / test 的等价物） |
| 完整 diff 审阅 | 变更审查步骤（diff vs 任务范围） |
| 自审与交接 | 完成前检查清单（范围、验证、已知限制） |
| Pull Request + 人类 Squash Merge | 审查对象 + 人工合并门（Agent 不自行合并） |
| 聚合授权与发布事务 | 外部写操作门（core/policy.md 不变，跨平台生效） |

## 2. 映射规则

- **任务来源**：复杂任务必须有记录目标、范围、验收条件和排除项的任务文档；
  小型低风险任务必须记录当前会话授权来源。无编号不得伪造。
- **单一交付责任人**：允许研究、实现、检查子代理与多个模型参与，但只能
  有一个主交付责任人控制任务最终范围、VCS、最终验证、push、Pull Request、
  发布授权执行与人类交接；子代理不得独立 push、创建或修改 Pull Request、
  merge、release、deploy、删除远端资源或扩大任务范围。
- **验证真实性**：Harness 的验证步骤必须调用项目权威验证入口，不得声明
  不存在的入口；失败必须修正并重跑，不得表述为成功。
- **diff 审阅**：Harness 的审查步骤必须覆盖完整 diff（范围、误删、临时
  文件、无关生成物、失效引用）。
- **人工门**：合并、发布、删除远端数据等外部操作必须由人类决定；Agent
  获批后按 core/policy.md 连续执行。
- **不复制规则**：Adapter 只写"如何映射"，不复制 Core/Profile 的规则正文。

## 3. 通用生命周期

```text
任务文档（Issue/PRD）
→ 任务 change
→ 实现（不提交不可逆外部操作）
→ 权威验证
→ 完整 diff 审阅与自审
→ 审查对象（PR 或等价物）
→ 人类决定合并
→ 清理
```

## 4. 边界

- Adapter 不改变 core/policy.md 的授权语义；
- Adapter 不改变 profiles/ 的发布命令；
- Harness 无法提供的环节（如无 PR 机制的平台）由 Adapter 说明替代方式，
  不降级人工门。
