# HuggingFace 模型管理脚本使用指南

本目录包含用于管理 HuggingFace 模型的脚本工具，包括模型下载和模型服务管理功能。所有脚本都配置为使用 `hf-mirror.com` 代理来加速下载。

## 文件说明

- `download_models.py` - 从 HuggingFace 批量下载模型的 Python 脚本（使用 hf-mirror.com 代理）
- `manage_models.sh` - 管理模型服务的 Bash 脚本（启动、停止、查看状态等）
- `README.md` - 本使用说明文档

## 前置要求

### 1. 安装依赖

```bash
# 安装 HuggingFace Hub
pip install huggingface_hub

# 安装 vLLM（用于运行模型服务）
pip install vllm

# 如果使用 GPU，确保已安装 CUDA 和相应的 PyTorch 版本
```

### 2. 配置环境

确保你的系统已配置好：
- Python 3.8+
- CUDA（如果使用 GPU）
- 足够的磁盘空间（模型文件通常很大，每个模型可能需要几十GB）

### 3. 配置代理（使用 hf-mirror.com）

脚本已自动配置使用 `hf-mirror.com` 作为 HuggingFace 镜像代理，无需额外配置。

**原理说明：**
- 脚本通过设置 `HF_ENDPOINT` 环境变量来使用镜像
- 默认镜像地址：`https://hf-mirror.com`
- 如果需要修改镜像地址，可以在脚本中修改 `HF_MIRROR` 变量

**手动配置代理（可选）：**

如果你想在其他地方手动使用代理，可以设置环境变量：

```bash
# 临时设置（当前终端会话）
export HF_ENDPOINT="https://hf-mirror.com"

# 永久设置（添加到 ~/.bashrc 或 ~/.zshrc）
echo 'export HF_ENDPOINT="https://hf-mirror.com"' >> ~/.bashrc
source ~/.bashrc
```

**验证代理是否生效：**

```bash
# 检查环境变量
echo $HF_ENDPOINT

# 或者在 Python 中检查
python -c "import os; print(os.environ.get('HF_ENDPOINT', 'Not set'))"
```

## 使用指南

### 一、下载模型

#### 1. 配置要下载的模型

编辑 `download_models.py` 文件，在脚本开头的配置区域修改 `MODEL_LIST`：

```python
MODEL_LIST = [
    "llava-hf/llava-1.5-7b-hf",
    # 添加更多模型...
    # "model-org/model-name",
]
```

#### 2. 配置保存目录（可选）

默认保存到 `VCG-Bench/models/huggingface/`，如需修改，编辑脚本中的 `SAVE_DIR` 变量。

#### 3. 配置镜像地址（可选）

默认使用 `https://hf-mirror.com`，如需修改，编辑脚本中的 `HF_MIRROR` 变量。

#### 4. 执行下载

```bash
cd VCG-Bench/scripts/local_model/huggingface

# 直接运行
python download_models.py

# 或者使用 nohup 后台运行
nohup python download_models.py > download.log 2>&1 &
```

#### 5. 查看下载进度

下载脚本会自动显示下载进度，每10秒输出一次状态信息，包括：
- 已下载的文件大小
- 当前下载速度
- 如果下载速度较慢，会提示"下载速度较慢或暂停中"

**实时查看日志：**

```bash
# 查看日志文件（推荐）
tail -f ../../logs/huggingface_download.log

# 或者如果使用 nohup
tail -f download.log
```

**日志输出示例：**

```
2026-01-05 15:39:12,096 - INFO - 开始下载模型: llava-hf/llava-1.5-7b-hf
2026-01-05 15:39:12,097 - INFO -   正在连接镜像服务器并开始下载...
2026-01-05 15:39:12,098 - INFO -   提示: 每10秒会输出一次下载进度，请耐心等待...
2026-01-05 15:39:22,100 - INFO -   📥 下载中... 已下载: 125.50 MB | 速度: 12.55 MB/s
2026-01-05 15:39:32,105 - INFO -   📥 下载中... 已下载: 250.30 MB | 速度: 12.48 MB/s
2026-01-05 15:39:42,110 - INFO -   📥 下载中... 已下载: 375.20 MB | 速度: 12.49 MB/s
...
2026-01-05 15:45:00,200 - INFO - ✓ 模型下载完成: llava-hf/llava-1.5-7b-hf
2026-01-05 15:45:00,201 - INFO -   保存路径: /path/to/models/huggingface/llava-hf_llava-1.5-7b-hf
2026-01-05 15:45:00,202 - INFO -   总大小: 13.50 GB
2026-01-05 15:45:00,203 - INFO -   本次下载: 13.50 GB
2026-01-05 15:45:00,204 - INFO -   耗时: 5.8 分钟 (348.1 秒)
2026-01-05 15:45:00,205 - INFO -   平均速度: 39.78 MB/s
```

**如何判断下载是否正常运行：**

1. **有进度输出**: 每10秒会看到 `📥 下载中...` 的日志，说明正在下载
2. **文件大小在增长**: 已下载的大小应该持续增加
3. **有下载速度**: 速度应该大于0（如果为0或很小，可能是网络问题）
4. **没有错误信息**: 如果看到错误信息，说明下载出现问题

**如果长时间没有进度输出：**

- 可能是网络较慢，请耐心等待
- 如果超过1分钟没有输出，可以检查网络连接
- 脚本支持断点续传，如果中断可以重新运行

### 二、管理模型服务

#### 1. 配置模型服务

编辑 `manage_models.sh` 文件，在脚本开头的配置区域修改 `MODEL_CONFIG`：

```bash
declare -A MODEL_CONFIG
MODEL_CONFIG["llava-1.5-7b-hf"]="llava-hf/llava-1.5-7b-hf|8001|llava-hf_llava-1.5-7b-hf"
# 添加更多模型配置...
# MODEL_CONFIG["model-name"]="org/model-id|8002|org_model-id"
```

配置格式：`"模型名称|端口|模型路径"`
- **模型名称**: 用于标识的简短名称
- **端口**: 服务监听的端口号
- **模型路径**: HuggingFace 模型ID 或本地路径（如果已下载，使用下划线替换斜杠，如 `llava-hf_llava-1.5-7b-hf`）

#### 2. 配置GPU分配（重要！）

编辑 `manage_models.sh` 文件，在脚本开头的配置区域修改 `GPU_CONFIG`：

```bash
declare -A GPU_CONFIG
GPU_CONFIG["llava-1.5-7b-hf"]="0|1"          # 使用GPU 0，单卡运行
# 添加更多GPU配置...
# GPU_CONFIG["model-name"]="1|1"              # 使用GPU 1，单卡运行
# GPU_CONFIG["large-model"]="2,3|2"          # 使用GPU 2和3，双卡张量并行
```

**配置格式：`"GPU设备ID|张量并行度"`**
- **GPU设备ID**: 
  - 单个GPU: 使用数字，例如 `"0"` 表示使用GPU 0
  - 多个GPU: 使用逗号分隔，例如 `"0,1"` 表示使用GPU 0和1，`"2,3,4,5"` 表示使用GPU 2,3,4,5
- **张量并行度**: 
  - 单卡运行: `1`（适合7B-13B模型，通常需要12-24GB显存）
  - 双卡张量并行: `2`（适合13B-30B模型，每卡需要12-24GB显存）
  - 四卡张量并行: `4`（适合30B+模型，每卡需要12-24GB显存）

**8卡服务器GPU分配示例：**

```bash
# 示例1: 每个模型使用单卡（适合7B-13B模型）
GPU_CONFIG["model1"]="0|1"   # GPU 0
GPU_CONFIG["model2"]="1|1"   # GPU 1
GPU_CONFIG["model3"]="2|1"   # GPU 2
GPU_CONFIG["model4"]="3|1"   # GPU 3
GPU_CONFIG["model5"]="4|1"   # GPU 4
GPU_CONFIG["model6"]="5|1"   # GPU 5
GPU_CONFIG["model7"]="6|1"   # GPU 6
GPU_CONFIG["model8"]="7|1"   # GPU 7

# 示例2: 混合使用（小模型单卡，大模型多卡）
GPU_CONFIG["small-model-1"]="0|1"      # GPU 0，单卡
GPU_CONFIG["small-model-2"]="1|1"      # GPU 1，单卡
GPU_CONFIG["medium-model"]="2,3|2"     # GPU 2,3，双卡张量并行
GPU_CONFIG["large-model"]="4,5,6,7|4"   # GPU 4,5,6,7，四卡张量并行
```

**如何估算模型显存需求：**

1. **查看GPU显存：**
   ```bash
   nvidia-smi
   ```

2. **模型显存估算（FP16/BF16）：**
   - 7B模型: 约14GB（单卡）
   - 13B模型: 约26GB（单卡或双卡）
   - 30B模型: 约60GB（需要多卡，建议4卡或更多）
   - 70B模型: 约140GB（需要8卡或更多）

3. **实际显存使用：**
   - vLLM会使用配置的 `gpu-memory-utilization`（默认0.9，即90%）
   - 如果显存不足，可以降低 `VLLM_GPU_MEMORY_UTILIZATION`（例如改为0.8或0.7）

4. **查看GPU使用情况：**
   ```bash
   # 实时查看
   watch -n 1 nvidia-smi
   
   # 或者
   nvidia-smi -l 1
   ```

**注意事项：**
- 确保每个GPU只分配给一个模型，避免冲突
- 如果模型显存需求超过单卡容量，必须使用多卡张量并行
- 张量并行度必须等于GPU设备ID中指定的GPU数量
- 如果不配置GPU_CONFIG，模型将使用所有可用GPU（不推荐）

#### 3. 给脚本添加执行权限

```bash
chmod +x manage_models.sh
```

#### 4. 启动模型服务

```bash
cd VCG-Bench/scripts/local_model/huggingface

# 启动所有配置的模型
./manage_models.sh start

# 查看帮助
./manage_models.sh
```

#### 5. 查看运行状态

```bash
./manage_models.sh status
```

输出示例：
```
========================================
模型运行状态
========================================

模型: llava-1.5-7b-hf
  状态: 运行中
  PID: 12345
  端口: 8001 (监听中)
  模型ID: llava-hf/llava-1.5-7b-hf
  GPU: 0 (TP=1)
  API地址: http://0.0.0.0:8001/v1

...
```

#### 6. 停止模型服务

```bash
# 停止所有模型
./manage_models.sh stop

# 停止指定模型
./manage_models.sh stop llava-1.5-7b-hf
```

#### 7. 强制终止模型进程

如果正常停止失败，可以使用 kill 命令：

```bash
# 强制终止所有模型
./manage_models.sh kill

# 强制终止指定模型
./manage_models.sh kill llava-1.5-7b-hf
```

### 三、后台运行

#### 使用 nohup 后台运行下载脚本

```bash
# 后台运行下载脚本
nohup python download_models.py > download_models.log 2>&1 &

# 查看运行状态
tail -f download_models.log

# 查看进程
ps aux | grep download_models.py

# 如果需要停止后台进程
# 先找到进程ID
ps aux | grep download_models.py
# 然后终止
kill <PID>
```

#### 使用 nohup 后台运行模型服务

模型服务脚本已经使用 nohup 在后台启动，但如果你想手动使用 nohup：

```bash
# 后台运行管理脚本（启动所有模型）
nohup ./manage_models.sh start > manage_models.log 2>&1 &

# 查看日志
tail -f manage_models.log
```

#### 使用 screen 或 tmux（推荐）

对于长时间运行的任务，建议使用 screen 或 tmux：

```bash
# 使用 screen
screen -S model_download
python download_models.py
# 按 Ctrl+A 然后 D 退出（进程继续运行）

# 重新连接
screen -r model_download

# 使用 tmux
tmux new -s model_download
python download_models.py
# 按 Ctrl+B 然后 D 退出

# 重新连接
tmux attach -t model_download
```

## 配置说明

### download_models.py 配置项

- `MODEL_LIST`: 要下载的模型列表（HuggingFace 模型ID）
- `SAVE_DIR`: 模型保存目录（默认: `VCG-Bench/models/huggingface/`）
- `HF_MIRROR`: HuggingFace 镜像地址（默认: `https://hf-mirror.com`）
- `LOG_DIR`: 日志目录（默认: `VCG-Bench/logs/`）

### manage_models.sh 配置项

- `MODEL_CONFIG`: 模型服务配置（格式: `"名称|端口|模型路径"`）
- `GPU_CONFIG`: GPU分配配置（格式: `"GPU设备ID|张量并行度"`）
  - 示例: `"0|1"` 表示使用GPU 0，单卡运行
  - 示例: `"2,3|2"` 表示使用GPU 2和3，双卡张量并行
- `MODELS_DIR`: 模型保存目录
- `LOG_DIR`: 日志目录
- `PID_DIR`: PID 文件目录（用于跟踪运行中的进程）
- `VLLM_HOST`: vLLM 服务监听地址（默认: `0.0.0.0`）
- `VLLM_GPU_MEMORY_UTILIZATION`: GPU 内存使用率（默认: `0.9`，可降低以节省显存）
- `VLLM_MAX_MODEL_LEN`: 最大模型长度（默认: `8192`）
- `HF_ENDPOINT`: HuggingFace 镜像地址（默认: `https://hf-mirror.com`）

## 日志文件

- 下载日志: `VCG-Bench/logs/huggingface_download.log`
- 模型服务日志: `VCG-Bench/logs/vllm_<模型名>_<端口>.log`
- PID 文件: `VCG-Bench/models/huggingface/pids/<模型名>.pid`

## 常见问题

### 1. 下载失败

- **检查网络连接**: 确保可以访问 hf-mirror.com
- **检查磁盘空间**: 确保有足够的磁盘空间
- **检查 HuggingFace 模型ID**: 确保模型ID正确
- **查看日志**: 检查 `logs/huggingface_download.log` 获取详细错误信息
- **检查代理配置**: 确认 `HF_ENDPOINT` 环境变量已正确设置

### 2. 模型服务启动失败

- **检查端口占用**: 使用 `lsof -i :端口号` 检查端口是否被占用
- **检查 GPU 内存**: 
  - 如果 GPU 内存不足，降低 `VLLM_GPU_MEMORY_UTILIZATION`（例如改为0.8或0.7）
  - 使用 `nvidia-smi` 查看GPU显存使用情况
  - 确保分配的GPU有足够显存
- **检查GPU配置**: 
  - 确保 `GPU_CONFIG` 中配置的GPU没有被其他模型占用
  - 检查张量并行度是否等于GPU数量
  - 使用 `nvidia-smi` 查看GPU是否被占用
- **检查模型路径**: 确保模型已下载或 HuggingFace ID 正确
- **查看日志**: 检查 `logs/vllm_<模型名>_<端口>.log` 获取详细错误信息
- **检查代理配置**: 确认模型服务启动时能访问 HuggingFace 镜像

### 3. 端口冲突

如果端口被占用，可以：
- 修改 `manage_models.sh` 中的端口配置
- 停止占用端口的进程
- 使用 `./manage_models.sh status` 查看当前使用的端口

### 4. 进程无法停止

如果正常停止失败：
```bash
# 使用 kill 命令强制终止
./manage_models.sh kill

# 或者手动查找并终止
ps aux | grep vllm
kill -9 <PID>
```

### 5. GPU相关问题

**问题：如何查看GPU使用情况**

```bash
# 实时查看GPU使用情况
watch -n 1 nvidia-smi

# 或者持续监控
nvidia-smi -l 1

# 查看特定进程的GPU使用
nvidia-smi pmon
```

**问题：如何知道模型需要多少显存**

1. 查看模型大小（参数量）：
   - 7B模型 ≈ 14GB (FP16)
   - 13B模型 ≈ 26GB (FP16)
   - 30B模型 ≈ 60GB (FP16)
   - 70B模型 ≈ 140GB (FP16)

2. 实际显存需求 = 模型大小 × 1.2-1.5（包含KV cache等）

3. 如果显存不足：
   - 使用多卡张量并行（例如：30B模型用4卡）
   - 降低 `VLLM_GPU_MEMORY_UTILIZATION`（例如从0.9降到0.8）
   - 减少 `VLLM_MAX_MODEL_LEN`（减少KV cache）

**问题：GPU被占用怎么办**

```bash
# 查看哪个进程在使用GPU
nvidia-smi

# 查看特定GPU的进程
fuser -v /dev/nvidia0  # GPU 0
fuser -v /dev/nvidia1  # GPU 1

# 如果发现冲突，停止占用GPU的模型
./manage_models.sh stop <model_name>
```

**问题：如何测试模型在单卡上是否能运行**

1. 先配置为单卡：`GPU_CONFIG["model"]="0|1"`
2. 启动模型并观察日志
3. 如果出现OOM（Out of Memory）错误，说明需要多卡或降低显存使用率

### 6. 代理相关问题

**问题：下载速度慢或失败**

- 确认 `HF_ENDPOINT` 环境变量已设置为 `https://hf-mirror.com`
- 检查网络是否能访问 hf-mirror.com
- 尝试直接访问 https://hf-mirror.com 验证镜像是否可用

**问题：如何切换回官方源**

如果需要使用官方 HuggingFace 源（不推荐，可能较慢）：
```bash
# 临时取消代理
unset HF_ENDPOINT

# 或者在脚本中修改 HF_MIRROR 为空字符串或官方地址
```

## API 使用

模型服务启动后，可以通过 OpenAI 兼容的 API 访问：

```python
from openai import OpenAI

# 连接到本地模型服务
client = OpenAI(
    api_key="local-placeholder",  # 本地服务通常不需要真实的 API key
    base_url="http://localhost:8001/v1"  # 替换为你的端口
)

# 使用模型
response = client.chat.completions.create(
    model="llava-hf/llava-1.5-7b-hf",  # 模型名称
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)
```

## 注意事项

1. **资源占用**: 运行大型模型需要大量 GPU 内存和计算资源
2. **端口管理**: 确保配置的端口不与其他服务冲突
3. **日志管理**: 定期清理日志文件，避免占用过多磁盘空间
4. **进程管理**: 使用 `status` 命令定期检查模型运行状态
5. **安全**: 如果服务暴露在公网，请配置适当的认证和防火墙规则
6. **代理稳定性**: hf-mirror.com 是社区维护的镜像，如遇问题可尝试切换其他镜像或官方源

## 示例工作流

### 8卡服务器GPU分配完整示例

假设你有一个8卡服务器（GPU 0-7），想要运行多个模型：

```bash
# 在 manage_models.sh 中配置

# 模型配置
declare -A MODEL_CONFIG
MODEL_CONFIG["llava-7b"]="llava-hf/llava-1.5-7b-hf|8001|llava-hf_llava-1.5-7b-hf"
MODEL_CONFIG["qwen-7b"]="Qwen/Qwen-7B-Chat|8002|Qwen_Qwen-7B-Chat"
MODEL_CONFIG["qwen-14b"]="Qwen/Qwen-14B-Chat|8003|Qwen_Qwen-14B-Chat"
MODEL_CONFIG["qwen-72b"]="Qwen/Qwen-72B-Chat|8004|Qwen_Qwen-72B-Chat"

# GPU分配配置
declare -A GPU_CONFIG
# 7B模型通常单卡即可（需要约14-20GB显存）
GPU_CONFIG["llava-7b"]="0|1"      # GPU 0，单卡
GPU_CONFIG["qwen-7b"]="1|1"        # GPU 1，单卡

# 14B模型可能需要单卡或双卡（需要约26-40GB显存）
GPU_CONFIG["qwen-14b"]="2|1"       # GPU 2，单卡（如果显存足够）
# 或者使用双卡：
# GPU_CONFIG["qwen-14b"]="2,3|2"   # GPU 2,3，双卡张量并行

# 72B模型需要多卡（需要约140GB显存）
GPU_CONFIG["qwen-72b"]="4,5,6,7|4"  # GPU 4,5,6,7，四卡张量并行
```

**分配策略说明：**
- GPU 0-1: 运行7B模型（单卡，每个约14-20GB）
- GPU 2: 运行14B模型（单卡，约26-40GB）或 GPU 2-3 双卡运行
- GPU 4-7: 运行72B模型（四卡张量并行，每卡约35GB）

### 完整流程示例

```bash
# 1. 下载模型
cd VCG-Bench/scripts/local_model/huggingface
python download_models.py

# 2. 配置模型服务和GPU分配（编辑 manage_models.sh）
# - 配置 MODEL_CONFIG（模型、端口、路径）
# - 配置 GPU_CONFIG（GPU分配、张量并行度）
# - 确保模型路径与下载后的目录名匹配

# 3. 查看GPU状态
nvidia-smi

# 4. 给脚本添加执行权限
chmod +x manage_models.sh

# 5. 启动模型服务
./manage_models.sh start

# 6. 查看状态（包括GPU分配信息）
./manage_models.sh status

# 7. 监控GPU使用情况
watch -n 1 nvidia-smi

# 8. 使用模型（在 Python 代码中）

# 9. 停止模型服务
./manage_models.sh stop
```

### 后台运行完整示例

```bash
# 1. 后台下载模型
cd VCG-Bench/scripts/local_model/huggingface
nohup python download_models.py > download.log 2>&1 &

# 2. 查看下载进度
tail -f download.log

# 3. 下载完成后，启动模型服务
./manage_models.sh start

# 4. 查看服务状态
./manage_models.sh status
```

## 支持

如有问题，请查看日志文件或联系维护人员。

