# CodeVQA 和 XDRFR 指标的输入输出说明

## CodeVQA 指标

### 指标说明
**CodeVQA (Code Visual Question Answering)** 是一个符号保真度评估指标，用于评估模型生成的图表渲染图是否能正确回答基于图表内容的视觉问题。

### 输入参数

#### 1. `rendered_image_path: Path`
- **类型**：`Path`（文件路径对象）
- **说明**：模型生成的图表渲染图路径
- **示例**：`data/task1_benchmark/domain_academic_domain_architecture/sample_0001/model_gemini-3-pro-preview/rendered.png`
- **要求**：文件必须存在，否则返回 0 分

#### 2. `qa_pairs: List[Dict[str, str]]`
- **类型**：`List[Dict[str, str]]`（字典列表）
- **说明**：QA 对列表，包含针对该样本的问题和答案对
- **来源**：从 `{sample_dir}/qa_pairs.json` 文件加载
- **格式**：
  ```json
  {
    "sample_id": "sample_0001",
    "domain": "domain_academic_domain_architecture",
    "num_questions": 3,
    "qa_pairs": [
      {
        "question": "How many horizontal bars representing task duration are colored blue in the Gantt chart?",
        "answer": "3",
        "question_type": "counting",
        "visual_anchor": "blue task bars"
      },
      {
        "question": "What is the English text displayed in the top right corner of the header area?",
        "answer": "Work Arrangement",
        "question_type": "identification",
        "visual_anchor": "top right text"
      },
      {
        "question": "In the department list at the bottom right, which department is located immediately to the right of the '策划部' (Planning Department)?",
        "answer": "设计部",
        "question_type": "relationship",
        "visual_anchor": "bottom right icons"
      }
    ],
    "generated_at": "2026-01-02T04:22:30.788546",
    "generation_model": "gemini-3-pro-preview"
  }
  ```

**每个 QA 对包含的字段**：
- `question: str` - 问题文本（必需）
- `answer: str` - 标准答案/ground truth（必需）
- `question_type: str` - 问题类型（可选，默认为 "open"）
  - `"counting"` - 计数类问题（如 "How many nodes..."）
  - `"identification"` - 识别类问题（如 "What is the text..."）
  - `"relationship"` - 关系类问题（如 "Which node is connected to..."）
  - `"open"` - 开放类问题（其他类型）
- `visual_anchor: str` - 视觉锚点（可选，用于问题生成时的参考）

#### 3. `execution_success: bool`
- **类型**：`bool`
- **说明**：XML 代码是否执行成功
- **默认值**：`True`
- **行为**：如果为 `False`，直接返回 0 分，不进行 API 调用

### API 调用方式

#### 评估模型
- **模型**：`gemini-3-pro-preview`（硬编码）
- **调用方式**：**批量处理** - 一次 API 调用回答所有问题（优化设计，减少 API 调用次数）
- **输入**：
  - **图像输入**：`rendered_image_path`（视觉输入）
  - **文本 prompt**：包含所有问题的批量 prompt
- **输出格式**：JSON 格式，包含所有问题的答案
  ```json
  {
    "Q1": "3",
    "Q2": "Work Arrangement",
    "Q3": "设计部"
  }
  ```

#### 答案正确性评估
- **计数类问题**（`question_type == "counting"`）：提取数字进行精确比较
- **识别类和关系类问题**（`question_type in ["identification", "relationship"]`）：
  1. 精确匹配（标准化后）
  2. 包含匹配（仅当标准答案是单个实体时）
  3. 实体集合匹配（提取实体，忽略连接词和顺序）
  4. 关键词匹配（单词级别，忽略连接词）
- **其他类型**：精确匹配（标准化后）

### 输出结果

#### MetricResult 对象结构
```python
MetricResult(
    metric_name="codevqa",
    score=0.6667,  # float: 准确率 = correct_answers / total_questions
    success=True,  # bool: 评估是否成功
    details={
        "total_questions": 3,  # int: 总问题数
        "correct_answers": 2,  # int: 正确答案数
        "per_question_results": [  # List[Dict]: 每个问题的详细结果
            {
                "question": "How many horizontal bars...",
                "question_type": "counting",
                "ground_truth": "3",
                "generated_answer": "3",
                "is_correct": True
            },
            {
                "question": "What is the English text...",
                "question_type": "identification",
                "ground_truth": "Work Arrangement",
                "generated_answer": "Work Arrangement",
                "is_correct": True
            },
            {
                "question": "In the department list...",
                "question_type": "relationship",
                "ground_truth": "设计部",
                "generated_answer": "Marketing Department",
                "is_correct": False
            }
        ]
    }
)
```

#### 保存到评估结果文件
评估结果会保存在分片文件中（`data/task1_evaluation/fragments/{model}_{domain}_results.json`），格式如下：
```json
{
  "samples": [
    {
      "sample_id": "sample_0001",
      "domain": "domain_academic_domain_architecture",
      "model": "gemini-3-pro-preview",
      "metrics": {
        "codevqa": {
          "score": 0.6667,
          "success": true,
          "details": {
            "total_questions": 3,
            "correct_answers": 2,
            "per_question_results": [...]
          }
        }
      }
    }
  ]
}
```

#### 生成的 CSV 统计文件
1. **all_models_comparison.csv**：样本级别的对比结果
   - 列：`sample_id`, `domain`, `model`, `codevqa`（score 值）

2. **all_models_codevqa_by_question_type.csv**：按问题类型分层的统计
   - 列：`model`, `question_type`, `total_questions`, `correct_answers`, `accuracy`, `accuracy_percentage`

---

## XDRFR 指标

### 指标说明
**XDRFR (XML-based DRFR)** 是一个基于 XML 代码的指令遵循评估指标，用于评估模型根据自然语言指令修改 XML 代码的能力。该指标完全基于 XML 代码进行评估，不依赖于渲染图像。

### 输入参数

#### 1. `original_xml: str`
- **类型**：`str`（字符串）
- **说明**：Gemini 生成的原始 XML 代码
- **来源**：从 `{sample_dir}/diagram.xml` 文件读取
- **示例**：
  ```xml
  <mxfile host="app.diagrams.net">
    <diagram id="diagram1">
      <mxGraphModel>
        ...
      </mxGraphModel>
    </diagram>
  </mxfile>
  ```

#### 2. `modified_xml: str`
- **类型**：`str`（字符串）
- **说明**：模型根据指令修改后的 XML 代码
- **来源**：从 `{instruction_dir}/model_{model_name}/modified.xml` 文件读取
- **格式**：与 `original_xml` 相同的 XML 格式

#### 3. `instruction: str`
- **类型**：`str`（字符串）
- **说明**：修改指令（自然语言）
- **来源**：从 `{instruction_dir}/instruction.txt` 文件读取
- **示例**：
  ```
  Change the color of all nodes in the central cluster to blue and increase their size by 20%.
  ```

#### 4. `decomposed_questions: List[str]`
- **类型**：`List[str]`（字符串列表）
- **说明**：将指令分解后的问题列表（Yes/No 问题）
- **来源**：从 `{instruction_dir}/question_set.json` 文件加载
- **格式**：
  ```json
  {
    "instruction_id": "instruction_0001",
    "common_questions": [
      "Is the modified diagram visually similar to the original?",
      "Does the modified diagram maintain the overall structure?"
    ],
    "decomposed_questions": [
      "Are all nodes in the central cluster colored blue?",
      "Has the size of nodes in the central cluster increased by 20%?",
      "Are there any new nodes added to the central cluster?",
      "Have any nodes been removed from the central cluster?"
    ],
    "generated_at": "2026-01-02T04:22:30.788546",
    "generation_model": "gemini-3-pro-preview"
  }
  ```
- **注意**：XDRFR **只使用 `decomposed_questions`**，不使用 `common_questions`

#### 5. `execution_success: bool`
- **类型**：`bool`
- **说明**：修改后的 XML 是否执行成功（通过检查 `modified.png` 文件是否存在判断）
- **默认值**：`True`
- **行为**：如果为 `False`，直接返回 0 分，不进行 API 调用

### API 调用方式

#### 评估模型
- **模型**：`gemini-3-pro-preview`（硬编码）
- **调用方式**：**批量处理** - 一次 API 调用评估所有问题（优化设计，减少 API 调用次数）
- **输入**：
  - **仅文本输入**：只传递 XML 代码文本，不传递图像（注意：虽然使用 gemini-3-pro-preview 支持图像输入，但 XDRFR 只使用文本）
  - **Prompt 内容**：
    - 原始 XML 代码
    - 修改后的 XML 代码
    - 修改指令（自然语言）
    - 所有分解后的问题（Yes/No 问题）
- **输出格式**：JSON 格式，包含所有问题的答案
  ```json
  {
    "answers": [
      {"question": "Are all nodes in the central cluster colored blue?", "answer": "Yes"},
      {"question": "Has the size of nodes in the central cluster increased by 20%?", "answer": "Yes"},
      {"question": "Are there any new nodes added to the central cluster?", "answer": "No"},
      {"question": "Have any nodes been removed from the central cluster?", "answer": "No"}
    ]
  }
  ```

#### XML 代码长度限制
- **最大长度**：50,000 字符
- **行为**：如果 XML 代码超过限制，会截断并添加提示信息
- **提示**：`"... (XML code truncated, please refer to file for complete code)"`

#### 答案解析
- **支持格式**：
  - `"Yes"` / `"yes"` / `"true"` / `"1"` / `"是"` → `is_satisfied = True`
  - `"No"` / `"no"` / `"false"` / `"0"` / `"否"` → `is_satisfied = False`
- **默认行为**：如果无法解析，默认为 `"No"`（保守策略）

### 输出结果

#### MetricResult 对象结构
```python
MetricResult(
    metric_name="xdrfr",
    score=0.75,  # float: XDRFR分数 = satisfied_count / total_questions
    success=True,  # bool: 评估是否成功
    details={
        "xdrfr_score": 0.75,  # float: XDRFR分数（与score相同）
        "total_questions": 4,  # int: 总问题数
        "satisfied_count": 3,  # int: 满足条件的问题数
        "per_question_results": [  # List[Dict]: 每个问题的详细结果
            {
                "question": "Are all nodes in the central cluster colored blue?",
                "answer": "Yes",
                "is_satisfied": True
            },
            {
                "question": "Has the size of nodes in the central cluster increased by 20%?",
                "answer": "Yes",
                "is_satisfied": True
            },
            {
                "question": "Are there any new nodes added to the central cluster?",
                "answer": "No",
                "is_satisfied": True  # "No" 也视为满足（问题本身就是问是否有新增）
            },
            {
                "question": "Have any nodes been removed from the central cluster?",
                "answer": "Yes",  # 实际上应该没有移除
                "is_satisfied": False  # 这是错误的，所以 is_satisfied = False
            }
        ]
    }
)
```

#### 保存到评估结果文件
评估结果会保存在分片文件中（`data/task2_evaluation/fragments/{model}_{domain}_results.json`），格式如下：
```json
{
  "instructions": [
    {
      "sample_id": "sample_0001",
      "domain": "domain_academic_domain_architecture",
      "instruction_id": "instruction_0001",
      "model": "gemini-3-pro-preview",
      "instruction_level": "Medium",
      "metrics": {
        "xdrfr": {
          "score": 0.75,
          "success": true,
          "details": {
            "xdrfr_score": 0.75,
            "total_questions": 4,
            "satisfied_count": 3,
            "per_question_results": [...]
          }
        }
      }
    }
  ]
}
```

#### 生成的 CSV 统计文件
1. **all_models_comparison.csv**：样本-指令级别的对比结果
   - 列：`sample_id`, `domain`, `instruction_id`, `model`, `instruction_level`, `xdrfr`（score 值）

2. **all_models_by_instruction_difficulty.csv**：按指令难度分层的统计
   - 列：`model`, `instruction_level`, `xdrfr_mean`, `xdrfr_count`

---

## 共同特点

### 1. API 调用优化
- **批量处理**：两个指标都采用批量处理方式，一次 API 调用处理所有问题，减少 API 调用次数
- **成本优化**：相比逐个问题调用 API，批量处理可以显著降低 API 调用成本

### 2. 重试机制
- **底层 API 重试**：LLMClient 内置重试机制，最多尝试 3 次（初始尝试 + 2 次重试）
- **评估层面重试**：如果 API 调用失败（`success=False`），重新运行评估时会自动重试失败的样本

### 3. 错误处理
- **执行失败**：如果 `execution_success=False`，直接返回 0 分，不进行 API 调用
- **文件缺失**：如果输入文件不存在，返回错误结果（`success=False`）
- **API 失败**：如果 API 调用失败，返回错误结果（`success=False`），详细信息保存在 `details` 中

### 4. 数据来源

#### CodeVQA
- **qa_pairs.json**：`{sample_dir}/qa_pairs.json`
  - 包含该样本的所有 QA 对
  - 每个 QA 对包含问题、答案、问题类型等信息

#### XDRFR
- **question_set.json**：`{instruction_dir}/question_set.json`
  - 包含该指令的分解问题
  - **只使用 `decomposed_questions`**，不使用 `common_questions`
- **diagram.xml**：`{sample_dir}/diagram.xml`
  - 原始 XML 代码
- **modified.xml**：`{instruction_dir}/model_{model_name}/modified.xml`
  - 修改后的 XML 代码
- **instruction.txt**：`{instruction_dir}/instruction.txt`
  - 修改指令（自然语言）

### 5. 评估策略

#### CodeVQA
- **基于图像**：使用视觉输入（渲染图）回答问题
- **答案匹配**：根据不同问题类型采用不同的答案匹配策略

#### XDRFR
- **基于代码**：完全基于 XML 代码评估，不依赖渲染图像
- **Yes/No 判断**：所有问题都是 Yes/No 问题，通过 LLM 判断修改后的 XML 是否满足要求

