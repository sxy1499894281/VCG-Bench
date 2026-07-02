#!/bin/bash
# 查看评估任务日志的辅助脚本
# Usage: ./check_evaluation_logs.sh [model_name] [domain]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="${LOG_DIR:-logs}"

MODEL="${1:-}"
DOMAIN="${2:-}"

echo "=========================================="
echo "评估任务日志查看工具"
echo "=========================================="
echo ""

if [ -z "$MODEL" ]; then
    echo "最近的日志文件（按时间排序）："
    echo "----------------------------------------"
    ls -lth "$LOG_DIR"/task1_evaluation_*.log 2>/dev/null | head -20 | awk '{printf "%-80s %s %s %s\n", $9, $6, $7, $8}'
    echo ""
    echo "按模型分组："
    echo "----------------------------------------"
    for model in $(ls "$LOG_DIR"/task1_evaluation_*.log 2>/dev/null | sed 's/.*task1_evaluation_//' | sed 's/_.*//' | sort -u); do
        count=$(ls "$LOG_DIR"/task1_evaluation_${model}_*.log 2>/dev/null | wc -l)
        echo "  $model: $count 个日志文件"
    done
else
    MODEL_SANITIZED=$(echo "$MODEL" | sed 's/\//_/g')
    if [ -n "$DOMAIN" ]; then
        DOMAIN_NAME=$(echo "$DOMAIN" | sed 's/domain_//g')
        pattern="${LOG_DIR}/task1_evaluation_${MODEL_SANITIZED}_${DOMAIN_NAME}_*.log"
    else
        pattern="${LOG_DIR}/task1_evaluation_${MODEL_SANITIZED}_*.log"
    fi
    
    echo "查找日志文件: $pattern"
    echo "----------------------------------------"
    logs=$(ls -t $pattern 2>/dev/null)
    if [ -z "$logs" ]; then
        echo "未找到匹配的日志文件"
    else
        echo "找到的日志文件："
        echo "$logs" | while read log; do
            size=$(ls -lh "$log" | awk '{print $5}')
            mtime=$(ls -l "$log" | awk '{print $6, $7, $8}')
            echo "  $log ($size, $mtime)"
        done
        echo ""
        echo "最新的日志内容（最后 50 行）："
        echo "----------------------------------------"
        latest_log=$(ls -t $pattern 2>/dev/null | head -1)
        if [ -n "$latest_log" ]; then
            tail -50 "$latest_log"
        fi
    fi
fi

echo ""
echo "=========================================="
echo "提示："
echo "  - 查看所有日志: ./check_evaluation_logs.sh"
echo "  - 查看特定模型: ./check_evaluation_logs.sh <model_name>"
echo "  - 查看特定领域: ./check_evaluation_logs.sh <model_name> <domain>"
echo "  - 实时监控日志: tail -f logs/task1_evaluation_<model>_<domain>_<timestamp>_<pid>.log"
echo "=========================================="

