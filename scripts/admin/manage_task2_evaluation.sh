#!/bin/bash
# Task 2 评估任务管理脚本 - 查看和停止特定模型的评估任务
# 用法:
#   查看所有任务: ./manage_task2_evaluation.sh list
#   停止特定模型: ./manage_task2_evaluation.sh stop gemini-3-pro-preview
#   查看特定模型: ./manage_task2_evaluation.sh show gemini-3-pro-preview
#   停止所有任务: ./manage_task2_evaluation.sh stop-all
#   停止除指定模型外的所有任务: ./manage_task2_evaluation.sh stop-except gemini-3-pro-preview

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

ACTION="${1:-list}"
MODEL_NAME="${2:-}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 查找所有运行中的 Task 2 评估任务
find_tasks() {
    # 查找所有 run_task2_evaluation.sh 进程
    ps aux | grep "run_task2_evaluation.sh" | grep -v grep | while read line; do
        # 提取 PID
        pid=$(echo "$line" | awk '{print $2}')
        
        # 提取完整命令行
        cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
        
        # 提取模型名（第一个参数）
        # 使用 sed 替代 grep -P，兼容 macOS
        model=$(echo "$cmd" | sed -n 's/.*run_task2_evaluation.sh \([^[:space:]]*\).*/\1/p' | head -1)
        model=${model:-unknown}
        
        # 提取启动时间
        start_time=$(ps -o lstart= -p "$pid" 2>/dev/null || echo "N/A")
        
        # 提取 CPU 和内存使用
        cpu=$(echo "$line" | awk '{print $3}')
        mem=$(echo "$line" | awk '{print $4}')
        
        echo "$pid|$model|$start_time|$cpu|$mem|$cmd"
    done
}

# 查找 Python 评估进程
find_python_processes() {
    ps aux | grep "eval/run_evaluation.py task2.*--models" | grep -v grep | while read line; do
        pid=$(echo "$line" | awk '{print $2}')
        cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
        
        # 提取模型名
        # 使用 sed 替代 grep -P，兼容 macOS
        model=$(echo "$cmd" | sed -n 's/.*--models \([^[:space:]]*\).*/\1/p' | head -1)
        model=${model:-unknown}
        
        start_time=$(ps -o lstart= -p "$pid" 2>/dev/null || echo "N/A")
        cpu=$(echo "$line" | awk '{print $3}')
        mem=$(echo "$line" | awk '{print $4}')
        
        echo "$pid|$model|$start_time|$cpu|$mem|$cmd"
    done
}

# 列出所有任务
list_tasks() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}运行中的 Task 2 评估任务列表${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    bash_tasks=$(find_tasks)
    python_tasks=$(find_python_processes)
    
    if [ -z "$bash_tasks" ] && [ -z "$python_tasks" ]; then
        echo -e "${YELLOW}没有运行中的任务${NC}"
        return
    fi
    
    # 合并并去重（按模型名分组）
    # 使用临时文件存储模型信息（兼容 bash 3.2 和 zsh）
    MODELS_TMP=$(mktemp)
    
    while IFS='|' read -r pid model start_time cpu mem cmd; do
        if [ -n "$pid" ] && [ -n "$model" ]; then
            echo "$model|$pid|$start_time|$cpu|$mem" >> "$MODELS_TMP"
        fi
    done < <(echo -e "$bash_tasks\n$python_tasks")
    
    # 显示表格
    printf "%-40s %-10s %-20s %-8s %-8s\n" "模型名称" "PID" "启动时间" "CPU%" "内存%"
    echo "--------------------------------------------------------------------------------------------"
    
    # 按模型名分组显示
    for model in $(cut -d'|' -f1 "$MODELS_TMP" 2>/dev/null | sort -u); do
        # 获取该模型的所有进程信息
        model_pids=$(grep "^$model|" "$MODELS_TMP" 2>/dev/null | cut -d'|' -f2-)
        first_line=$(echo "$model_pids" | head -1)
        IFS='|' read -r pid start_time cpu mem <<< "$first_line"
        
        printf "%-40s %-10s %-20s %-8s %-8s\n" "$model" "$pid" "$start_time" "$cpu%" "$mem%"
        
        # 如果有多个进程，显示其他 PID
        pid_count=$(echo "$model_pids" | wc -l | tr -d ' ')
        if [ "$pid_count" -gt 1 ]; then
            echo "$model_pids" | tail -n +2 | while IFS='|' read -r pid start_time cpu mem; do
                printf "%-40s %-10s %-20s %-8s %-8s\n" "  (子进程)" "$pid" "$start_time" "$cpu%" "$mem%"
            done
        fi
    done
    
    rm -f "$MODELS_TMP"
    
    echo ""
    echo -e "${GREEN}提示: 使用 './manage_task2_evaluation.sh stop <model_name>' 停止特定模型${NC}"
}

# 显示特定模型的任务
show_model() {
    if [ -z "$MODEL_NAME" ]; then
        echo -e "${RED}错误: 请指定模型名称${NC}"
        echo "用法: ./manage_task2_evaluation.sh show <model_name>"
        return 1
    fi
    
    echo -e "${BLUE}查找模型: $MODEL_NAME${NC}"
    echo ""
    
    found=false
    
    # 查找 bash 脚本进程
    ps aux | grep "run_task2_evaluation.sh.*$MODEL_NAME" | grep -v grep | while read line; do
        found=true
        pid=$(echo "$line" | awk '{print $2}')
        cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
        start_time=$(ps -o lstart= -p "$pid" 2>/dev/null || echo "N/A")
        
        echo -e "${GREEN}找到进程:${NC}"
        echo "  PID: $pid"
        echo "  启动时间: $start_time"
        echo "  命令行: $cmd"
        echo ""
    done
    
    # 查找 Python 进程
    ps aux | grep "eval/run_evaluation.py task2.*--models.*$MODEL_NAME" | grep -v grep | while read line; do
        found=true
        pid=$(echo "$line" | awk '{print $2}')
        cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
        start_time=$(ps -o lstart= -p "$pid" 2>/dev/null || echo "N/A")
        
        echo -e "${GREEN}找到进程:${NC}"
        echo "  PID: $pid"
        echo "  启动时间: $start_time"
        echo "  命令行: $cmd"
        echo ""
    done
    
    if [ "$found" = false ]; then
        echo -e "${YELLOW}未找到模型 '$MODEL_NAME' 的运行进程${NC}"
    fi
}

# 停止特定模型的任务
stop_model() {
    if [ -z "$MODEL_NAME" ]; then
        echo -e "${RED}错误: 请指定模型名称${NC}"
        echo "用法: ./manage_task2_evaluation.sh stop <model_name>"
        return 1
    fi
    
    echo -e "${YELLOW}正在查找模型 '$MODEL_NAME' 的进程...${NC}"
    echo ""
    
    found=false
    
    # 查找并显示 bash 脚本进程
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            found=true
            pid=$(echo "$line" | awk '{print $2}')
            cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
            echo -e "${GREEN}找到 bash 进程: PID $pid${NC}"
            echo "  命令: $cmd"
        fi
    done < <(ps aux | grep "run_task2_evaluation.sh.*$MODEL_NAME" | grep -v grep)
    
    # 查找并显示 Python 进程（精确匹配模型名）
    while IFS= read -r line; do
        if echo "$line" | grep -q "eval/run_evaluation.py task2.*--models.*$MODEL_NAME"; then
            found=true
            pid=$(echo "$line" | awk '{print $2}')
            cmd=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
            echo -e "${GREEN}找到 Python 进程: PID $pid${NC}"
            echo "  命令: $cmd"
        fi
    done < <(ps aux | grep "eval/run_evaluation.py task2" | grep -v grep)
    
    if [ "$found" = false ]; then
        echo -e "${YELLOW}未找到模型 '$MODEL_NAME' 的运行进程${NC}"
        return 0
    fi
    
    # 使用 pkill 精确匹配
    echo ""
    echo -e "${YELLOW}正在停止进程...${NC}"
    
    # 停止 bash 脚本（精确匹配：脚本名 + 模型名作为第一个参数）
    # 使用更精确的匹配模式
    pkill -f "run_task2_evaluation.sh $MODEL_NAME " && echo -e "${GREEN}✓ 已停止 bash 脚本进程${NC}" || echo -e "${YELLOW}未找到 bash 脚本进程${NC}"
    
    # 停止 Python 进程（精确匹配模型名）
    escaped_model=$(echo "$MODEL_NAME" | sed 's/[\/&]/\\&/g')
    pkill -f "eval/run_evaluation.py task2.*--models $escaped_model" && echo -e "${GREEN}✓ 已停止 Python 进程${NC}" || echo -e "${YELLOW}未找到 Python 进程${NC}"
    
    sleep 1
    
    # 验证是否已停止
    remaining=$(ps aux | grep -E "run_task2_evaluation.sh.*$MODEL_NAME|eval/run_evaluation.py task2.*--models.*$MODEL_NAME" | grep -v grep | wc -l)
    if [ "$remaining" -eq 0 ]; then
        echo -e "${GREEN}✓ 模型 '$MODEL_NAME' 的所有进程已停止${NC}"
    else
        echo -e "${RED}警告: 仍有 $remaining 个进程在运行，尝试强制停止...${NC}"
        pkill -9 -f "run_task2_evaluation.sh $MODEL_NAME "
        escaped_model=$(echo "$MODEL_NAME" | sed 's/[\/&]/\\&/g')
        pkill -9 -f "eval/run_evaluation.py task2.*--models $escaped_model"
        sleep 1
        remaining=$(ps aux | grep -E "run_task2_evaluation.sh.*$MODEL_NAME|eval/run_evaluation.py task2.*--models.*$MODEL_NAME" | grep -v grep | wc -l)
        if [ "$remaining" -eq 0 ]; then
            echo -e "${GREEN}✓ 已强制停止所有进程${NC}"
        else
            echo -e "${RED}错误: 无法停止所有进程${NC}"
        fi
    fi
}

# 停止所有任务
stop_all() {
    echo -e "${RED}警告: 这将停止所有运行中的 Task 2 评估任务！${NC}"
    read -p "确认继续？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消"
        return 0
    fi
    
    echo -e "${YELLOW}正在停止所有任务...${NC}"
    
    pkill -f "run_task2_evaluation.sh" && echo -e "${GREEN}✓ 已停止所有 bash 脚本${NC}" || echo -e "${YELLOW}未找到 bash 脚本${NC}"
    pkill -f "eval/run_evaluation.py task2.*--models" && echo -e "${GREEN}✓ 已停止所有 Python 进程${NC}" || echo -e "${YELLOW}未找到 Python 进程${NC}"
    
    sleep 1
    remaining=$(ps aux | grep -E "run_task2_evaluation.sh|eval/run_evaluation.py task2.*--models" | grep -v grep | wc -l)
    if [ "$remaining" -eq 0 ]; then
        echo -e "${GREEN}✓ 所有任务已停止${NC}"
    else
        echo -e "${YELLOW}仍有 $remaining 个进程，尝试强制停止...${NC}"
        pkill -9 -f "run_task2_evaluation.sh"
        pkill -9 -f "eval/run_evaluation.py task2.*--models"
    fi
}

# 停止除指定模型外的所有任务
stop_except() {
    if [ -z "$MODEL_NAME" ]; then
        echo -e "${RED}错误: 请指定要保留的模型名称${NC}"
        echo "用法: ./manage_task2_evaluation.sh stop-except <model_name>"
        return 1
    fi
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}停止除 '$MODEL_NAME' 外的所有 Task 2 评估任务${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # 获取所有运行中的模型
    bash_tasks=$(find_tasks)
    python_tasks=$(find_python_processes)
    
    # 收集所有模型名（去重）
    # 使用临时文件存储模型信息（兼容 bash 3.2 和 zsh）
    ALL_MODELS_TMP=$(mktemp)
    
    while IFS='|' read -r pid model start_time cpu mem cmd; do
        if [ -n "$pid" ] && [ -n "$model" ] && [ "$model" != "unknown" ]; then
            echo "$model" >> "$ALL_MODELS_TMP"
        fi
    done < <(echo -e "$bash_tasks\n$python_tasks")
    
    model_count=$(sort -u "$ALL_MODELS_TMP" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$model_count" -eq 0 ]; then
        echo -e "${YELLOW}没有运行中的任务${NC}"
        rm -f "$ALL_MODELS_TMP"
        return 0
    fi
    
    # 检查要保留的模型是否在运行
    if grep -q "^$MODEL_NAME$" "$ALL_MODELS_TMP" 2>/dev/null; then
        echo -e "${GREEN}保留模型: $MODEL_NAME${NC}"
        model_to_keep_found=true
    else
        echo -e "${YELLOW}警告: 模型 '$MODEL_NAME' 当前没有运行${NC}"
        model_to_keep_found=false
    fi
    
    # 找出需要停止的模型
    models_to_stop=()
    while IFS= read -r model; do
        if [ "$model" != "$MODEL_NAME" ]; then
            models_to_stop+=("$model")
        fi
    done < <(sort -u "$ALL_MODELS_TMP" 2>/dev/null)
    
    if [ ${#models_to_stop[@]} -eq 0 ]; then
        echo -e "${GREEN}没有需要停止的任务（只有 '$MODEL_NAME' 在运行）${NC}"
        return 0
    fi
    
    echo ""
    echo -e "${YELLOW}将停止以下模型:${NC}"
    for model in "${models_to_stop[@]}"; do
        echo "  - $model"
    done
    echo ""
    
    read -p "确认继续？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消"
        return 0
    fi
    
    echo ""
    echo -e "${YELLOW}正在停止任务...${NC}"
    
    stopped_count=0
    for model in "${models_to_stop[@]}"; do
        echo -e "${BLUE}停止模型: $model${NC}"
        
        # 停止 bash 脚本
        pkill -f "run_task2_evaluation.sh $model " && echo -e "  ${GREEN}✓ 已停止 bash 脚本${NC}" || true
        
        # 停止 Python 进程（需要转义特殊字符）
        escaped_model=$(echo "$model" | sed 's/[\/&]/\\&/g')
        pkill -f "eval/run_evaluation.py task2.*--models $escaped_model" && echo -e "  ${GREEN}✓ 已停止 Python 进程${NC}" || true
        
        stopped_count=$((stopped_count + 1))
    done
    
    sleep 1
    
    # 验证结果
    echo ""
    echo -e "${BLUE}验证结果:${NC}"
    bash_tasks_after=$(find_tasks)
    python_tasks_after=$(find_python_processes)
    
    # 使用临时文件存储剩余模型信息（兼容 bash 3.2 和 zsh）
    REMAINING_MODELS_TMP=$(mktemp)
    
    while IFS='|' read -r pid model start_time cpu mem cmd; do
        if [ -n "$pid" ] && [ -n "$model" ] && [ "$model" != "unknown" ] && [ "$model" != "$MODEL_NAME" ]; then
            echo "$model" >> "$REMAINING_MODELS_TMP"
        fi
    done < <(echo -e "$bash_tasks_after\n$python_tasks_after")
    
    remaining_count=$(sort -u "$REMAINING_MODELS_TMP" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$remaining_count" -eq 0 ]; then
        echo -e "${GREEN}✓ 所有目标任务已停止${NC}"
        if [ "$model_to_keep_found" = true ]; then
            echo -e "${GREEN}✓ 模型 '$MODEL_NAME' 仍在运行${NC}"
        fi
    else
        echo -e "${YELLOW}警告: 以下模型仍在运行:${NC}"
        while IFS= read -r model; do
            echo "  - $model"
        done < <(sort -u "$REMAINING_MODELS_TMP" 2>/dev/null)
        echo ""
        echo -e "${YELLOW}尝试强制停止...${NC}"
        while IFS= read -r model; do
            pkill -9 -f "run_task2_evaluation.sh $model "
            escaped_model=$(echo "$model" | sed 's/[\/&]/\\&/g')
            pkill -9 -f "eval/run_evaluation.py task2.*--models $escaped_model"
        done < <(sort -u "$REMAINING_MODELS_TMP" 2>/dev/null)
        sleep 1
        echo -e "${GREEN}✓ 强制停止完成${NC}"
    fi
    
    rm -f "$REMAINING_MODELS_TMP" "$ALL_MODELS_TMP"
}

# 主逻辑
case "$ACTION" in
    list)
        list_tasks
        ;;
    show)
        show_model
        ;;
    stop)
        stop_model
        ;;
    stop-all)
        stop_all
        ;;
    stop-except)
        stop_except
        ;;
    *)
        echo "用法: $0 {list|show|stop|stop-all|stop-except} [model_name]"
        echo ""
        echo "命令:"
        echo "  list                    - 列出所有运行中的 Task 2 评估任务"
        echo "  show <model_name>        - 显示特定模型的详细信息"
        echo "  stop <model_name>        - 停止特定模型的评估任务"
        echo "  stop-all                 - 停止所有 Task 2 评估任务（需确认）"
        echo "  stop-except <model_name> - 停止除指定模型外的所有 Task 2 评估任务（需确认）"
        echo ""
        echo "示例:"
        echo "  $0 list"
        echo "  $0 show gemini-3-pro-preview"
        echo "  $0 stop gemini-3-pro-preview"
        echo "  $0 stop-except zai-org/GLM-4.6V"
        exit 1
        ;;
esac


