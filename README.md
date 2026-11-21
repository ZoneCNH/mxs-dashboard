# MxS 监控仪表盘（Macro×Signals）

参考 Google Sites 全页嵌入结构的单文件监控仪表盘：宏观叙事（M1–M7）× 市场状态（S0–S7）→ T1–T7 策略模板 + R0–R3 风险档位。

**定位**：离线研究 / 推演沙盘。所有矩阵、阈值、权重均来自 `knowledge/framework/config/*.yaml`（SSOT），`matrix_cells` 参数标注 `UNCALIBRATED`，**不构成交易信号**。

## 数据口径

- 决策矩阵：`ms_matrix_core.yaml`（7×7，列序 S0–S7）
- 单元参数：`matrix_cells.yaml`（49 格）
- 风险档位：`risk.yaml`（R0–R3 上限）
- LGIP 四因子：`narratives.yaml`（trend_20d + z 标准化）
- S 五维分类：`regimes.yaml`（加权和 + 状态优先级）
- 门控：stale ×0.7 / 冲突 −0.25 / 置信度降档 / M6 全行 R0

## 情景预设

12 个人工推演预设 + 1 个实测快照：

- `live`：宏观 10/11 指标实测值。FRED 侧走 fredpy PIT（vintage 2026-11-19），Yahoo 侧为对照源（GC=F / HG=F / DX-Y.NYB canonical 对照；^GSPC / ^VIX 非 canonical 对照）。`hy_oas`（BAMLH0A0HYM2）fredpy 未接入观测，置 0。M/S 为占位待人工判定。
- 其余预设为离线示例快照。

## 实测数据流水线（每日自动）

```
cron 06:45 CST → tools/run_daily.sh
  → tools/fetch_live_snapshot.py   # fredpy PIT + Yahoo → /tmp/mxs_live.json
  → tools/push_live_snapshot.py    # 更新 Lark「MxS 指标明细」实测-滚动 11 行
```

- Lark 侧 `快照=实测-滚动` 为就地更新的最新快照（不新建行；历史快照暂存在 `/tmp/mxs_live_*.json` 与 `logs/daily.log`）。
- 手动刷新：`tools/run_daily.sh` 或单独跑两个脚本。
- 依赖：`~/.config` 无关；fredpy 凭据读 `/home/workspace/bytechainx/.config/fredpy-mxs.env`；`lark-cli` 需在 PATH（`~/.npm-global/bin`）。

## 重新生成实测快照（手动）

```bash
python3 tools/fetch_live_snapshot.py > /tmp/mxs_live.json
python3 tools/push_live_snapshot.py /tmp/mxs_live.json   # 可选：写回 Lark
```

依赖：fredpy 服务（`FREDPY_MXS_CLIENT_ID/SECRET`，默认 `http://127.0.0.1:8000/api/v1`）+ Yahoo chart API。口径：trend_20d + z(2y 滚动, pstdev, min 60)；jobless_claims 用 4 周相对变化。产物含 `raw_z`（未截断）与 `diagnostics`（各源最后观测日）。

## 已知限制

- 宏观指标 UI 量程 [-1,1]，raw_z 超界被截断（实测快照中 spx/vix/breakeven/gold/copper/dxy/oil 多项触边）。
- S 五维（趋势/杠杆/热度/去杠杆/波动率）需要加密市场数据（OI、funding、爆仓），当前无接入，`live` 预设中为占位。
- Lark Base 侧「MxS 指标明细 / MxS 判定」表为同一 SSOT 的离线快照集。
