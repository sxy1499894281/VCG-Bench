#!/bin/bash
# HuggingFace模型服务管理脚本
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
#   ./manage_models.sh kill       # 强制杀死所有模型进程
#   ./manage_models.sh kill <model_name>  # 强制杀死指定模型进程

set -e

# ==================== 配置区域 ====================
# 脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSGBENCH_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# 模型配置（格式: "模型名称|端口|模型路径"）
# 模型路径可以是HuggingFace模型ID或本地路径
# 如果使用本地路径，应该是下载后的模型目录
declare -A MODEL_CONFIG
MODEL_CONFIG["llava-1.5-7b-hf"]="llava-hf/llava-1.5-7b-hf|8004|llava-hf_llava-1.5-7b-hf"
# 添加更多模型配置...
# MODEL_CONFIG["model-name"]="org/model-id|8002|org_model-id"

# GPU分配配置（格式: "GPU设备ID|张量并行度"）
# GPU设备ID: 单个GPU用数字，多个GPU用逗号分隔，例如 "0" 或 "0,1" 或 "0,1,2,3"
# 张量并行度: 使用几张GPU进行张量并行，通常等于GPU数量，例如 1 或 2 或 4
# 注意: 如果使用多GPU张量并行，GPU设备ID应该包含所有要使用的GPU
# 示例:
#   "0|1"      - 使用GPU 0，单卡运行（适合7B-13B模型）
#   "1|1"      - 使用GPU 1，单卡运行
#   "2,3|2"    - 使用GPU 2和3，双卡张量并行（适合大模型）
#   "4,5,6,7|4" - 使用GPU 4,5,6,7，四卡张量并行（适合超大模型）
declare -A GPU_CONFIG
GPU_CONFIG["llava-1.5-7b-hf"]="0|1"          # 使用GPU 0，单卡运行
# 添加更多GPU配置...
# GPU_CONFIG["model-name"]="1|1"              # 使用GPU 1，单卡运行
# GPU_CONFIG["large-model"]="2,3|2"          # 使用GPU 2和3，双卡张量并行

# 模型保存目录（相对于VCG-Bench根目录）
MODELS_DIR="$CSGBENCH_DIR/models/huggingface"

# 日志目录
LOG_DIR="$CSGBENCH_DIR/logs"
mkdir -p "$LOG_DIR"

# PID文件目录（用于跟踪运行中的进程）
PID_DIR="$CSGBENCH_DIR/models/huggingface/pids"
mkdir -p "$PID_DIR"

# vLLM启动参数（可根据需要修改）
VLLM_HOST="0.0.0.0"
VLLM_GPU_MEMORY_UTILIZATION="0.9"
# 不设置 max_model_len，让 vLLM 自动使用模型的最大长度

# Python环境配置（vLLM所在的conda环境）
# 如果vLLM安装在conda环境中，设置环境名称或Python路径
# 例如: VLLM_PYTHON_ENV="xysu" 或 VLLM_PYTHON="/path/to/python"
VLLM_PYTHON_ENV="xysu"  # conda环境名称，如果为空则使用系统Python

# HuggingFace镜像配置（使用hf-mirror.com代理）
export HF_ENDPOINT="https://hf-mirror.com"
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
    
    # 如果本地路径存在，使用本地路径；否则使用HuggingFace ID
    if [ -d "$local_path" ]; then
        echo "$local_path"
    else
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
    echo -e "  HuggingFace镜像: $HF_ENDPOINT"
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
    local vllm_cmd_array=(
        $python_cmd -m vllm.entrypoints.openai.api_server
        --model "$actual_model_path"
        --served-model-name "$model_id"
        --host "$VLLM_HOST"
        --port "$port"
        --gpu-memory-utilization "$VLLM_GPU_MEMORY_UTILIZATION"
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
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 模型 $model_name 启动成功 (PID: $pid, 端口: $port)${NC}"
        if [ -n "$cuda_visible_devices" ]; then
            echo -e "  GPU设备: $cuda_visible_devices"
        fi
        echo -e "  日志文件: $log_file"
        echo -e "  API地址: http://${VLLM_HOST}:${port}/v1"
        return 0
    else
        echo -e "${RED}✗ 模型 $model_name 启动失败，请查看日志: $log_file${NC}"
        rm -f "$pid_file"
        return 1
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
    kill "$pid" 2>/dev/null || true
    
    # 等待进程结束
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done
    
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${YELLOW}模型 $model_name 未能正常停止，尝试强制终止...${NC}"
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
    fi
    
    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 模型 $model_name 已停止${NC}"
        rm -f "$pid_file"
        return 0
    else
        echo -e "${RED}✗ 无法停止模型 $model_name${NC}"
        return 1
    fi
}

# 强制杀死模型进程
kill_model() {
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
    
    echo -e "${RED}强制终止模型: $model_name (PID: $pid)${NC}"
    kill -9 "$pid" 2>/dev/null || true
    sleep 1
    
    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 模型 $model_name 已强制终止${NC}"
        rm -f "$pid_file"
        return 0
    else
        echo -e "${RED}✗ 无法终止模型 $model_name${NC}"
        return 1
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
        
        # 获取GPU配置
        local gpu_config="${GPU_CONFIG[$model_name]}"
        local gpu_info=""
        if [ -n "$gpu_config" ]; then
            IFS='|' read -r gpu_devices tensor_parallel_size <<< "$gpu_config"
            gpu_info="GPU: $gpu_devices (TP=$tensor_parallel_size)"
        fi
        
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
        if [ -n "$gpu_info" ]; then
            echo -e "  $gpu_info"
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
            
            for model_name in "${!MODEL_CONFIG[@]}"; do
                if start_model "$model_name" "${MODEL_CONFIG[$model_name]}"; then
                    success_count=$((success_count + 1))
                else
                    fail_count=$((fail_count + 1))
                fi
                echo ""
            done
            
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
                
                for model_name in "${!MODEL_CONFIG[@]}"; do
                    if stop_model "$model_name"; then
                        success_count=$((success_count + 1))
                    else
                        fail_count=$((fail_count + 1))
                    fi
                done
                
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
                
                for model_name in "${!MODEL_CONFIG[@]}"; do
                    if kill_model "$model_name"; then
                        success_count=$((success_count + 1))
                    else
                        fail_count=$((fail_count + 1))
                    fi
                done
                
                echo ""
                echo -e "${BLUE}终止完成: 成功 $success_count 个, 失败 $fail_count 个${NC}"
            fi
            ;;
            
        status)
            show_status
            ;;
            
        *)
            echo "使用方法: $0 {start|stop|kill|status} [model_name]"
            echo ""
            echo "命令说明:"
            echo "  start         启动所有配置的模型"
            echo "  stop          停止所有模型"
            echo "  stop <name>   停止指定模型"
            echo "  kill          强制终止所有模型"
            echo "  kill <name>   强制终止指定模型"
            echo "  status        查看所有模型运行状态"
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
