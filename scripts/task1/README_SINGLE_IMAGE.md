# 单独处理单张图片 - Task 1

这个脚本可以单独处理一张图片，生成 Task 1 所需的 LLM 描述和 XML 代码。

## 使用方法

### 基本用法

```bash
# 从项目根目录运行
cd VCG-Bench

# 处理一张图片（默认使用 gemini-3-pro-preview 模型，输出到 /tmp/task1_single_image_<timestamp>）
python scripts/task1/process_single_image.py /path/to/your/image.png

# 指定输出目录（会保存到 /tmp）
python scripts/task1/process_single_image.py /path/to/your/image.png --output /tmp/my_result

# 指定模型
python scripts/task1/process_single_image.py /path/to/your/image.png --model gpt-4o

# 指定 provider
python scripts/task1/process_single_image.py /path/to/your/image.png --provider siliconflow --model Qwen/Qwen3-VL-30B-A3B-Instruct
```

### 参数说明

- `image_path`: 图片路径（必需）
- `--model`: 模型名称（默认: gemini-3-pro-preview）
- `--output`: 输出目录（默认: /tmp/task1_single_image_<timestamp>）
- `--provider`: LLM provider（可选: siliconflow, zhipu, custom, local，默认: custom）
- `--temperature`: LLM 温度参数（默认: 0.0）
- `--skip-render`: 跳过 Draw.io 渲染，只生成描述和 XML

## 输出结构

处理完成后，输出目录结构如下：

```
output_dir/
├── original.png              # 原始图片的副本
├── model_<model_name>/
│   ├── llm_description.txt   # LLM 生成的描述（JSON 格式）
│   ├── diagram.xml           # 生成的 Draw.io XML 代码
│   └── rendered.png          # 渲染结果；使用 --skip-render 时不会生成
└── stats.json                 # 处理统计信息（token 使用量、时间等）
```

## 示例

```bash
# 处理图片并保存到指定目录
python scripts/task1/process_single_image.py \
    /path/to/diagram.png \
    --model gemini-3-pro-preview \
    --output /tmp/my_diagram_result
```

## 注意事项

1. 确保已配置好 LLM API 密钥（通过环境变量或 .env 文件）
2. 默认会尝试调用 Draw.io 渲染；未安装 Draw.io 时可以加 `--skip-render`
3. 如果处理失败，会在输出目录生成 `error.json` 文件记录错误信息
