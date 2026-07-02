# ModelScope 模型管理脚本使用指南

本目录包含用于管理 ModelScope 模型的脚本工具，包括模型下载和模型服务管理功能。

## 文件说明

- `download_models.py` - 从 ModelScope 批量下载模型的 Python 脚本
- `manage_models.sh` - 管理模型服务的 Bash 脚本（启动、停止、查看状态等）
- `README.md` - 本使用说明文档

## 前置要求

### 1. 安装依赖

```bash
# 安装 ModelScope SDK
pip install modelscope

# 安装 vLLM（用于运行模型服务）
pip install vllm

# 如果使用 GPU，确保已安装 CUDA 和相应的 PyTorch 版本
```

### 2. 配置环境

确保你的系统已配置好：
- Python 3.8+
- CUDA（如果使用 GPU）
- 足够的磁盘空间（模型文件通常很大，每个模型可能需要几十GB）

## 使用指南

### 一、下载模型

#### 1. 配置要下载的模型

编辑 `download_models.py` 文件，在脚本开头的配置区域修改 `MODEL_LIST`：

```python
MODEL_LIST = [
    "OpenBMB/MiniCPM-V-4_5",
    "OpenGVLab/InternVL3_5-8B",
    "OpenGVLab/InternVL3_5-14B",
    # 添加更多模型...
]
```

#### 2. 配置保存目录（可选）

默认保存到 `VCG-Bench/models/modelscope/`，如需修改，编辑脚本中的 `SAVE_DIR` 变量。

#### 3. 执行下载

```bash
cd VCG-Bench/scripts/local_model/modelscope

# 直接运行
python download_models.py

# 或者使用 nohup 后台运行
nohup python download_models.py > download.log 2>&1 &
```

#### 4. 查看下载进度

脚本会自动显示下载进度，包括：
- 已下载文件大小
- 实时下载速度
- 每10秒更新一次状态

**实时查看进度**：

```bash
# 如果直接运行，进度会直接显示在终端
python download_models.py

# 如果使用 nohup 后台运行，可以实时查看日志
tail -f ../../logs/modelscope_download.log

# 或者查看 nohup 输出
tail -f download.log
```

**进度输出示例**：
```
2026-01-05 15:39:12,097 - INFO - 开始下载模型: OpenBMB/MiniCPM-V-4_5
2026-01-05 15:39:12,098 - INFO -   正在连接ModelScope并开始下载...
2026-01-05 15:39:22,123 - INFO -   📥 下载中... 已下载: 125.34 MB | 速度: 12.53 MB/s
2026-01-05 15:39:32,145 - INFO -   📥 下载中... 已下载: 256.78 MB | 速度: 13.15 MB/s
...
2026-01-05 15:45:30,567 - INFO - ✓ 模型下载完成: OpenBMB/MiniCPM-V-4_5
2026-01-05 15:45:30,568 - INFO -   总大小: 8.45 GB
2026-01-05 15:45:30,569 - INFO -   本次下载: 8.45 GB
2026-01-05 15:45:30,570 - INFO -   耗时: 378.5 秒
2026-01-05 15:45:30,571 - INFO -   平均速度: 22.85 MB/s
```

**注意事项**：
- 如果检测到已存在的文件，脚本会自动续传
- 进度每10秒更新一次，如果长时间没有更新，可能是网络问题或下载完成
- 可以通过查看日志文件确认下载是否正常进行

### 二、管理模型服务

#### 1. 配置模型服务

编辑 `manage_models.sh` 文件，在脚本开头的配置区域修改 `MODEL_CONFIG`：

```bash
declare -A MODEL_CONFIG
MODEL_CONFIG["MiniCPM-V-4_5"]="OpenBMB/MiniCPM-V-4_5|8001|OpenBMB/MiniCPM-V-4_5"
MODEL_CONFIG["InternVL3_5-8B"]="OpenGVLab/InternVL3_5-8B|8002|OpenGVLab/InternVL3_5-8B"
MODEL_CONFIG["InternVL3_5-14B"]="OpenGVLab/InternVL3_5-14B|8003|OpenGVLab/InternVL3_5-14B"
```

配置格式：`"模型名称|端口|模型路径"`
- **模型名称**: 用于标识的简短名称
- **端口**: 服务监听的端口号
- **模型路径**: ModelScope 模型ID 或本地路径（如果已下载）

#### 1.1. 配置GPU分配（重要）

编辑 `manage_models.sh` 文件，在 `GPU_CONFIG` 中配置每个模型使用的GPU：

```bash
# GPU分配配置（格式: "GPU设备ID|张量并行度"）
declare -A GPU_CONFIG
GPU_CONFIG["MiniCPM-V-4_5"]="0|1"          # 使用GPU 0，单卡运行
GPU_CONFIG["InternVL3_5-8B"]="1|1"          # 使用GPU 1，单卡运行
GPU_CONFIG["InternVL3_5-14B"]="2,3|2"        # 使用GPU 2和3，双卡张量并行
```

配置说明：
- **GPU设备ID**: 
  - 单个GPU: 使用数字，如 `"0"` 表示使用GPU 0
  - 多个GPU: 使用逗号分隔，如 `"2,3"` 表示使用GPU 2和3
- **张量并行度**: 
  - 单卡运行: 设置为 `1`
  - 多卡张量并行: 设置为GPU数量，如 `2` 表示使用2张GPU进行张量并行

**8卡服务器推荐配置示例**：

```bash
# 方案1: 每个模型使用单卡（适合显存充足的模型）
GPU_CONFIG["MiniCPM-V-4_5"]="0|1"          # GPU 0
GPU_CONFIG["InternVL3_5-8B"]="1|1"          # GPU 1
GPU_CONFIG["InternVL3_5-14B"]="2|1"        # GPU 2

# 方案2: 大模型使用多卡，小模型使用单卡
GPU_CONFIG["MiniCPM-V-4_5"]="0|1"          # GPU 0 (单卡)
GPU_CONFIG["InternVL3_5-8B"]="1|1"          # GPU 1 (单卡)
GPU_CONFIG["InternVL3_5-14B"]="2,3|2"      # GPU 2,3 (双卡并行)

# 方案3: 所有模型使用多卡并行（最大化性能）
GPU_CONFIG["MiniCPM-V-4_5"]="0,1|2"        # GPU 0,1 (双卡并行)
GPU_CONFIG["InternVL3_5-8B"]="2,3|2"        # GPU 2,3 (双卡并行)
GPU_CONFIG["InternVL3_5-14B"]="4,5,6,7|4"   # GPU 4,5,6,7 (四卡并行)
```

**显存需求估算**（仅供参考，实际需求取决于模型精度、KV cache大小等）：

| 模型 | 参数量 | 单卡显存需求（FP16） | 单卡显存需求（INT8） | 推荐配置 |
|------|--------|---------------------|---------------------|----------|
| MiniCPM-V-4_5 | ~4.5B | ~10-12GB | ~6-8GB | 单卡（24GB+） |
| InternVL3_5-8B | ~8B | ~18-20GB | ~10-12GB | 单卡（24GB+）或双卡（16GB×2） |
| InternVL3_5-14B | ~14B | ~30-35GB | ~18-20GB | 双卡（24GB×2）或四卡（16GB×4） |

**注意事项**：
- 显存需求会因 `gpu-memory-utilization` 和 `max-model-len` 设置而变化
- 如果显存不足，可以：
  1. 降低 `VLLM_GPU_MEMORY_UTILIZATION`（如从 0.9 降到 0.7）
  2. 减少 `VLLM_MAX_MODEL_LEN`（如从 8192 降到 4096）
  3. 使用多卡张量并行
  4. 使用量化模型（INT8/INT4）

**查看GPU使用情况**：

```bash
# 查看所有GPU状态
nvidia-smi

# 实时监控GPU使用
watch -n 1 nvidia-smi

# 查看特定GPU的详细信息
nvidia-smi -i 0  # 查看GPU 0
```

#### 2. 启动模型服务

```bash
cd VCG-Bench/scripts/local_model/modelscope

# 启动所有配置的模型
./manage_models.sh start

# 查看帮助
./manage_models.sh
```

#### 3. 查看运行状态

```bash
./manage_models.sh status
```

输出示例：
```
========================================
模型运行状态
========================================

模型: MiniCPM-V-4_5
  状态: 运行中
  PID: 12345
  端口: 8001 (监听中)
  模型ID: OpenBMB/MiniCPM-V-4_5
  API地址: http://0.0.0.0:8001/v1

...
```

#### 4. 停止模型服务

```bash
# 停止所有模型
./manage_models.sh stop

# 停止指定模型
./manage_models.sh stop MiniCPM-V-4_5
```

#### 5. 强制终止模型进程

如果正常停止失败，可以使用 kill 命令：

```bash
# 强制终止所有模型
./manage_models.sh kill

# 强制终止指定模型
./manage_models.sh kill MiniCPM-V-4_5
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

## GPU 配置快速指南

### 查看GPU信息

```bash
# 查看所有GPU信息
nvidia-smi

# 查看GPU数量和显存大小
nvidia-smi --query-gpu=index,name,memory.total --format=csv

# 实时监控GPU使用情况
watch -n 1 nvidia-smi
```

### 8卡服务器配置示例

假设你有8张GPU（每张24GB显存），推荐配置：

```bash
# 方案1: 保守配置（每个模型单卡，留出余量）
GPU_CONFIG["MiniCPM-V-4_5"]="0|1"          # GPU 0 (约需10-12GB)
GPU_CONFIG["InternVL3_5-8B"]="1|1"          # GPU 1 (约需18-20GB)
GPU_CONFIG["InternVL3_5-14B"]="2,3|2"      # GPU 2,3 (约需30-35GB，双卡并行)
# 剩余 GPU 4,5,6,7 可用于其他任务

# 方案2: 平衡配置（充分利用GPU）
GPU_CONFIG["MiniCPM-V-4_5"]="0|1"          # GPU 0
GPU_CONFIG["InternVL3_5-8B"]="1,2|2"        # GPU 1,2 (双卡并行，提升性能)
GPU_CONFIG["InternVL3_5-14B"]="3,4,5,6|4"   # GPU 3,4,5,6 (四卡并行，最大化性能)
# GPU 7 保留用于其他任务

# 方案3: 最大化性能（所有GPU都用上）
GPU_CONFIG["MiniCPM-V-4_5"]="0,1|2"         # GPU 0,1 (双卡并行)
GPU_CONFIG["InternVL3_5-8B"]="2,3|2"         # GPU 2,3 (双卡并行)
GPU_CONFIG["InternVL3_5-14B"]="4,5,6,7|4"   # GPU 4,5,6,7 (四卡并行)
```

### 显存不足时的解决方案

如果遇到显存不足（OOM）错误：

1. **降低内存使用率**（在 `manage_models.sh` 中修改）：
   ```bash
   VLLM_GPU_MEMORY_UTILIZATION="0.7"  # 从0.9降到0.7
   ```

2. **减少最大序列长度**：
   ```bash
   VLLM_MAX_MODEL_LEN="4096"  # 从8192降到4096
   ```

3. **使用多卡张量并行**（在 `GPU_CONFIG` 中配置）：
   ```bash
   # 单卡不够，改为双卡
   GPU_CONFIG["InternVL3_5-14B"]="2,3|2"  # 使用GPU 2和3
   ```

4. **检查GPU占用**：
   ```bash
   # 查看哪些GPU被占用
   nvidia-smi
   
   # 查看特定进程的GPU使用
   fuser -v /dev/nvidia*
   ```

## 配置说明

### download_models.py 配置项

- `MODEL_LIST`: 要下载的模型列表（ModelScope 模型ID）
- `SAVE_DIR`: 模型保存目录（默认: `VCG-Bench/models/modelscope/`）
- `LOG_DIR`: 日志目录（默认: `VCG-Bench/logs/`）

### manage_models.sh 配置项

- `MODEL_CONFIG`: 模型服务配置（格式: `"名称|端口|模型路径"`）
- `GPU_CONFIG`: GPU分配配置（格式: `"GPU设备ID|张量并行度"`）
  - GPU设备ID: 单个用数字（如 `"0"`），多个用逗号分隔（如 `"0,1"`）
  - 张量并行度: 单卡用 `1`，多卡用GPU数量（如 `2` 表示2卡并行）
- `MODELS_DIR`: 模型保存目录
- `LOG_DIR`: 日志目录
- `PID_DIR`: PID 文件目录（用于跟踪运行中的进程）
- `VLLM_HOST`: vLLM 服务监听地址（默认: `0.0.0.0`）
- `VLLM_GPU_MEMORY_UTILIZATION`: GPU 内存使用率（默认: `0.9`）
  - 如果显存不足，可以降低到 `0.7` 或 `0.5`
- `VLLM_MAX_MODEL_LEN`: 最大模型长度（默认: `8192`）
  - 如果显存不足，可以降低到 `4096` 或 `2048`

## 日志文件

- 下载日志: `VCG-Bench/logs/modelscope_download.log`
- 模型服务日志: `VCG-Bench/logs/vllm_<模型名>_<端口>.log`
- PID 文件: `VCG-Bench/models/modelscope/pids/<模型名>.pid`

## 常见问题

### 1. 下载失败

- **检查网络连接**: 确保可以访问 ModelScope
- **检查磁盘空间**: 确保有足够的磁盘空间
- **检查 ModelScope 模型ID**: 确保模型ID正确
- **查看日志**: 检查 `logs/modelscope_download.log` 获取详细错误信息

### 2. 模型服务启动失败

- **检查端口占用**: 使用 `lsof -i :端口号` 检查端口是否被占用
- **检查 GPU 内存**: 
  - 如果 GPU 内存不足（OOM错误），可以：
    1. 降低 `VLLM_GPU_MEMORY_UTILIZATION`（如从 0.9 降到 0.7）
    2. 减少 `VLLM_MAX_MODEL_LEN`（如从 8192 降到 4096）
    3. 使用多卡张量并行（在 `GPU_CONFIG` 中配置）
    4. 使用量化模型
- **检查 GPU 配置**: 
  - 确保 `GPU_CONFIG` 中的GPU设备ID正确
  - 使用 `nvidia-smi` 查看GPU是否可用
  - 确保GPU没有被其他进程占用
- **检查模型路径**: 确保模型已下载或 ModelScope ID 正确
- **查看日志**: 检查 `logs/vllm_<模型名>_<端口>.log` 获取详细错误信息

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

## API 使用

模型服务启动后，可以通过 OpenAI 兼容的 API 访问。以下是详细的配置和使用示例。

### 一、本地模型服务 URL 配置

根据 `manage_models.sh` 中的配置，各模型的 API 地址如下：

| 模型名称 | 端口 | API URL |
|---------|------|---------|
| MiniCPM-V-4_5 | 8001 | `http://localhost:8001/v1` |
| InternVL3_5-8B | 8002 | `http://localhost:8002/v1` |
| InternVL3_5-14B | 8003 | `http://localhost:8003/v1` |

如果服务运行在其他机器上，将 `localhost` 替换为对应的 IP 地址，例如：
- `http://192.168.1.100:8001/v1`
- `http://10.0.0.5:8002/v1`

### 二、Python API 使用示例

#### 1. 基础文本对话示例

```python
from openai import OpenAI

# 连接到本地模型服务（MiniCPM-V-4_5，端口8001）
client = OpenAI(
    api_key="local-placeholder",  # 本地服务通常不需要真实的 API key，任意值即可
    base_url="http://localhost:8001/v1"
)

# 文本对话
response = client.chat.completions.create(
    model="OpenBMB/MiniCPM-V-4_5",  # 模型名称（vLLM会自动处理）
    messages=[
        {"role": "user", "content": "你好，请介绍一下你自己"}
    ],
    temperature=0.7,
    max_tokens=1024
)

print(response.choices[0].message.content)
```

#### 2. 视觉模型（多模态）使用示例

```python
from openai import OpenAI
import base64
from pathlib import Path

# 连接到本地视觉模型服务
client = OpenAI(
    api_key="local-placeholder",
    base_url="http://localhost:8001/v1"  # MiniCPM-V-4_5 支持视觉
)

# 读取图片并转换为base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# 使用视觉模型分析图片
image_path = "path/to/your/image.jpg"
base64_image = encode_image(image_path)

response = client.chat.completions.create(
    model="OpenBMB/MiniCPM-V-4_5",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请描述这张图片的内容"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }
    ],
    max_tokens=1024
)

print(response.choices[0].message.content)
```

#### 3. 切换不同模型示例

```python
from openai import OpenAI

# 模型配置字典
MODELS = {
    "MiniCPM-V-4_5": {
        "base_url": "http://localhost:8001/v1",
        "model_name": "OpenBMB/MiniCPM-V-4_5"
    },
    "InternVL3_5-8B": {
        "base_url": "http://localhost:8002/v1",
        "model_name": "OpenGVLab/InternVL3_5-8B"
    },
    "InternVL3_5-14B": {
        "base_url": "http://localhost:8003/v1",
        "model_name": "OpenGVLab/InternVL3_5-14B"
    }
}

def get_client(model_key):
    """获取指定模型的客户端"""
    config = MODELS[model_key]
    return OpenAI(
        api_key="local-placeholder",
        base_url=config["base_url"]
    ), config["model_name"]

# 使用不同的模型
for model_key in MODELS.keys():
    client, model_name = get_client(model_key)
    print(f"\n使用模型: {model_key}")
    
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "user", "content": "Hello!"}
        ]
    )
    print(f"响应: {response.choices[0].message.content[:50]}...")
```

### 三、在 VCG-Bench 项目中使用本地模型

#### 1. 通过环境变量配置

在 VCG-Bench 项目中，可以通过环境变量配置本地模型：

```bash
# 设置本地模型服务地址
export LOCAL_BASE_URL="http://localhost:8001/v1"  # 使用 MiniCPM-V-4_5
export LOCAL_VISION_MODEL="OpenBMB/MiniCPM-V-4_5"
export LOCAL_API_KEY="ollama"

# 或者使用其他模型
export LOCAL_BASE_URL="http://localhost:8002/v1"  # 使用 InternVL3_5-8B
export LOCAL_VISION_MODEL="OpenGVLab/InternVL3_5-8B"
```

#### 2. 在 .env 文件中配置

在 VCG-Bench 根目录创建或编辑 `.env` 文件：

```bash
# .env 文件
LOCAL_BASE_URL=http://localhost:8001/v1
LOCAL_VISION_MODEL=OpenBMB/MiniCPM-V-4_5
LOCAL_API_KEY=ollama
```

#### 3. 在 Python 代码中使用

```python
from VCG-Bench.src.llm.providers import get_provider

# 获取本地模型提供者
provider = get_provider('local')
client = provider.get_client()

# 使用模型
response = client.chat.completions.create(
    model=provider.get_default_model(),
    messages=[
        {"role": "user", "content": "你的问题"}
    ]
)
```

#### 4. 使用 CustomProvider 配置多个本地模型

如果需要同时使用多个本地模型，可以使用 `CustomProvider`：

```bash
# 在 .env 或环境变量中配置
export CUSTOM_BASE_URL="http://localhost:8001/v1"  # MiniCPM-V-4_5
export CUSTOM_VISION_MODEL="OpenBMB/MiniCPM-V-4_5"
export CUSTOM_API_KEY="ollama"
```

然后在代码中：

```python
from VCG-Bench.src.llm.providers import get_provider

provider = get_provider('custom')
client = provider.get_client()
# ... 使用模型
```

### 四、使用 curl 测试 API

#### 1. 测试文本对话

```bash
# 测试 MiniCPM-V-4_5 (端口 8001)
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-placeholder" \
  -d '{
    "model": "OpenBMB/MiniCPM-V-4_5",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ],
    "max_tokens": 100
  }'
```

#### 2. 测试健康检查

```bash
# 检查服务是否运行
curl http://localhost:8001/health

# 或者查看模型列表
curl http://localhost:8001/v1/models
```

#### 3. 测试视觉模型（需要先编码图片）

```bash
# 注意：视觉模型需要 base64 编码的图片
# 这里只是示例，实际使用时需要先编码图片
curl http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-placeholder" \
  -d '{
    "model": "OpenBMB/MiniCPM-V-4_5",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "描述这张图片"},
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
            }
          }
        ]
      }
    ],
    "max_tokens": 500
  }'
```

### 五、完整使用示例

```python
#!/usr/bin/env python3
"""
本地模型服务完整使用示例
"""

from openai import OpenAI
import os

# 配置模型服务地址
MODEL_CONFIGS = {
    "minicpm": {
        "url": "http://localhost:8001/v1",
        "model": "OpenBMB/MiniCPM-V-4_5"
    },
    "internvl_8b": {
        "url": "http://localhost:8002/v1",
        "model": "OpenGVLab/InternVL3_5-8B"
    },
    "internvl_14b": {
        "url": "http://localhost:8003/v1",
        "model": "OpenGVLab/InternVL3_5-14B"
    }
}

def test_model(model_key: str, prompt: str):
    """测试指定模型"""
    config = MODEL_CONFIGS[model_key]
    
    print(f"\n{'='*60}")
    print(f"测试模型: {model_key}")
    print(f"URL: {config['url']}")
    print(f"模型: {config['model']}")
    print(f"{'='*60}")
    
    try:
        client = OpenAI(
            api_key="local-placeholder",
            base_url=config["url"]
        )
        
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        print(f"\n响应:\n{response.choices[0].message.content}")
        print(f"\n使用token: {response.usage.total_tokens}")
        
    except Exception as e:
        print(f"错误: {str(e)}")

if __name__ == "__main__":
    # 测试所有模型
    test_prompt = "请用一句话介绍人工智能"
    
    for model_key in MODEL_CONFIGS.keys():
        test_model(model_key, test_prompt)
```

### 六、故障排查

#### 1. 检查服务是否运行

```bash
# 查看服务状态
./manage_models.sh status

# 或者直接测试端口
curl http://localhost:8001/health
```

#### 2. 检查端口是否被占用

```bash
# 检查端口占用情况
lsof -i :8001
lsof -i :8002
lsof -i :8003
```

#### 3. 查看服务日志

```bash
# 查看模型服务日志
tail -f ../../logs/vllm_MiniCPM-V-4_5_8001.log
tail -f ../../logs/vllm_InternVL3_5-8B_8002.log
```

#### 4. 常见错误处理

- **Connection refused**: 检查服务是否启动，端口是否正确
- **Model not found**: 检查模型名称是否正确，或模型是否已加载
- **Timeout**: 检查 GPU 资源是否充足，或增加超时时间
- **Out of memory**: 降低 `VLLM_GPU_MEMORY_UTILIZATION` 或使用更小的模型

## 注意事项

1. **资源占用**: 运行大型模型需要大量 GPU 内存和计算资源
2. **端口管理**: 确保配置的端口不与其他服务冲突
3. **日志管理**: 定期清理日志文件，避免占用过多磁盘空间
4. **进程管理**: 使用 `status` 命令定期检查模型运行状态
5. **安全**: 如果服务暴露在公网，请配置适当的认证和防火墙规则

## 示例工作流

### 完整流程示例

```bash
# 1. 下载模型
cd VCG-Bench/scripts/local_model/modelscope
python download_models.py

# 2. 配置模型服务（编辑 manage_models.sh）

# 3. 启动模型服务
./manage_models.sh start

# 4. 查看状态
./manage_models.sh status

# 5. 使用模型（在 Python 代码中）

# 6. 停止模型服务
./manage_models.sh stop
```

## 支持

如有问题，请查看日志文件或联系维护人员。

