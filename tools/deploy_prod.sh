#!/usr/bin/env bash
# 将 index.html 部署到生产服务器 ser-ts112（zone@100.122.125.112）
# 站点路径：https://www.xhyperium.com/mxs/ （nginx alias /var/www/mxs-dashboard/）
set -euo pipefail

HOST="${MXD_DEPLOY_HOST:-zone@100.122.125.112}"
DEST="${MXD_DEPLOY_DEST:-/var/www/mxs-dashboard/index.html}"
URL="${MXD_DEPLOY_URL:-https://www.xhyperium.com/mxs/}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

rsync -avz "$ROOT/index.html" "$HOST:$DEST"

code=$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 15 "$URL")
echo "deploy ok: $URL -> HTTP $code"
