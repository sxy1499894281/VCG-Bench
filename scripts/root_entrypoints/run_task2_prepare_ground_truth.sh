#!/bin/bash
# Task 2: Prepare Ground Truth Data (Instructions and Question Sets Generation)
# 这个脚本只需要运行一次，使用Gemini生成指令和问题集作为ground truth
# 后续评测其他模型时，只需要加载这些指令和问题集，不需要重新生成
# Usage: ./run_task2_prepare_ground_truth.sh [--domain domain1 domain2 ...]
#
# ========================================
# 如何中断脚本执行（使用 nohup 运行时）：
# ========================================
# 使用 nohup 运行脚本：
#   nohup ./run_task2_prepare_ground_truth.sh [--domain ...] > nohup.out 2>&1 &
#
# 中断 nohup 运行的脚本：
# 1. 查找脚本进程：
#    ps aux | grep run_task2_prepare_ground_truth.sh | grep -v grep
#    或者查找 Python 子进程：
#    ps aux | grep -E "(instruction_generation|generate_question_set)" | grep python
#
# 2. 获取进程 ID (PID) 后终止：
#    kill <PID>              # 正常终止（推荐）
#    kill -9 <PID>           # 强制终止（如果正常终止无效）
#
# 3. 或者使用 pkill 命令（一次性终止所有相关进程）：
#    pkill -f run_task2_prepare_ground_truth.sh
#    pkill -f instruction_generation.py
#    pkill -f generate_question_set.py
#
# 4. 查看 nohup 输出：
#    tail -f nohup.out       # 实时查看输出
#    cat nohup.out           # 查看完整输出
#
# 中断后：
#    - 正在执行的 Python 进程会被终止
#    - 已生成的指令和问题集会保留在 data/task2_benchmark 目录中
#    - 日志文件会保留在 logs/ 目录中，可以查看已执行的部分
#    - 如果中断发生在 Step 1 和 Step 2 之间，Step 1 的结果会保留
#    - 可以重新运行脚本，已生成的数据会被跳过（如果 Python 脚本支持）
# ========================================

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse arguments for --domain and --skip-render
DOMAIN_ARGS=()
SKIP_RENDER=""
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
        --skip-render)
            SKIP_RENDER="--skip-render"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Configuration
TARGET_DIR="${TARGET_DIR:-data/task2_benchmark}"
LOG_DIR="${LOG_DIR:-logs}"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Log file with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/task2_prepare_ground_truth_${TIMESTAMP}.log"

echo "=========================================="
echo "Task 2: Prepare Ground Truth"
echo "=========================================="
echo "Target: $TARGET_DIR"
if [ ${#DOMAIN_ARGS[@]} -gt 0 ]; then
    echo "Domains: ${DOMAIN_ARGS[@]}"
else
    echo "Domains: All"
fi
if [ -n "$SKIP_RENDER" ]; then
    echo "Skip Render: Yes"
else
    echo "Skip Render: No"
fi
echo "Log: $LOG_FILE"
echo "=========================================="
echo ""
echo "This script generates instructions and question sets using Gemini (gemini-3-pro-preview)."
echo "These will be used as ground truth for Task 2 evaluation."
echo "You only need to run this ONCE. Other models will load these instructions and question sets."
echo ""

# Step 1: Generate instructions
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 1: Generating instructions with Gemini..."
python scripts/task2/instruction_generation.py generate-all \
    --source "$TARGET_DIR" \
    --output "$TARGET_DIR" \
    --model gemini-3-pro-preview \
    "${DOMAIN_ARGS[@]}" \
    $SKIP_RENDER \
    >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "ERROR: Step 1 (instruction generation) failed. Check log: $LOG_FILE"
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 1 completed."

# Step 2: Generate question sets
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 2: Generating question sets with Gemini..."
python scripts/task2/generate_question_set.py generate-all \
    --source "$TARGET_DIR" \
    --model gemini-3-pro-preview \
    "${DOMAIN_ARGS[@]}" \
    >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "ERROR: Step 2 (question set generation) failed. Check log: $LOG_FILE"
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Step 2 completed."

echo ""
echo "=========================================="
echo "Task 2 Ground Truth Preparation Completed!"
echo "Log file: $LOG_FILE"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run ./run_task2_data_generation.sh [model_name] to test other models"
echo "2. The instructions and question sets will be automatically loaded"

