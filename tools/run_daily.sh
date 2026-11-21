#!/usr/bin/env bash
# MxS 实测快照日更：fetch (fredpy PIT + Yahoo) -> push Lark Base
# 用法: tools/run_daily.sh   （cron 调用）
set -euo pipefail
cd "$(dirname "$0")/.."
TS=$(date +%Y%m%d_%H%M%S)
LOG=/home/workspace/mxs-dashboard/logs/daily.log
mkdir -p "$(dirname "$LOG")"
{
  echo "=== $TS fetch ==="
  python3 tools/fetch_live_snapshot.py > "/tmp/mxs_live_$TS.json" 2>>"$LOG"
  python3 tools/push_live_snapshot.py "/tmp/mxs_live_$TS.json"
  cp "/tmp/mxs_live_$TS.json" "/tmp/mxs_live.json"
  echo "=== $TS done ==="
} >>"$LOG" 2>&1
tail -5 "$LOG"
