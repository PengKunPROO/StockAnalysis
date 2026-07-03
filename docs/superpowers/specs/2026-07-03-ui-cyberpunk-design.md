# UI 4.0 设计 — 赛博朋克暗黑终端

> 2026-07-03 | 深蓝黑底 + 蓝青/品红霓虹 | 左6右4分栏

## 1. 布局架构

```
┌──────────────────────────────────────────────────────────┐
│ TopBar: [☰] Stock Agent  [搜索框...            ] [⚙]   │
├────┬──────────────────────────┬──────────────────────────┤
│ 40 │  Price: 贵州茅台 ¥1203   │  Skill: [股票分析▼]     │
│ px │  ┌──────────────────┐   │  ─────────────────────   │
│ 图 │  │  K线图 45vh       │   │  Chat Messages          │
│ 标 │  │  成交量副图       │   │  (流式Markdown)         │
│ 栏 │  └──────────────────┘   │                         │
│    │  VOL MACD RSI KDJ BOLL  │                         │
│ ho │  ─────────────────────  │                         │
│ ve │                         │  [__________] [发送]     │
│ r  │                         │                         │
└────┴──────────────────────────┴──────────────────────────┘
     ←───── ~60% ──────→          ←─── ~40% ───→
```

- **TopBar:** 汉堡(侧栏) + Logo + 搜索 + Skill管理
- **IconBar (40px):** 垂直图标栏，hover 弹出自选列表覆盖层
- **Main (60%):** 价格条 + K线图(45vh) + 指标卡片横排(grid auto-fill)
- **Right (40%):** 对话面板，多轮对话，流式 Markdown

## 2. 配色

```css
--bg:        #08081a;  /* 深蓝黑底 */
--surface:   #10102a;  /* 卡片/面板 */
--border:    #1a1a3a;  /* 边框 */
--text:      #c8c8e0;  /* 主文字 */
--muted:     #6b6b8a;  /* 次要文字 */
--accent:    #00e5ff;  /* 蓝青霓虹(强调/上涨) */
--accent2:   #b44dff;  /* 紫霓虹(辅助) */
--up:        #00e5ff;  /* 涨 */
--down:      #ff3366;  /* 跌 */
--chart-bg:  #0a0a20;  /* 图表背景 */
--glow:      0 0 12px rgba(0,229,255,0.25);
```

## 3. 技术方案

**扔掉 shadcn/ui**——它引入了不必要的复杂度和依赖问题。回归纯 CSS，但用 CSS 变量 + Flexbox + Grid 做现代布局。

| 组件 | 实现 |
|------|------|
| 布局 | CSS Grid `grid-template-columns: 40px 1fr minmax(320px, 40%)` |
| 图标栏 | 40px 固定宽，flex-col，CSS hover 展开覆盖层 |
| K线图 | lightweight-charts，容器固定 `height: 45vh` |
| 指标卡 | 横排 Grid `auto-fill`，赛博边框发光效果 |
| 对话 | 独立滚动区，Markdown 渲染，左对齐气泡 |
| 搜索 | 绝对定位下拉，输入防抖 200ms |
| 图标 | Unicode 或简单 SVG，不引入 lucide-react |

**去掉的依赖:** shadcn/ui, radix-ui, lucide-react, tailwind-merge, clsx — 回归零依赖纯 CSS。

## 4. K线图修复

问题：`kline-container { height: clamp(...) }` + 内部 `height: 100%` → lightweight-charts 无法正确计算尺寸。

修复：容器用固定 `height: 45vh`，图表 `height: 100%`，父容器明确高度链。

## 5. 自适应

```css
/* 2K (2560px) */
.main { grid-template-columns: 40px 1fr minmax(380px, 42%); }

/* 1080p */
.main { grid-template-columns: 40px 1fr minmax(300px, 38%); }

/* 移动端 (< 768px) */
.main { grid-template-columns: 1fr; }
.iconbar { display: none; }
.right-panel { display: none; } /* 点击弹出 */
```

## 6. 交互

- **搜索:** 输入 → 同花顺 API → 下拉结果 → 点击选股
- **侧栏:** 40px 图标栏 hover → 200px 自选列表覆盖层
- **对话:** Skill 选择 + 输入框 + Enter 发送 + SSE 流式渲染
- **Skill管理:** 顶栏齿轮 → 弹窗（上传/删除 .md）
- **所有按钮:** title tooltip

## 7. 验收

- [ ] K线图正常显示，成交量副图正常
- [ ] 指标卡片全部展示(MACD/RSI/KDJ/BOLL/VOL/ROE/负债率)
- [ ] 2K 屏左右分栏比例正确(≈60/40)
- [ ] 暗黑赛博朋克配色完整统一
- [ ] 对话 Markdown 表格标题正确渲染
- [ ] 搜索选股 + 自选列表正常
- [ ] 移动端自适应
