# SigLIP 指标配置指南

## 概述

SigLIP (Sigmoid Loss for Language Image Pre-Training) 是用于评估视觉语义相似度的指标，通过计算原始图像和渲染图像在语义特征空间中的余弦相似度来衡量生成质量。

## 实现状态

✅ **已实现**：`VCG-Bench/eval/task1/metrics.py` 中的 `SigLIPScore` 类

## 依赖安装

### 必需依赖

```bash
# 基础依赖
pip install transformers torch pillow

# 如果需要 GPU 加速（强烈推荐）
# 根据你的 CUDA 版本安装对应的 PyTorch
# CUDA 11.8
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# CPU 版本（不推荐，速度很慢）
pip install torch torchvision
```

### 验证安装

```python
# 测试 transformers 和 torch
python -c "import transformers; import torch; print(f'Transformers: {transformers.__version__}'); print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}')"
```

## 模型配置

### 当前使用的模型

代码中当前使用的模型名称：`google/siglip-so400m-patch14-384`

**注意**：文档中提到的模型名称是 `google/siglip2-so400m-patch14-384`（多了一个 "2"），但实际代码中使用的是 `google/siglip-so400m-patch14-384`。

### 模型自动下载

模型会在首次运行时自动从 HuggingFace 下载，无需手动下载。

下载位置：`~/.cache/huggingface/transformers/`

### 如果模型不存在或需要替换模型

如果 `google/siglip-so400m-patch14-384` 不存在，或者你想使用其他模型，可以按以下步骤替换：

#### 步骤 1：打开模型配置文件

```bash
# 文件位置
VCG-Bench/eval/task1/metrics.py
```

#### 步骤 2：找到模型配置行

在 `SigLIPScore` 类的 `_load_model` 方法中（约第 1140 行），找到：

```python
model_checkpoint = "google/siglip-so400m-patch14-384"
```

#### 步骤 3：替换为其他可用模型

可用的替代模型选项：

1. **google/siglip-base-patch16-224**（较小，速度快，约 86M 参数）
2. **google/siglip-base-patch16-256**（中等，约 86M 参数）
3. **google/siglip-large-patch16-256**（较大，精度高，约 307M 参数）

修改示例：

```python
# 在 metrics.py 第 1140 行，将：
model_checkpoint = "google/siglip-so400m-patch14-384"

# 改为（例如使用 base 模型）：
model_checkpoint = "google/siglip-base-patch16-256"
```

#### 步骤 4：验证修改

修改后，运行评估时会自动下载新模型。可以通过日志确认：

```bash
# 运行评估，查看日志
python eval/run_evaluation.py task1 \
    --benchmark data/task1_benchmark \
    --output eval/task1/results \
    --metrics siglip_score

# 日志中应该显示：
# SigLIP model loaded on cuda (或 cpu)
```

#### 使用本地模型路径（可选）

如果你已经手动下载了模型到本地，也可以使用本地路径：

```python
# 使用本地路径
model_checkpoint = "/path/to/local/siglip-model"
# 或
model_checkpoint = "./models/siglip-base-patch16-256"
```

## 使用方式

### 方式 1：完整评估（包含 SigLIP）

```bash
cd VCG-Bench

# 评估所有指标（包括 SigLIP）
python eval/run_evaluation.py task1 \
    --benchmark data/task1_benchmark \
    --output eval/task1/results
```

**要求**：需要 GPU 支持（推荐）或足够的 CPU 资源

### 方式 2：分阶段评估（推荐）

#### 第一步：本地运行（禁用 SigLIP）

```bash
# 在本地运行除 SigLIP 外的所有指标
python eval/run_evaluation.py task1 \
    --benchmark data/task1_benchmark \
    --output eval/task1/results \
    --disable-metrics siglip_score
```

这会生成结果文件，但 `siglip_score` 字段为 `null`。

#### 第二步：服务器运行（只运行 SigLIP）

```bash
# 在 GPU 服务器上只运行 SigLIP 指标
./run_task1_evaluation_siglip_only.sh gemini-3-pro-preview
```

评估器会自动：
1. 检查已有结果文件
2. 只评估缺失的 `siglip_score` 指标
3. 将结果补充到现有结果中

### 方式 3：使用脚本

```bash
# 完整评估（默认禁用 SigLIP）
./run_task1_evaluation.sh gemini-3-pro-preview

# 只运行 SigLIP（需要 GPU）
./run_task1_evaluation_siglip_only.sh gemini-3-pro-preview
```

## 性能优化

### GPU 加速

SigLIP 模型在 GPU 上运行速度会显著提升（10-100倍）。

检查 GPU 是否可用：
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")
```

### 批量处理

当前实现是逐张处理图像。如果需要批量处理，可以修改代码：

```python
# 在 metrics.py 中修改 evaluate 方法
# 支持批量处理多张图像
def evaluate_batch(self, image_pairs: List[Tuple[Path, Path]]) -> List[MetricResult]:
    # 批量预处理
    # 批量推理
    # 批量计算相似度
    pass
```

## 故障排除

### 问题 1：模型下载失败

**症状**：`OSError: Can't load tokenizer for 'google/siglip-so400m-patch14-384'`

**解决方案**：
1. 检查网络连接
2. 设置 HuggingFace 镜像（如果在中国）：
   ```bash
   export HF_ENDPOINT=https://hf-mirror.com
   ```
3. 手动下载模型到本地，然后修改代码使用本地路径

### 问题 2：CUDA 内存不足

**症状**：`RuntimeError: CUDA out of memory`

**解决方案**：
1. 减小 batch size（如果使用批量处理）
2. 使用 CPU 模式（速度较慢）：
   ```python
   # 在 _load_model 中强制使用 CPU
   device = "cpu"
   ```
3. 使用更小的模型（如 `siglip-base-patch16-224`）

### 问题 3：模型名称不存在

**症状**：`OSError: google/siglip-so400m-patch14-384 is not a local folder and is not a valid model identifier`

**解决方案**：
1. 检查 HuggingFace 上实际存在的模型名称
2. 修改代码中的 `model_checkpoint` 为可用模型
3. 参考本文档的"如果模型不存在"部分

### 问题 4：transformers 版本不兼容

**症状**：`AttributeError: 'SiglipModel' object has no attribute 'get_image_features'`

**解决方案**：
```bash
# 升级 transformers
pip install --upgrade transformers

# 或安装特定版本
pip install transformers>=4.30.0
```

## 验证配置

运行以下测试脚本验证 SigLIP 配置是否正确：

```python
# test_siglip.py
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.task1.metrics import SigLIPScore
from pathlib import Path

# 创建指标实例
metric = SigLIPScore()

# 检查模型是否加载成功
if metric.model is None:
    print("❌ SigLIP 模型加载失败")
    sys.exit(1)
else:
    print("✅ SigLIP 模型加载成功")
    print(f"   设备: {next(metric.model.parameters()).device}")
    print(f"   模型: google/siglip-so400m-patch14-384")

# 测试评估（需要提供测试图像路径）
# original_image = Path("path/to/original.png")
# rendered_image = Path("path/to/rendered.png")
# result = metric.evaluate(original_image, rendered_image, execution_success=True)
# print(f"相似度得分: {result.score}")
```

运行测试：
```bash
cd VCG-Bench
python test_siglip.py
```

## 总结

1. ✅ SigLIP 指标已实现
2. ⚠️ 注意模型名称：代码使用 `google/siglip-so400m-patch14-384`，文档中写的是 `google/siglip2-so400m-patch14-384`
3. 📦 需要安装：`transformers`, `torch`, `pillow`
4. 🚀 推荐使用 GPU 加速
5. 🔄 支持增量评估，可以先运行其他指标，后续单独补充 SigLIP

## 相关文件

- 实现代码：`VCG-Bench/eval/task1/metrics.py` (第 1125-1247 行)
- 评估脚本：`VCG-Bench/run_task1_evaluation_siglip_only.sh`
- 文档说明：`docs/evaluation_metrics_design_csbench.md` (第 947-1061 行)

