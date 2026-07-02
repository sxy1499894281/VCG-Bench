"""
评估相关的 Prompt 模板集中管理

设计原则：
1. Prompt 与代码逻辑完全分离
2. 使用 Jinja2 模板引擎支持变量替换
3. 支持版本管理和 A/B 测试
4. 便于后续修改而无需改动代码
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json


# ============================================================================
# 风格一致性评估 (SCS) Prompts
# ============================================================================

SCS_PROMPT_V2 = """你是一名专业的图表设计评审员。请对比"原始图表"和"生成图表"，并按以下步骤进行系统性评估：

原始图表：
[Image: {{ original_image_path }}]

生成图表：
[Image: {{ generated_image_path }}]

**评估步骤：**

**步骤 1：属性提取**
请先仔细分析原始图表，提取以下关键属性：
- 配色方案：列出主要颜色的十六进制值或色系名称（如"蓝色系"、"暖色调"）
- 字体风格：字体粗细（细/中/粗）、大小（小/中/大）、字体族（如有）
- 布局结构：整体结构类型（树状/环状/线性/网格/自由布局）
- 视觉元素：节点形状（圆形/矩形/菱形等）、线条样式（实线/虚线/粗细）

**步骤 2：差异比对**
逐一检查生成图中上述属性的偏离程度：
- 配色方案是否保持一致？如有差异，描述具体差异
- 字体风格是否匹配？
- 布局结构是否相同？元素位置、间距关系是否一致？
- 视觉元素样式是否一致？

**步骤 3：维度打分（0-10 分制）**
请对以下三个维度分别打分（0-10 分，保留一位小数）：
1. 视觉风格一致性（色彩、线条粗细、节点样式）：___
2. 布局结构一致性（元素位置、间距、空间关系）：___
3. 审美质量（对齐、视觉平衡、整体美感）：___

**步骤 4：最终得分计算**
- 计算三个维度得分的平均值
- 将平均值除以 10，归一化到 0-1 之间
- 例如：维度得分 [8.5, 7.0, 9.0]，平均值 = 8.17，最终得分 = 0.817

**输出格式（JSON）：**
{
    "analysis": {
        "original_attributes": {
            "color_scheme": "...",
            "font_style": "...",
            "layout_structure": "...",
            "visual_elements": "..."
        },
        "differences": [
            "差异描述 1",
            "差异描述 2"
        ],
        "dimension_scores": {
            "visual_style_consistency": 8.5,
            "layout_consistency": 7.0,
            "aesthetic_quality": 9.0
        },
        "average_score": 8.17
    },
    "final_score": 0.817
}

**重要提示：**
- 请严格遵循评分标准，避免直接给出高分（0.85+）
- 必须先完成属性提取和差异比对，再给出维度打分
- 如果生成图表存在明显的视觉错误（如元素重叠、文字错位），应在相应维度中扣分
- 最终得分必须基于维度得分的平均值计算，不能直接估算
"""

# 旧版本 Prompt（向后兼容）
SCS_PROMPT_V1 = """Please evaluate the style consistency between the original diagram and the generated diagram.

Original diagram:
[Image: {{ original_image_path }}]

Generated diagram:
[Image: {{ generated_image_path }}]

Please evaluate the following aspects:
1. Style consistency: color scheme, visual style, design patterns
2. Aesthetic consistency: visual balance, composition, overall aesthetics
3. Layout consistency: element positions, spatial relationships, structure

Please rate the overall style consistency on a scale from 0 to 1, where:
- 1.0: Completely consistent in all aspects
- 0.75: Mostly consistent with minor differences
- 0.5: Moderately consistent with noticeable differences
- 0.25: Partially consistent with significant differences
- 0.0: Completely different styles

Please output only a single floating-point number between 0 and 1."""


# ============================================================================
# CodeVQA QA 对生成 Prompts
# ============================================================================

CODEVQA_QA_GENERATION_PROMPT_V2 = """请分析提供的图表图像，生成 3 个用于测试语义信息保留的问题-答案对。
必须包含以下三种类型，每种类型各一个：
1. 计数类（counting）：统计图表中元素的数量
2. 识别类（identification）：识别特定元素的属性或标签
3. 关系类（relationship）：识别元素之间的关系或连接

图像：[original_image]

**要求（增强版）：**

**1. 深度要求（提高区分度）**
- **计数类问题**：不应只问"有多少个节点"这种过于简单的问题。应包含对特定属性的计数，例如：
  - "图表中有多少个蓝色的圆形节点？"
  - "有多少条虚线连接？"
  - "有多少个节点的标签以字母'A'开头？"
- **识别类问题**：应测试具体的视觉细节，例如：
  - "id 为 'node_5' 的节点的填充颜色是什么？"
  - "位于图表左上角的节点的标签是什么？"
  - "连接节点A和节点B的线条是什么颜色？"
- **关系类问题**：应测试多级连接或复杂关系，例如：
  - "节点A通过哪些中间节点可以到达节点D？"
  - "哪些节点同时与节点B和节点C相连？"
  - "从根节点到叶子节点的最长路径包含多少个节点？"

**2. 语义唯一性**
- 确保每个问题的答案在图中是唯一的、无歧义的
- 避免可以通过常识或上下文猜测的问题
- 问题应要求模型必须仔细观察图像才能回答

**3. 视觉锚点**
- 引导问题关注图中的关键细节和特定位置
- 使用具体的标识符（如节点ID、位置描述）来锚定问题
- 防止模型通过一般性推理而非视觉观察来回答

**4. 可验证性**
- 答案应该具体且可验证（数字、颜色值、标签文本等）
- 避免主观判断类问题

**输出格式（JSON）：**
{
    "qa_pairs": [
        {
            "question": "图表中有多少个蓝色的圆形节点？",
            "answer": "3",
            "question_type": "counting",
            "visual_anchor": "蓝色圆形节点"
        },
        {
            "question": "id 为 'anchor' 的节点的填充颜色是什么（十六进制）？",
            "answer": "#FF5733",
            "question_type": "identification",
            "visual_anchor": "节点ID 'anchor'"
        },
        {
            "question": "节点A通过哪些中间节点可以到达节点D？请按顺序列出。",
            "answer": "节点B和节点C",
            "question_type": "relationship",
            "visual_anchor": "节点A到节点D的路径"
        }
    ]
}
"""


# ============================================================================
# HDRFR 指令拆解 Prompts
# ============================================================================

HDRFR_DECOMPOSITION_PROMPT_V2 = """请将以下图表修改指令拆解为一系列是/否问题，这些问题应该直接针对指令本身的内容，用于验证指令是否被正确遵循。

指令："{{ instruction }}"

**要求：**
1. 每个问题应该可以用"是"或"否"来回答
2. 问题应该直接针对指令中提到的具体修改内容
3. 问题应该可以通过比较原始图表和修改后的图表来验证
4. 问题应该清晰且明确，避免歧义
5. 只关注指令本身要求的内容，不要添加额外的检查项

**输出格式（JSON）：**
{
    "decomposed_questions": [
        "问题1？",
        "问题2？",
        "问题3？"
    ]
}

**示例：**
如果指令是"将节点A的颜色改为红色"，可以拆解为：
- "节点A的颜色是否已改为红色？"
- "节点A是否仍然存在于图表中？"

请只针对指令本身的内容生成问题，不要添加指令未提及的检查项。
"""

HDRFR_DECOMPOSITION_PROMPT_V1 = """请将以下图表修改指令拆解为一系列是/否问题，这些问题可用于验证指令是否被正确遵循。

指令："{{ instruction }}"

要求：
1. 每个问题应该可以用是或否来回答
2. 问题应该测试指令的特定方面
3. 问题应该可以通过比较原始图表和修改后的图表来验证
4. 覆盖指令中的所有关键要求
5. 问题应该清晰且明确

输出格式（JSON）：
{
    "decomposed_questions": [
        "问题 1？",
        "问题 2？",
        ...
    ]
}
"""


# ============================================================================
# HDRFR 最终评估 Prompts
# ============================================================================

HDRFR_EVALUATION_PROMPT_V2 = """根据提供的原始图表、修改后的图表和修改指令，用"是"或"否"回答以下问题。

原始图表（Gemini 生成）：
[Image: {{ gemini_image_path }}]

修改后的图表（模型生成）：
[Image: {{ modified_image_path }}]

修改指令：
"{{ instruction }}"

问题：
{{ question }}

**请按照以下格式回答：**

**【视觉证据】**
请分别描述原始图表和修改后图表中，问题所涉区域的具体状态：
- 原始图表中，相关区域的状态是什么？
- 修改后图表中，相关区域的状态是什么？
- 如果问题涉及其他元素（如其他节点、连线），请描述它们的状态。

**【判断逻辑】**
基于上述视觉证据，比对指令要求：
- 指令要求修改什么？
- 修改后的图表是否满足指令要求？
- 如果问题涉及负向约束（如"其他节点是否保持不变"），请检查是否有不应修改的元素被修改。

**【结论】**
基于证据和逻辑，给出最终判断：是/否

**输出格式（JSON）：**
{
    "visual_evidence": {
        "original_state": "原始图表中相关区域的状态描述",
        "modified_state": "修改后图表中相关区域的状态描述",
        "other_elements": "其他相关元素的状态描述"
    },
    "judgment_logic": "基于证据的判断逻辑说明",
    "conclusion": "是" 或 "否"
}

**重要规则：**
1. **必须提供视觉证据**：不能仅凭推测或假设回答，必须基于实际观察到的图表内容
2. **考虑渲染错误**：如果修改后的图表出现了渲染错误（如文字重叠、连线错位、元素缺失），即使指令已完成，在审美相关问题中也应考虑回答"否"
3. **负向约束严格性**：对于负向约束问题（如"其他节点是否保持不变"），如果发现任何不应修改的元素被修改，应回答"否"
4. **细微差异识别**：对于颜色、位置等细微修改，请仔细观察并准确描述，避免因细微差异而误判

**如果问题类型为负向约束（side_effect_check），请特别关注：**
- 是否有不应修改的元素被修改？
- 是否有不应删除的元素被删除？
- 是否有不应添加的元素被添加？
- 修改是否导致了意外的视觉问题？
"""

HDRFR_EVALUATION_PROMPT_V1 = """根据提供的原始图表、修改后的图表和修改指令，用"是"或"否"回答以下问题。

原始图表（Gemini 生成）：
[Image: {{ gemini_image_path }}]

修改后的图表（模型生成）：
[Image: {{ modified_image_path }}]

修改指令：
"{{ instruction }}"

问题：
{{ question }}

规则：
- 是：如果修改后的图表完全满足问题中指定的条件，同时正确遵循了修改指令，则选择"是"。
- 否：如果修改后的图表未能满足问题的要求，或者没有正确遵循修改指令，则选择"否"。

请只回答"是"或"否"。
"""


# ============================================================================
# Prompt 版本配置
# ============================================================================

PROMPT_VERSIONS = {
    "scs": {
        "default": "v2",
        "versions": {
            "v1": SCS_PROMPT_V1,
            "v2": SCS_PROMPT_V2,
        }
    },
    "codevqa_qa_generation": {
        "default": "v2",
        "versions": {
            "v2": CODEVQA_QA_GENERATION_PROMPT_V2,
        }
    },
    "hdrfr_decomposition": {
        "default": "v2",
        "versions": {
            "v1": HDRFR_DECOMPOSITION_PROMPT_V1,
            "v2": HDRFR_DECOMPOSITION_PROMPT_V2,
        }
    },
    "hdrfr_evaluation": {
        "default": "v2",
        "versions": {
            "v1": HDRFR_EVALUATION_PROMPT_V1,
            "v2": HDRFR_EVALUATION_PROMPT_V2,
        }
    }
}


def get_prompt(prompt_name: str, version: Optional[str] = None) -> str:
    """
    获取指定名称和版本的 Prompt
    
    Args:
        prompt_name: Prompt 名称（如 "scs", "hdrfr_evaluation"）
        version: 版本号（如 "v1", "v2"），如果为 None 则使用默认版本
    
    Returns:
        Prompt 模板字符串
    """
    if prompt_name not in PROMPT_VERSIONS:
        raise ValueError(f"Unknown prompt name: {prompt_name}")
    
    config = PROMPT_VERSIONS[prompt_name]
    version = version or config["default"]
    
    if version not in config["versions"]:
        raise ValueError(f"Unknown version '{version}' for prompt '{prompt_name}'")
    
    return config["versions"][version]


def render_prompt(prompt_template: str, **kwargs) -> str:
    """
    渲染 Prompt 模板（使用简单的字符串替换，避免 Jinja2 依赖）
    
    Args:
        prompt_template: Prompt 模板字符串（使用 {{ variable_name }} 格式）
        **kwargs: 模板变量
    
    Returns:
        渲染后的 Prompt 字符串
    """
    result = prompt_template
    for key, value in kwargs.items():
        placeholder = f"{{{{ {key} }}}}"
        result = result.replace(placeholder, str(value))
    return result


# 如果安装了 Jinja2，可以使用更强大的模板引擎
try:
    from jinja2 import Template
    
    def render_prompt_jinja2(prompt_template: str, **kwargs) -> str:
        """
        使用 Jinja2 渲染 Prompt 模板（支持更复杂的逻辑）
        
        Args:
            prompt_template: Prompt 模板字符串
            **kwargs: 模板变量
        
        Returns:
            渲染后的 Prompt 字符串
        """
        template = Template(prompt_template)
        return template.render(**kwargs)
    
    # 默认使用 Jinja2（如果可用）
    render_prompt = render_prompt_jinja2
except ImportError:
    # 如果没有 Jinja2，使用简单的字符串替换
    pass

