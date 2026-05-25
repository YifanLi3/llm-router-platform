# Phase 3

**从这一阶段开始，正式进入“后端可观测接口 + 前端看板页面”联动开发**

- 先补齐看板需要的后端接口
- 再把 Streamlit 页面接到这些真实接口上

---

## 1. 阶段目标

完成阶段 3 后目标效果：

- 使用Streamlit 完成页面效果
- 在 `http://localhost:8080/docs` 里连续调用 `POST /route` 之后：
  - `GET /quality/dashboard` 指标会变化（请求数、成功率、等）
  - Streamlit 的 Overview / Models / Performance 刷新后能看到同样的变化
- 后端不可用时，Streamlit 明确提示“数据不可用/后端不可达”，不能继续展示随机数假装正常

---

## 2. 核心内容

### A. 后端接口层
阶段 3 新增/完善的后端接口如下：

- `GET /status`
  - 用于返回系统状态快照
  - 给前端展示服务运行态、router_mode、quality/adapters/optimization 等信息
- `GET /analytics`
  - 用于返回看板总览数据
  - 给 Overview / Models / Users / Costs 页面提供聚合数据
- `GET /quality/dashboard`
  - 用于返回质量监控数据
  - 给 Performance / Alerts 页面提供成功率、错误率、P95、hotspots、SLO 等
- `POST /feedback`
  - 用于提交用户反馈
  - 给后续质量闭环做入口

说明：
- `/health` 和 `/route` 不是阶段 3 新写的，但仍然继续使用
- 阶段 3 的后端重点是“为看板提供真实数据”

### B. 前端页面层
- `Overview`
- `Models`
- `Performance`

- `Users`
- `Costs`
- `Alerts`
- Logs`

---

## 3.  页面与后端接口对应关系

### `Overview`
页面作用：
- 展示系统总览
- 展示总请求量、平均延迟、成功率、成本、缓存命中率等核心指标

需要的后端接口：
- `GET /analytics`
- `GET /health`

实现要求：
- 顶部 5 个指标卡能显示真实值
- 页面刷新后，指标会随着 `/route` 的调用而变化

### `Models`
页面作用：
- 展示每个模型的请求量、成功率、延迟、成本、效率

需要的后端接口：
- `GET /analytics`

实现要求：
- 至少用表格展示 1 组按模型聚合后的真实数据

### `Performance`
页面作用：
- 展示请求量、响应时间、P95、错误率等性能指标

需要的后端接口：
- `GET /quality/dashboard`
- `GET /analytics`

实现要求：
- 展示真实的 avg / p95 / error_rate

### `Users`
页面作用：
- 展示不同用户层级的请求分布与使用情况

需要的后端接口：
- `GET /analytics`

实现要求：
- 能显示 free / premium / enterprise 的请求占比或请求数

### `Costs`
页面作用：
- 展示成本分布与主要成本来源

需要的后端接口：
- `GET /analytics`

实现要求：
- 能显示总成本与按模型成本分布

### `Alerts`
页面作用：
- 展示系统告警、热点模型、SLO 状态

需要的后端接口：
- `GET /quality/dashboard`
- `GET /health`

实现要求：
- 展示热点模型、SLO 合规状态或错误率异常提示

### `Logs`
页面作用：
- 展示系统日志与排障信息

---

## 4. 实现顺序参考

### 第一步：补齐后端接口
先把这些接口准备好并确认返回结构稳定：
- `GET /status`
- `GET /analytics`
- `GET /quality/dashboard`
- `POST /feedback`

### 第二步：先做 3 个核心页面
先完成：
- `Overview`
- `Models`
- `Performance`

原因：
- 这 3 个页面最能体现“真实数据联动”
- 做完它们，阶段 3 就已经具备最小可交付成果

### 第三步：补齐业务分析页面
再完成：
- `Users`
- `Costs`
- `Alerts`

### 第四步：最后做日志页
最后完成：
- `Logs`
- Feedback 表单
- Sidebar 真实状态
- 真正的趋势线

