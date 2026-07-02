#!/bin/bash
# ModelScope模型服务管理脚本
# 
# 功能:
#   - 启动模型服务
#   - 查看运行状态
#   - 停止模型服务
#   - 删除模型进程
#
# 使用方法:
#   ./manage_models.sh start      # 启动所有配置的模型
#   ./manage_models.sh status     # 查看运行状态
#   ./manage_models.sh stop       # 停止所有模型
#   ./manage_models.sh stop <model_name>  # 停止指定模型
#   ./manage_models.sh kill       # 强制杀死所有模型进程（包括子进程）
#   ./manage_models.sh kill <model_name>  # 强制杀死指定模型进程（包括子进程）
#   ./manage_models.sh cleanup    # 清理所有残留的 vLLM 进程和无效 PID 文件

set -e

# ==================== 配置区域 ====================
# 脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSGBENCH_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# 模型配置（格式: "模型ID|端口|模型路径"）
# 模型路径可以是ModelScope模型ID或本地路径
# 如果使用本地路径，应该是下载后的模型目录
declare -A MODEL_CONFIG
MODEL_CONFIG["MiniCPM-V-4_5"]="OpenBMB/MiniCPM-V-4_5|8001|OpenBMB/MiniCPM-V-4_5"
MODEL_CONFIG["InternVL3_5-8B"]="OpenGVLab/InternVL3_5-8B|8002|OpenGVLab/InternVL3_5-8B"
MODEL_CONFIG["InternVL3_5-14B"]="OpenGVLab/InternVL3_5-14B|8003|OpenGVLab/InternVL3_5-14B"

# GPU分配配置（格式: "GPU设备ID|张量并行度"）
# GPU设备ID: 单个GPU用数字，多个GPU用逗号分隔，例如 "0" 或 "0,1"
# 张量并行度: 使用几张GPU进行张量并行，通常等于GPU数量，例如 1 或 2
# 注意: 如果使用多GPU张量并行，GPU设备ID应该包含所有要使用的GPU
declare -A GPU_CONFIG
GPU_CONFIG["MiniCPM-V-4_5"]="0|1"          # 使用GPU 0，单卡运行
GPU_CONFIG["InternVL3_5-8B"]="1|1"          # 使用GPU 1，单卡运行
# GPU_CONFIG["InternVL3_5-14B"]="2,3|2"      # 使用GPU 2和3，双卡张量并行
GPU_CONFIG["InternVL3_5-14B"]="0|1"      # 使用GPU 0，单卡运行（注意：如果与 MiniCPM-V-4_5 同时运行会有冲突，建议使用不同GPU）

# 模型保存目录（相对于VCG-Bench根目录）
MODELS_DIR="$CSGBENCH_DIR/models/modelscope"

# 日志目录
LOG_DIR="$CSGBENCH_DIR/logs"
mkdir -p "$LOG_DIR"

# PID文件目录（用于跟踪运行中的进程）
PID_DIR="$CSGBENCH_DIR/models/modelscope/pids"
mkdir -p "$PID_DIR"

# vLLM启动参数（可根据需要修改）
VLLM_HOST="0.0.0.0"
VLLM_GPU_MEMORY_UTILIZATION="0.9"
# 不设置 max_model_len，让 vLLM 自动使用模型的最大长度

# Python环境配置（vLLM所在的conda环境）
# 如果vLLM安装在conda环境中，设置环境名称或Python路径
# 例如: VLLM_PYTHON_ENV="xysu" 或 VLLM_PYTHON="/path/to/python"
VLLM_PYTHON_ENV="xysu"  # conda环境名称，如果为空则使用系统Python
# ==================== 配置区域结束 ====================

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 获取模型本地路径
get_model_path() {
    local model_id=$1
    local model_name=$(echo "$model_id" | tr '/' '_')
    local local_path="$MODELS_DIR/$model_name"
    
    # 如果本地路径存在，查找包含 config.json 的实际模型目录
    if [ -d "$local_path" ]; then
        # 首先检查根目录是否有 config.json
        if [ -f "$local_path/config.json" ]; then
            echo "$local_path"
        else
            # 递归查找包含 config.json 的目录
            local actual_path=$(find "$local_path" -name "config.json" -type f 2>/dev/null | head -1 | xargs dirname 2>/dev/null)
            if [ -n "$actual_path" ] && [ -d "$actual_path" ]; then
                echo "$actual_path"
            else
                # 如果找不到，尝试使用 ModelScope ID（让 vLLM 自动下载）
                echo "$model_id"
            fi
        fi
    else
        # 本地路径不存在，使用 ModelScope ID
        echo "$model_id"
    fi
}

# 获取PID文件路径
get_pid_file() {
    local model_name=$1
    echo "$PID_DIR/${model_name}.pid"
}

# 检查端口是否被占用
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # 端口被占用
    else
        return 1  # 端口空闲
    fi
}

# 启动单个模型
start_model() {
    local model_name=$1
    local config=$2
    
    IFS='|' read -r model_id port model_path <<< "$config"
    
    # 获取GPU配置
    local gpu_config="${GPU_CONFIG[$model_name]}"
    if [ -z "$gpu_config" ]; then
        echo -e "${YELLOW}警告: 模型 $model_name 未配置GPU，将使用所有可用GPU${NC}"
        local cuda_visible_devices=""
        local tensor_parallel_size="1"
    else
        IFS='|' read -r gpu_devices tensor_parallel_size <<< "$gpu_config"
        local cuda_visible_devices="$gpu_devices"
    fi
    
    # 检查PID文件是否存在（模型可能已经在运行）
    local pid_file=$(get_pid_file "$model_name")
    if [ -f "$pid_file" ]; then
        local old_pid=$(cat "$pid_file")
        if ps -p "$old_pid" > /dev/null 2>&1; then
            echo -e "${YELLOW}模型 $model_name 已经在运行 (PID: $old_pid)${NC}"
            return 0
        else
            # PID文件存在但进程不存在，删除旧的PID文件
            rm -f "$pid_file"
        fi
    fi
    
    # 检查端口是否被占用
    if check_port "$port"; then
        echo -e "${RED}端口 $port 已被占用，无法启动模型 $model_name${NC}"
        return 1
    fi
    
    # 获取模型路径
    local actual_model_path=$(get_model_path "$model_path")
    
    echo -e "${CYAN}启动模型: $model_name${NC}"
    echo -e "  模型ID: $model_id"
    echo -e "  端口: $port"
    echo -e "  模型路径: $actual_model_path"
    if [ -n "$cuda_visible_devices" ]; then
        echo -e "  GPU设备: $cuda_visible_devices"
        echo -e "  张量并行度: $tensor_parallel_size"
    fi
    
    # 启动vLLM服务器
    local log_file="$LOG_DIR/vllm_${model_name}_${port}.log"
    
    # 确定Python命令（优先使用conda环境）
    local python_cmd="python"
    if [ -n "$VLLM_PYTHON_ENV" ]; then
        # 尝试多种方式找到conda环境的Python
        # 方法1: 从CONDA_PREFIX推断
        if [ -n "$CONDA_PREFIX" ]; then
            local conda_base=$(dirname "$CONDA_PREFIX")
            local conda_env_python="$conda_base/envs/$VLLM_PYTHON_ENV/bin/python"
            if [ -f "$conda_env_python" ]; then
                python_cmd="$conda_env_python"
            fi
        fi
        
        # 方法2: 从常见conda安装路径查找
        if [ "$python_cmd" = "python" ]; then
            for conda_base in "$HOME/miniconda3" "$HOME/anaconda3" "/opt/conda" "/usr/local/miniconda3" "/usr/local/anaconda3"; do
                local conda_env_python="$conda_base/envs/$VLLM_PYTHON_ENV/bin/python"
                if [ -f "$conda_env_python" ]; then
                    python_cmd="$conda_env_python"
                    break
                fi
            done
        fi
        
        # 方法3: 使用conda run（如果前两种方法都失败）
        if [ "$python_cmd" = "python" ] && command -v conda >/dev/null 2>&1; then
            python_cmd="conda run -n $VLLM_PYTHON_ENV python"
        fi
    fi
    
    # 构建vLLM命令（使用数组避免引号问题）
    # 不设置 --max-model-len，让 vLLM 自动使用模型的最大长度
    # 使用 --served-model-name 设置模型名称，使其与 API 调用时使用的名称匹配
    # 添加 --trust-remote-code 以支持包含自定义代码的模型（如 ModelScope 模型）
    local vllm_cmd_array=(
        $python_cmd -m vllm.entrypoints.openai.api_server
        --model "$actual_model_path"
        --served-model-name "$model_id"
        --host "$VLLM_HOST"
        --port "$port"
        --gpu-memory-utilization "$VLLM_GPU_MEMORY_UTILIZATION"
        --trust-remote-code
    )
    
    # 如果配置了张量并行，添加参数
    if [ "$tensor_parallel_size" != "1" ] && [ -n "$tensor_parallel_size" ]; then
        vllm_cmd_array+=(--tensor-parallel-size "$tensor_parallel_size")
    fi
    
    # 确保 ninja 在 PATH 中（FlashInfer 需要）
    local ninja_path=""
    if [ -n "$VLLM_PYTHON_ENV" ]; then
        # 尝试从 conda 环境找到 ninja
        for conda_base in "$HOME/miniconda3" "$HOME/anaconda3" "/opt/conda" "/usr/local/miniconda3" "/usr/local/anaconda3"; do
            local ninja_bin="$conda_base/envs/$VLLM_PYTHON_ENV/bin/ninja"
            if [ -f "$ninja_bin" ]; then
                ninja_path="$ninja_bin"
                break
            fi
        done
    fi
    
    # 构建环境变量
    local env_vars=""
    if [ -n "$cuda_visible_devices" ]; then
        env_vars="CUDA_VISIBLE_DEVICES=$cuda_visible_devices"
    fi
    
    # 确保 ninja 和 gcc 在 PATH 中（FlashInfer 和 Triton 需要）
    local path_additions=""
    if [ -n "$ninja_path" ]; then
        path_additions="$(dirname $ninja_path)"
    fi
    
    # 添加 gcc 路径（如果存在）
    local gcc_path=$(which gcc 2>/dev/null)
    if [ -n "$gcc_path" ]; then
        local gcc_dir=$(dirname "$gcc_path")
        if [ -n "$path_additions" ]; then
            path_additions="$path_additions:$gcc_dir"
        else
            path_additions="$gcc_dir"
        fi
    fi
    
    if [ -n "$path_additions" ]; then
        if [ -n "$env_vars" ]; then
            env_vars="$env_vars PATH=\"$path_additions:\$PATH\" CC=\"${gcc_path:-gcc}\""
        else
            env_vars="PATH=\"$path_additions:\$PATH\" CC=\"${gcc_path:-gcc}\""
        fi
    elif [ -n "$gcc_path" ]; then
        if [ -n "$env_vars" ]; then
            env_vars="$env_vars CC=\"$gcc_path\""
        else
            env_vars="CC=\"$gcc_path\""
        fi
    fi
    
    # 使用nohup在后台启动
    # 构建完整的环境变量设置
    if [ -n "$cuda_visible_devices" ] || [ -n "$path_additions" ] || [ -n "$gcc_path" ]; then
        # 构建 PATH
        local new_path="$PATH"
        if [ -n "$path_additions" ]; then
            new_path="$path_additions:$PATH"
        fi
        
        # 构建环境变量字符串
        local env_cmd=""
        if [ -n "$cuda_visible_devices" ]; then
            env_cmd="CUDA_VISIBLE_DEVICES=$cuda_visible_devices"
        fi
        if [ -n "$new_path" ] && [ "$new_path" != "$PATH" ]; then
            if [ -n "$env_cmd" ]; then
                env_cmd="$env_cmd PATH=\"$new_path\""
            else
                env_cmd="PATH=\"$new_path\""
            fi
        fi
        if [ -n "$gcc_path" ]; then
            if [ -n "$env_cmd" ]; then
                env_cmd="$env_cmd CC=\"$gcc_path\""
            else
                env_cmd="CC=\"$gcc_path\""
            fi
        fi
        
        # 使用 bash -c 来正确设置环境变量
        # 将命令数组转换为字符串
        local cmd_str="${vllm_cmd_array[*]}"
        nohup bash -c "export $env_cmd && $cmd_str" > "$log_file" 2>&1 &
    else
        nohup "${vllm_cmd_array[@]}" > "$log_file" 2>&1 &
    fi
    
    local pid=$!
    echo "$pid" > "$pid_file"
    
    # 等待几秒检查进程是否还在运行
    sleep 3
    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${RED}✗ 模型 $model_name 启动失败（进程已退出），请查看日志: $log_file${NC}"
        rm -f "$pid_file"
        return 1
    fi
    
    # 额外检查：等待更长时间，然后检查端口是否真正监听
    # 模型加载需要时间，给更多时间让服务完全启动
    echo -e "${CYAN}等待模型加载（最多60秒）...${NC}"
    local max_wait=60
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if ! ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${RED}✗ 模型 $model_name 启动失败（进程在加载过程中退出），请查看日志: $log_file${NC}"
            rm -f "$pid_file"
            return 1
        fi
        
        # 检查端口是否监听
        if check_port "$port"; then
            echo -e "${GREEN}✓ 模型 $model_name 启动成功 (PID: $pid, 端口: $port)${NC}"
            if [ -n "$cuda_visible_devices" ]; then
                echo -e "  GPU: $cuda_visible_devices"
            fi
            echo -e "  日志文件: $log_file"
            echo -e "  API地址: http://${VLLM_HOST}:${port}/v1"
            return 0
        fi
        
        sleep 2
        waited=$((waited + 2))
        if [ $((waited % 10)) -eq 0 ]; then
            echo -e "${CYAN}  已等待 ${waited} 秒，继续等待...${NC}"
        fi
    done
    
    # 超时检查：进程还在但端口未监听，可能是加载失败
    if ! check_port "$port"; then
        echo -e "${YELLOW}⚠ 模型 $model_name 进程运行中但端口未监听（可能仍在加载或加载失败），请检查日志: $log_file${NC}"
        echo -e "  PID: $pid"
        echo -e "  日志文件: $log_file"
        # 不返回失败，让用户自己判断
        return 0
    fi
}

# 停止单个模型
stop_model() {
    local model_name=$1
    local pid_file=$(get_pid_file "$model_name")
    
    if [ ! -f "$pid_file" ]; then
        echo -e "${YELLOW}模型 $model_name 未运行（PID文件不存在）${NC}"
        return 1
    fi
    
    local pid=$(cat "$pid_file")
    
    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${YELLOW}模型 $model_name 未运行（进程不存在）${NC}"
        rm -f "$pid_file"
        return 1
    fi
    
    echo -e "${CYAN}停止模型: $model_name (PID: $pid)${NC}"
    
    # 获取所有子进程
    local child_pids=$(get_child_pids "$pid")
    local all_pids="$pid $child_pids"
    
    # 先尝试正常终止（SIGTERM）
    for p in $all_pids; do
        if ps -p "$p" > /dev/null 2>&1; then
            kill "$p" 2>/dev/null || true
        fi
    done
    
    # 等待进程结束
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done
    
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${YELLOW}模型 $model_name 未能正常停止，尝试强制终止...${NC}"
        # 强制终止所有进程
        for p in $all_pids; do
            if ps -p "$p" > /dev/null 2>&1; then
                kill -9 "$p" 2>/dev/null || true
            fi
        done
        sleep 1
    fi
    
    # 清理可能残留的进程
    cleanup_model_by_name "$model_name"
    
    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 模型 $model_name 已停止${NC}"
        rm -f "$pid_file"
        return 0
    else
        echo -e "${RED}✗ 无法停止模型 $model_name${NC}"
        return 1
    fi
}

# 获取进程的所有子进程PID
get_child_pids() {
    local parent_pid=$1
    local child_pids=""
    
    # 使用 pstree 或 ps 来查找子进程
    if command -v pstree >/dev/null 2>&1; then
        # 使用 pstree 获取所有子进程（最可靠的方法）
        child_pids=$(pstree -p "$parent_pid" 2>/dev/null | grep -oP '\(\K[0-9]+' | grep -v "^${parent_pid}$" || true)
    elif command -v pgrep >/dev/null 2>&1; then
        # 使用 pgrep 查找所有子进程（通过进程组）
        local pgid=$(ps -o pgid= -p "$parent_pid" 2>/dev/null | tr -d ' ' || true)
        if [ -n "$pgid" ] && [ "$pgid" != "1" ]; then
            # 获取进程组中的所有进程（排除父进程本身）
            child_pids=$(pgrep -g "$pgid" 2>/dev/null | grep -v "^${parent_pid}$" || true)
        fi
        # 如果没有找到，回退到直接子进程
        if [ -z "$child_pids" ]; then
            child_pids=$(ps -o pid= --ppid "$parent_pid" 2>/dev/null || true)
        fi
    else
        # 使用 ps 查找直接子进程（简单方法，可能不完整）
        child_pids=$(ps -o pid= --ppid "$parent_pid" 2>/dev/null || true)
    fi
    
    echo "$child_pids" | tr ' ' '\n' | grep -v '^$' | sort -u
}

# 强制杀死模型进程（包括所有子进程）
kill_model() {
    local model_name=$1
    local pid_file=$(get_pid_file "$model_name")
    
    if [ ! -f "$pid_file" ]; then
        echo -e "${YELLOW}模型 $model_name 未运行（PID文件不存在）${NC}"
        # 即使没有PID文件，也尝试通过端口查找并清理残留进程
        cleanup_model_by_name "$model_name"
        return 1
    fi
    
    local pid=$(cat "$pid_file")
    
    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${YELLOW}模型 $model_name 未运行（进程不存在）${NC}"
        rm -f "$pid_file"
        # 清理可能残留的进程
        cleanup_model_by_name "$model_name"
        return 1
    fi
    
    echo -e "${RED}强制终止模型: $model_name (PID: $pid)${NC}"
    
    # 获取所有子进程
    local child_pids=$(get_child_pids "$pid")
    local all_pids="$pid $child_pids"
    
    # 先尝试正常终止（SIGTERM）
    for p in $all_pids; do
        if ps -p "$p" > /dev/null 2>&1; then
            kill "$p" 2>/dev/null || true
        fi
    done
    
    # 等待1秒
    sleep 1
    
    # 强制终止所有仍在运行的进程
    for p in $all_pids; do
        if ps -p "$p" > /dev/null 2>&1; then
            kill -9 "$p" 2>/dev/null || true
        fi
    done
    
    # 额外清理：通过进程组终止
    if ps -p "$pid" > /dev/null 2>&1; then
        # 尝试通过进程组终止
        local pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
        if [ -n "$pgid" ] && [ "$pgid" != "1" ]; then
            kill -9 -"$pgid" 2>/dev/null || true
        fi
    fi
    
    sleep 1
    
    # 清理可能残留的 vLLM 进程（通过端口或模型路径）
    cleanup_model_by_name "$model_name"
    
    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 模型 $model_name 已强制终止（包括所有子进程）${NC}"
        rm -f "$pid_file"
        return 0
    else
        echo -e "${RED}✗ 无法完全终止模型 $model_name，请手动检查${NC}"
        return 1
    fi
}

# 通过模型名称清理残留进程（通过端口或进程名）
cleanup_model_by_name() {
    local model_name=$1
    local config="${MODEL_CONFIG[$model_name]}"
    
    if [ -z "$config" ]; then
        return 1
    fi
    
    IFS='|' read -r model_id port model_path <<< "$config"
    
    # 通过端口查找并终止进程
    if [ -n "$port" ]; then
        local port_pids=$(lsof -ti :$port 2>/dev/null || true)
        if [ -n "$port_pids" ]; then
            echo -e "${YELLOW}  发现端口 $port 上的残留进程，正在清理...${NC}"
            for p in $port_pids; do
                if ps -p "$p" > /dev/null 2>&1; then
                    local child_pids=$(get_child_pids "$p")
                    kill -9 "$p" $child_pids 2>/dev/null || true
                fi
            done
            sleep 0.5
        fi
    fi
    
    # 通过 vLLM 进程名和模型路径查找残留进程
    local vllm_pids=$(ps aux | grep -E "vllm.*$model_path|vllm.*$model_id" | grep -v grep | awk '{print $2}' || true)
    if [ -n "$vllm_pids" ]; then
        echo -e "${YELLOW}  发现 vLLM 残留进程，正在清理...${NC}"
        for p in $vllm_pids; do
            if ps -p "$p" > /dev/null 2>&1; then
                local child_pids=$(get_child_pids "$p")
                kill -9 "$p" $child_pids 2>/dev/null || true
            fi
        done
        sleep 0.5
    fi
}

# 查看模型状态
show_status() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}模型运行状态${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    local running_count=0
    local stopped_count=0
    
    for model_name in "${!MODEL_CONFIG[@]}"; do
        local config="${MODEL_CONFIG[$model_name]}"
        IFS='|' read -r model_id port model_path <<< "$config"
        
        local pid_file=$(get_pid_file "$model_name")
        local status=""
        local pid=""
        local port_status=""
        
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if ps -p "$pid" > /dev/null 2>&1; then
                status="${GREEN}运行中${NC}"
                running_count=$((running_count + 1))
                
                # 检查端口
                if check_port "$port"; then
                    port_status="${GREEN}监听中${NC}"
                else
                    port_status="${YELLOW}未监听${NC}"
                fi
            else
                status="${RED}已停止${NC} (PID文件存在但进程不存在)"
                stopped_count=$((stopped_count + 1))
                port_status="${RED}未监听${NC}"
                rm -f "$pid_file"
            fi
        else
            status="${YELLOW}未运行${NC}"
            stopped_count=$((stopped_count + 1))
            port_status="${YELLOW}未监听${NC}"
        fi
        
        echo -e "${CYAN}模型: $model_name${NC}"
        echo -e "  状态: $status"
        if [ -n "$pid" ]; then
            echo -e "  PID: $pid"
        fi
        echo -e "  端口: $port ($port_status)"
        echo -e "  模型ID: $model_id"
        
        # 显示GPU配置
        local gpu_config="${GPU_CONFIG[$model_name]}"
        if [ -n "$gpu_config" ]; then
            IFS='|' read -r gpu_devices tensor_parallel_size <<< "$gpu_config"
            echo -e "  GPU设备: $gpu_devices (张量并行度: $tensor_parallel_size)"
        fi
        
        if [ "$port_status" = "${GREEN}监听中${NC}" ]; then
            echo -e "  API地址: http://${VLLM_HOST}:${port}/v1"
        fi
        echo ""
    done
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "运行中: ${GREEN}$running_count${NC} 个"
    echo -e "已停止: ${YELLOW}$stopped_count${NC} 个"
    echo -e "总计: ${#MODEL_CONFIG[@]} 个"
    echo -e "${BLUE}========================================${NC}"
}

# 主函数
main() {
    local command=${1:-status}
    
    case "$command" in
        start)
            echo -e "${BLUE}启动所有配置的模型...${NC}"
            echo ""
            local success_count=0
            local fail_count=0
            
            # 临时禁用 set -e，确保即使某个模型启动失败也能继续启动其他模型
            set +e
            for model_name in "${!MODEL_CONFIG[@]}"; do
                if start_model "$model_name" "${MODEL_CONFIG[$model_name]}"; then
                    success_count=$((success_count + 1))
                else
                    fail_count=$((fail_count + 1))
                fi
                echo ""
            done
            set -e  # 恢复 set -e
            
            echo -e "${BLUE}启动完成: 成功 $success_count 个, 失败 $fail_count 个${NC}"
            ;;
            
        stop)
            if [ -n "$2" ]; then
                # 停止指定模型
                local model_name=$2
                if [ -z "${MODEL_CONFIG[$model_name]}" ]; then
                    echo -e "${RED}错误: 未找到模型配置: $model_name${NC}"
                    echo -e "可用模型: ${!MODEL_CONFIG[@]}"
                    exit 1
                fi
                stop_model "$model_name"
            else
                # 停止所有模型
                echo -e "${BLUE}停止所有模型...${NC}"
                echo ""
                local success_count=0
                local fail_count=0
                
                # 临时禁用 set -e，确保即使某个模型停止失败也能继续停止其他模型
                set +e
                for model_name in "${!MODEL_CONFIG[@]}"; do
                    if stop_model "$model_name"; then
                        success_count=$((success_count + 1))
                    else
                        fail_count=$((fail_count + 1))
                    fi
                done
                set -e  # 恢复 set -e
                
                echo ""
                echo -e "${BLUE}停止完成: 成功 $success_count 个, 失败 $fail_count 个${NC}"
            fi
            ;;
            
        kill)
            if [ -n "$2" ]; then
                # 强制终止指定模型
                local model_name=$2
                if [ -z "${MODEL_CONFIG[$model_name]}" ]; then
                    echo -e "${RED}错误: 未找到模型配置: $model_name${NC}"
                    echo -e "可用模型: ${!MODEL_CONFIG[@]}"
                    exit 1
                fi
                kill_model "$model_name"
            else
                # 强制终止所有模型
                echo -e "${RED}强制终止所有模型...${NC}"
                echo ""
                local success_count=0
                local fail_count=0
                
                # 临时禁用 set -e，确保即使某个模型终止失败也能继续终止其他模型
                set +e
                for model_name in "${!MODEL_CONFIG[@]}"; do
                    if kill_model "$model_name"; then
                        success_count=$((success_count + 1))
                    else
                        fail_count=$((fail_count + 1))
                    fi
                done
                set -e  # 恢复 set -e
                
                echo ""
                echo -e "${BLUE}终止完成: 成功 $success_count 个, 失败 $fail_count 个${NC}"
            fi
            ;;
            
        status)
            show_status
            ;;
            
        cleanup)
            # 清理所有残留的 vLLM 进程
            echo -e "${YELLOW}清理所有残留的 vLLM 进程...${NC}"
            echo ""
            
            local cleaned_count=0
            
            # 清理所有配置的模型
            set +e
            for model_name in "${!MODEL_CONFIG[@]}"; do
                cleanup_model_by_name "$model_name"
                cleaned_count=$((cleaned_count + 1))
            done
            set -e
            
            # 清理所有占用配置端口的进程
            echo -e "${CYAN}检查配置的端口...${NC}"
            for model_name in "${!MODEL_CONFIG[@]}"; do
                local config="${MODEL_CONFIG[$model_name]}"
                IFS='|' read -r model_id port model_path <<< "$config"
                if [ -n "$port" ]; then
                    local port_pids=$(lsof -ti :$port 2>/dev/null || true)
                    if [ -n "$port_pids" ]; then
                        echo -e "${YELLOW}  端口 $port 上仍有进程，正在清理...${NC}"
                        for p in $port_pids; do
                            if ps -p "$p" > /dev/null 2>&1; then
                                local child_pids=$(get_child_pids "$p")
                                kill -9 "$p" $child_pids 2>/dev/null || true
                                echo -e "  ${GREEN}✓ 已终止进程 $p 及其子进程${NC}"
                            fi
                        done
                    fi
                fi
            done
            
            # 清理所有 vLLM 相关进程（通过进程名）
            echo -e "${CYAN}检查所有 vLLM 进程...${NC}"
            local all_vllm_pids=$(ps aux | grep -E "vllm\.entrypoints\.openai\.api_server|python.*vllm" | grep -v grep | awk '{print $2}' | sort -u || true)
            if [ -n "$all_vllm_pids" ]; then
                echo -e "${YELLOW}  发现以下 vLLM 进程，正在清理...${NC}"
                for p in $all_vllm_pids; do
                    if ps -p "$p" > /dev/null 2>&1; then
                        local child_pids=$(get_child_pids "$p")
                        echo -e "  ${YELLOW}终止进程 $p 及其子进程: $child_pids${NC}"
                        kill -9 "$p" $child_pids 2>/dev/null || true
                    fi
                done
                sleep 1
            else
                echo -e "${GREEN}  未发现残留的 vLLM 进程${NC}"
            fi
            
            # 清理所有 PID 文件（如果对应的进程不存在）
            echo -e "${CYAN}清理无效的 PID 文件...${NC}"
            for pid_file in "$PID_DIR"/*.pid; do
                if [ -f "$pid_file" ]; then
                    local pid=$(cat "$pid_file" 2>/dev/null || true)
                    if [ -n "$pid" ] && ! ps -p "$pid" > /dev/null 2>&1; then
                        local model_name=$(basename "$pid_file" .pid)
                        rm -f "$pid_file"
                        echo -e "  ${GREEN}✓ 已清理无效的 PID 文件: $model_name${NC}"
                    fi
                fi
            done
            
            echo ""
            echo -e "${GREEN}✓ 清理完成${NC}"
            echo -e "${CYAN}提示: 如果显存仍被占用，可能需要等待几秒让 CUDA 上下文释放，或重启系统${NC}"
            ;;
            
        *)
            echo "使用方法: $0 {start|stop|kill|status|cleanup} [model_name]"
            echo ""
            echo "命令说明:"
            echo "  start         启动所有配置的模型"
            echo "  stop          停止所有模型"
            echo "  stop <name>   停止指定模型"
            echo "  kill          强制终止所有模型（包括子进程）"
            echo "  kill <name>   强制终止指定模型（包括子进程）"
            echo "  status        查看所有模型运行状态"
            echo "  cleanup       清理所有残留的 vLLM 进程和无效 PID 文件"
            echo ""
            echo "配置的模型:"
            for model_name in "${!MODEL_CONFIG[@]}"; do
                echo "  - $model_name"
            done
            exit 1
            ;;
    esac
}

main "$@"
