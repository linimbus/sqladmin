#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

IMAGE="sql-station:latest"
PLATFORMS=""
PUSH=0
NO_CACHE=0
INSTALL_MSSQL="false"
INSTALL_ORACLE="false"

usage() {
  cat <<'EOF'
构建 SQL Station Docker 镜像。

用法:
  ./docker-build.sh [选项]

选项:
  -t, --tag <name:tag>       镜像名称与标签（默认 sql-station:latest）
  -p, --platform <platforms> 指定目标平台，例如 linux/amd64,linux/arm64
      --push                 使用 buildx 构建并推送到镜像仓库
      --no-cache             不使用构建缓存
      --with-mssql           安装 SQL Server 可选驱动 pymssql
      --with-oracle          安装 Oracle 可选驱动 oracledb
  -h, --help                 显示帮助

示例:
  ./docker-build.sh
  ./docker-build.sh --tag sql-station:1.0.0
  ./docker-build.sh --with-mssql --with-oracle
  ./docker-build.sh --platform linux/amd64,linux/arm64 \
      --tag registry.example.com/sql-station:latest --push
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--tag)
      IMAGE="${2:?缺少镜像名称}"
      shift 2
      ;;
    -p|--platform)
      PLATFORMS="${2:?缺少平台参数}"
      shift 2
      ;;
    --push)
      PUSH=1
      shift
      ;;
    --no-cache)
      NO_CACHE=1
      shift
      ;;
    --with-mssql)
      INSTALL_MSSQL="true"
      shift
      ;;
    --with-oracle)
      INSTALL_ORACLE="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "错误: 未找到 docker，请先安装 Docker。" >&2
  exit 1
fi

if [[ -n "$PLATFORMS" && "$PLATFORMS" == *,* && "$PUSH" != "1" ]]; then
  echo "错误: 多平台构建无法加载到本地 Docker，请配合 --push 使用。" >&2
  exit 1
fi

BUILD_ARGS=(--build-arg "INSTALL_MSSQL=$INSTALL_MSSQL" --build-arg "INSTALL_ORACLE=$INSTALL_ORACLE")
if [[ "$NO_CACHE" == "1" ]]; then
  BUILD_ARGS+=(--no-cache)
fi

echo "==> 构建镜像: $IMAGE"
echo "    SQL Server 驱动: $INSTALL_MSSQL"
echo "    Oracle 驱动:     $INSTALL_ORACLE"
[[ -n "$PLATFORMS" ]] && echo "    目标平台:        $PLATFORMS"

if [[ -n "$PLATFORMS" || "$PUSH" == "1" ]]; then
  if ! docker buildx version >/dev/null 2>&1; then
    echo "错误: 当前 Docker 未安装 buildx 插件。" >&2
    exit 1
  fi

  BUILD_CMD=(docker buildx build --tag "$IMAGE" "${BUILD_ARGS[@]}")
  if [[ -n "$PLATFORMS" ]]; then
    BUILD_CMD+=(--platform "$PLATFORMS")
  fi
  if [[ "$PUSH" == "1" ]]; then
    BUILD_CMD+=(--push)
  else
    BUILD_CMD+=(--load)
  fi
  BUILD_CMD+=(.)
else
  BUILD_CMD=(docker build --tag "$IMAGE" "${BUILD_ARGS[@]}" .)
fi

printf '    '
printf '%q ' "${BUILD_CMD[@]}"
printf '\n'
"${BUILD_CMD[@]}"

echo ""
echo "==> 镜像构建完成: $IMAGE"
if [[ "$PUSH" != "1" ]]; then
  docker image inspect --format '    大小: {{.Size}} bytes' "$IMAGE" 2>/dev/null || true
  cat <<EOF

本地运行:
  docker run -d --name sql-station \\
    -p 8000:8000 \\
    -v sql-station-data:/app/data \\
    --restart unless-stopped \\
    $IMAGE

或使用 docker compose:
  docker compose up -d

访问: http://127.0.0.1:8000
EOF
else
  echo "已推送到镜像仓库: $IMAGE"
fi
