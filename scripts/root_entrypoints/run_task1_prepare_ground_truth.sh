#!/bin/bash
# Task 1: Prepare Ground Truth Data (QA Pairs Generation)
# 这个脚本只需要运行一次，使用Gemini生成QA对作为ground truth
# 后续评测其他模型时，只需要加载这些QA对，不需要重新生成
# Usage: ./run_task1_prepare_ground_truth.sh [--domain domain1 domain2 ...]
#
# ========================================
# 如何中断脚本执行（使用 nohup 运行时）：
# ========================================
# 使用 nohup 运行脚本：
#   nohup ./run_task1_prepare_ground_truth.sh [--domain ...] > nohup.out 2>&1 &
#
# 中断 nohup 运行的脚本：
# 1. 查找脚本进程：
#    ps aux | grep run_task1_prepare_ground_truth.sh | grep -v grep
#    或者查找 Python 子进程：
#    ps aux | grep generate_qa_pairs.py | grep -v grep
#
# 2. 获取进程 ID (PID) 后终止：
#    kill <PID>              # 正常终止（推荐）
#    kill -9 <PID>           # 强制终止（如果正常终止无效）
#
# 3. 或者使用 pkill 命令（一次性终止所有相关进程）：
#    pkill -f run_task1_prepare_ground_truth.sh
#    pkill -f generate_qa_pairs.py
#
# 4. 查看 nohup 输出：
#    tail -f nohup.out       # 实时查看输出
#    cat nohup.out           # 查看完整输出
#
# 中断后：
#    - 正在执行的 Python 进程会被终止
#    - 已生成的 QA 对会保留在 data/task1_benchmark 目录中
#    - 日志文件会保留在 logs/ 目录中，可以查看已执行的部分
#    - 可以重新运行脚本，已生成的 QA 对会被跳过（如果 Python 脚本支持）
# ========================================

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse arguments for --domain
DOMAIN_ARGS=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain)
            shift
            # Collect domain names until next option or end of arguments
            while [[ $# -gt 0 ]]; do
                # Check if current argument starts with --
                if [[ "$1" == --* ]]; then
                    break
                fi
                DOMAIN_ARGS+=("--domain" "$1")
                shift
            done
            ;;
        *)
            shift
            ;;
    esac
done

# Configuration
TARGET_DIR="${TARGET_DIR:-data/task1_benchmark}"
LOG_DIR="${LOG_DIR:-logs}"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Log file with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/task1_prepare_ground_truth_${TIMESTAMP}.log"

echo "=========================================="
echo "Task 1: Prepare Ground Truth (QA Pairs)"
echo "=========================================="
echo "Target: $TARGET_DIR"
if [ ${#DOMAIN_ARGS[@]} -gt 0 ]; then
    echo "Domains: ${DOMAIN_ARGS[@]}"
else
    echo "Domains: All"
fi
echo "Log: $LOG_FILE"
echo "=========================================="
echo ""
echo "This script generates QA pairs using Gemini (gemini-3-pro-preview)."
echo "These will be used as ground truth for Task 1 CodeVQA evaluation."
echo "You only need to run this ONCE. Other models will load these QA pairs."
echo ""

# Generate QA pairs
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Generating QA pairs with Gemini..."
python scripts/task1/generate_qa_pairs.py generate-all \
    --source "$TARGET_DIR" \
    --model gemini-3-pro-preview \
    "${DOMAIN_ARGS[@]}" \
    >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "ERROR: QA pairs generation failed. Check log: $LOG_FILE"
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] QA pairs generation completed."

echo ""
echo "=========================================="
echo "Task 1 Ground Truth Preparation Completed!"
echo "Log file: $LOG_FILE"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run ./run_task1_data_generation.sh [model_name] to test other models"
echo "2. The QA pairs will be automatically loaded from qa_pairs.json files"

