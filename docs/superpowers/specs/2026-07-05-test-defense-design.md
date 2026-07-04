# 测试防线设计

> 2026-07-05 | pytest + pre-push hook | 全栈回归测试

## 1. 目标

每次 `git push` 前自动跑全量回归测试，确保旧功能不被新代码破坏。新功能必须附带测试。

## 2. 架构

```
git push
  → .git/hooks/pre-push
    → bash verify.sh
      ├── 1. Backend API 回归测试 (pytest)
      ├── 2. 数据源集成测试
      ├── 3. 前端构建验证
      └── 4. 诊断端点格式验证
    → 任一失败 → push 被拒绝
```

## 3. 测试文件结构

```
backend/tests/
├── conftest.py              # Fixtures: TestClient, API key
├── test_health.py           # 健康检查
├── test_search.py           # 股票搜索
├── test_kline.py            # K线数据 + 缓存
├── test_realtime.py         # 实时行情
├── test_financials.py       # 财务指标
├── test_indicators.py       # 技术指标计算
├── test_skills.py           # Skill CRUD
├── test_watchlist.py        # 自选股 CRUD
├── test_diagnosis.py        # 诊断 SSE 格式
├── test_datasources.py      # 数据源插件
├── test_data_engine.py      # 缓存引擎
└── test_scheduler.py        # 定时任务

verify.sh                     # 一键验证脚本
frontend/                     # (tsc + vite build 已在 verify.sh 中)
```

## 4. 测试用例清单

### test_health.py
- [ ] `/api/v1/health` 返回 200, status=ok
- [ ] datasources 包含 tonghuashun
- [ ] database=connected

### test_search.py
- [ ] `?q=600519` 返回贵州茅台
- [ ] `?q=贵州茅台` 返回结果
- [ ] 空搜索返回空列表

### test_kline.py
- [ ] 日线返回 bars (真实同花顺数据)
- [ ] 第二次查询命中缓存 (响应更快)
- [ ] period=weekly 参数有效
- [ ] 无效代码返回空数据

### test_realtime.py
- [ ] 行情返回 price > 0
- [ ] 返回字段: price, change_pct, volume, high, low
- [ ] change_pct 是数字类型

### test_financials.py
- [ ] 财务返回 ROE 和 debt_ratio
- [ ] ROE 是数字类型, 不为 None
- [ ] report_date 字段存在

### test_indicators.py
- [ ] 指标返回 MACD 数据
- [ ] 指标返回 RSI 数据  
- [ ] 指标返回 KDJ 数据
- [ ] 指标返回 BOLL 数据
- [ ] days 参数控制返回数量

### test_skills.py
- [ ] GET /skills 返回列表
- [ ] 至少包含 "股票分析" skill
- [ ] POST /skills/upload 上传 .md 文件
- [ ] DELETE /skills/{name} 删除

### test_watchlist.py
- [ ] GET /watchlist 返回列表
- [ ] POST /watchlist 添加自选
- [ ] DELETE /watchlist/{code} 删除自选
- [ ] 重复添加不报错

### test_diagnosis.py
- [ ] POST /diagnosis/chat 返回 200
- [ ] SSE 格式: data: {session_id}
- [ ] SSE 格式: data: {status: "agent_starting"}
- [ ] SSE 格式: data: {done: true}

### test_datasources.py
- [ ] TonghuashunSource 可实例化
- [ ] health_check() 返回 True
- [ ] markets 包含 "a_share"
- [ ] _to_ths_code("sh.600519") → "600519.SH"
- [ ] sample 数据源可生成数据

### test_data_engine.py
- [ ] _market_from_code("sh.600519") → "a_share"
- [ ] _market_from_code("us.AAPL") → "us"
- [ ] health() 返回正确结构

### test_scheduler.py
- [ ] cleanup_old_data 函数存在
- [ ] sync_all_daily_klines 函数存在

## 5. 前端构建验证

- [ ] `npx tsc --noEmit` 零错误
- [ ] `npx vite build` 成功
- [ ] index.css 包含关键 CSS class (kline-container, right-panel, info-card)
- [ ] App.tsx 导入所有必要组件

## 6. verify.sh 脚本

```bash
#!/bin/bash
set -e
echo "=== Stock Agent Test Suite ==="

# Backend tests
echo "[1/4] Backend API Tests..."
cd backend
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short

# Data source tests  
echo "[2/4] Data Source Tests..."
.venv/Scripts/python.exe -m pytest tests/test_datasources.py tests/test_data_engine.py -v

# Scheduler tests
echo "[3/4] Scheduler Tests..."
.venv/Scripts/python.exe -m pytest tests/test_scheduler.py -v

# Frontend build
echo "[4/4] Frontend Build..."
cd ../frontend
npx tsc --noEmit
npx vite build --logLevel error

echo ""
echo "=== ALL TESTS PASSED ==="
```

## 7. pre-push hook

`.git/hooks/pre-push`:
```bash
#!/bin/bash
bash verify.sh
```

安装: `cp verify.sh .git/hooks/pre-push`

## 8. 铁律

> **每次新增功能必须新增测试用例。修改功能必须更新对应测试。测试不过不能 push。**

该规则写入 `.hermes.md` 和 CONTRIBUTING 指南。
