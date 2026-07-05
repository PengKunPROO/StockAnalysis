# 多 Agent 协作流程设计

> 2026-07-06 | git worktree + branch + merge

## 1. 问题

Hermes Agent 和 OpenCode Agent 同时在 main 分支修改代码，导致：
- 代码互相覆盖
- 端口/配置冲突（如 8002→8003 回退）
- 测试防线无法防止代理间的运行时冲突

## 2. 方案：git worktree 隔离开发

每个 Agent 在自己的 worktree 中开发，独立目录、独立分支。

```
D:\AI\hermesStockAgent\              ← 主仓库 (main, 用户)
D:\AI\hermes-worktrees\<feature>\    ← Agent 独立工作区
```

## 3. 流程

```
接到任务
  ↓
git worktree add ../hermes-worktrees/<feature> -b feat/<feature>
  ↓
在 worktree 中开发 + 测试 (verify.sh)
  ↓
完成 → git push origin feat/<feature>
  ↓
用户审批 (查看 commit diff)
  ↓
git checkout main && git merge feat/<feature> && git push
  ↓
git worktree remove ../hermes-worktrees/<feature>
```

## 4. 命名规范

- 分支: `hermes/<feature>` 或 `opencode/<feature>`
- worktree 目录: `D:\AI\hermes-worktrees\<feature>\`

## 5. 规则

- Agent 只在 worktree 中修改代码
- 禁止 Agent 直接修改 main 分支
- 合并前必须跑 `verify.sh` 全绿
- 合并后立即删除 worktree
- 用户始终在 main 上操作 `start.bat`

## 6. 初始目录结构

```
D:\AI\hermesStockAgent\          ← main (用户 + opencode)
D:\AI\hermes-worktrees\          ← Hermes Agent 工作区
  ├── feat-news\                 (示例)
  └── fix-port\                  (示例)
```
