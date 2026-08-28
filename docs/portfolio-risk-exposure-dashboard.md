# 组合风险与暴露看板

Web 持仓页新增“风险与暴露看板”，放在组合总览指标和持仓明细之间，用于提供一眼可读的组合风险状态。

## 风险旗标

| 旗标 | 数据来源 | 触发语义 |
| --- | --- | --- |
| 个股集中 | `risk.concentration` | Top1 个股权重触发 concentration alert |
| 行业集中 | `risk.sectorConcentration` | Top1 行业权重触发 sector alert |
| 回撤 | `risk.drawdown` | 当前或最大回撤触发 drawdown alert |
| 止损 | `risk.stopLoss` | 存在接近或已触发止损标的 |
| AI 信号 | `risk.decisionSignalRisk` | 存在 sell / reduce / alert 等防御型建议 |
| 价格质量 | `snapshot.accounts[].positions[]` | 缺价或价格过期 |

## 暴露看板

| 暴露维度 | 聚合方式 |
| --- | --- |
| 市场暴露 | 先将 `position.marketValueBase` 从账户基准币折算到快照聚合币种，再按 `position.market` 聚合 |
| 币种暴露 | 先将 `position.marketValueBase` 从账户基准币折算到快照聚合币种，再按 `position.currency` 聚合 |

权重使用当前快照 `totalMarketValue` 作为分母。

## 边界

- 本次不新增后端字段，所有数据均来自既有 snapshot 和 risk 响应。
- `/api/v1/portfolio/risk` 不可用或返回空风险块时，依赖服务端风险结果的旗标显示为“不可用”，不伪装成“正常”。
- 暴露换算仅在当前作用域可稳定推断到账户基准币到快照币种的比例时展示；若处于“全部账户”且包含多种账户基准币、前端缺少逐账户已折算金额，则市场/币种暴露降级为空态，避免展示错误金额。
- 原有持仓明细、集中度饼图、回撤、止损、AI 风险小卡继续保留。
- 价格质量只基于 `priceAvailable`、`priceSource` 和 `priceStale`，同一持仓只按“缺价或过期”计数一次，不额外请求行情。

## 后续扩展

- 按账户、行业、货币和市场增加可切换暴露视图。
- 接入 PersonalFinanceCalendar 后，在旗标中显示即将到期的分红、财报、期权或融资事件。
- 接入 ResearchArtifact 后，展示每只重仓股的 thesis 是否被风险旗标触发。
