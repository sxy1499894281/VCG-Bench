#!/bin/bash
# 使用 nohup 后台运行 SigLIP 模型下载脚本
# Usage: ./scripts/download_siglip_model_nohup.sh [model_name]
# Example: ./scripts/download_siglip_model_nohup.sh google/siglip2-so400m-patch16-512

set -e

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# 默认模型名称
MODEL_NAME="${1:-google/siglip2-so400m-patch16-512}"

# 日志文件路径（与脚本在同一目录）
LOG_FILE="$SCRIPT_DIR/download_siglip_model.log"

echo "=========================================="
echo "SigLIP 模型下载脚本 (后台运行)"
echo "=========================================="
echo "模型名称: $MODEL_NAME"
echo "使用镜像: hf-mirror.com"
echo "日志文件: $LOG_FILE"
echo "=========================================="
echo ""
echo "正在后台启动下载任务..."
echo ""

# 使用 nohup 后台运行，输出重定向到日志文件
nohup python scripts/download_siglip_model.py --model "$MODEL_NAME" > "$LOG_FILE" 2>&1 &

# 获取进程 ID
PID=$!

echo "✅ 下载任务已启动！"
echo "   进程 ID: $PID"
echo "   日志文件: $LOG_FILE"
echo ""
echo "查看日志:"
echo "   tail -f $LOG_FILE"
echo ""
echo "查看进程:"
echo "   ps aux | grep $PID"
echo ""
echo "停止下载:"
echo "   kill $PID"
echo ""
echo "=========================================="

# 等待一秒，检查进程是否还在运行
sleep 1
if ps -p $PID > /dev/null 2>&1; then
    echo "✅ 进程运行正常"
else
    echo "⚠️  进程可能已退出，请检查日志: $LOG_FILE"
fi

echo "=========================================="

