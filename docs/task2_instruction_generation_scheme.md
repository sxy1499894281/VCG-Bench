# 任务2指令生成方案

## 一、方案概述

### 1.1 核心策略

1. **使用3个专用Prompt**：分别为Easy、Medium、Hard三个难度等级设计专用Prompt
2. **对每张图片生成3条指令**：使用3个不同的Prompt分别生成1条指令，确保覆盖Easy/Medium/Hard三个难度等级
3. **统一的难度标准**：3个Prompt共用一套难度分级标准，确保难度划分的一致性和可解释性

### 1.2 工作流程

```
对于每个样本（Gemini XML + Gemini 渲染图）：
├── 使用 Easy Prompt → 生成1条 Easy 难度指令
├── 使用 Medium Prompt → 生成1条 Medium 难度指令
└── 使用 Hard Prompt → 生成1条 Hard 难度指令

最终得到：每个样本有3条指令，分别对应Easy/Medium/Hard三个难度等级
```

---

## 二、统一的难度分级标准

### 2.1 难度评估的五个维度

我们采用**五维度综合评分体系**来划分指令难度，确保难度划分的科学性和可解释性：

#### 维度1：操作复杂度 (Operation Complexity)

- **Level 1 (1分) - 单操作**：仅涉及一个原子操作
  - 示例："删除节点A"、"将节点B的颜色改为红色"
  
- **Level 2 (2分) - 双操作**：涉及两个相关操作，但操作顺序明确
  - 示例："删除节点A及其所有连接线"、"将节点B移动到位置(x, y)并更新连接"
  
- **Level 3 (3分) - 复合操作**：涉及3个及以上操作，或需要协调多个元素
  - 示例："删除节点A，将其所有输入连接指向节点B，输出连接指向节点C"

#### 维度2：指令明确性 (Instruction Clarity)

- **Level 1 (1分) - 明确指令**：直接指定目标元素（通过ID、标签、位置等唯一标识）
  - 示例："删除id为'node_1'的节点"、"将标签为'Start'的节点颜色改为#FF0000"
  
- **Level 2 (2分) - 半明确指令**：通过描述性特征定位元素，需要一次推理
  - 示例："删除最上方的节点"、"将红色节点改为蓝色"
  
- **Level 3 (3分) - 模糊指令**：需要上下文理解、语义推理或多步骤定位
  - 示例："删除流程图的起始节点"、"将关键路径上的所有节点高亮显示"

#### 维度3：修改范围 (Modification Scope)

- **Level 1 (1分) - 单元素修改**：仅修改一个元素
  - 示例："删除节点A"、"修改箭头B的颜色"
  
- **Level 2 (2分) - 局部批量修改**：修改同一类型或同一区域的多个元素（2-5个）
  - 示例："将所有矩形节点改为圆形"、"删除左侧区域的所有节点"
  
- **Level 3 (3分) - 全局批量修改**：修改整个图表的大量元素（5个以上）或全局属性
  - 示例："将所有节点的颜色改为红色"、"调整整个图表的布局方向"

#### 维度4：依赖关系复杂度 (Dependency Complexity)

- **Level 1 (1分) - 独立操作**：操作不依赖其他元素的状态
  - 示例："删除节点A"、"修改节点B的颜色"
  
- **Level 2 (2分) - 简单依赖**：操作需要检查或更新1-2个相关元素
  - 示例："删除节点A及其连接线"、"将节点B移动到新位置并更新连接"
  
- **Level 3 (3分) - 复杂依赖**：操作需要处理多个元素的依赖关系，或需要维护全局一致性
  - 示例："删除节点A，将其所有输入重新连接到节点B，输出连接到节点C"

#### 维度5：操作类型难度 (Operation Type Difficulty)

- **Level 1 (1分)**：属性修改（仅修改元素属性，不改变结构）
  - 示例："修改节点颜色"、"改变文本大小"
  
- **Level 2 (2分)**：元素删除（简单删除为L1，带连接处理为L2）、元素添加、元素移动（简单移动）
  - 示例："删除节点及连接"、"在节点A右侧添加新节点"
  
- **Level 3 (3分)**：布局调整、结构重组（改变图表拓扑结构）
  - 示例："改为横向布局"、"合并节点"、"拆分节点"

### 2.2 综合难度评分与等级划分

**总分计算**：
```
总难度分数 = 操作复杂度 + 指令明确性 + 修改范围 + 依赖关系复杂度 + 操作类型难度
```

**难度等级划分**：
- **Easy (简单)**：总分 **5-8分**
  - 典型特征：单操作、明确指令、单元素、独立操作
  - 示例："删除id为'node_1'的节点"（1+1+1+1+1=5分）
  
- **Medium (中等)**：总分 **9-12分**
  - 典型特征：双操作、半明确指令、局部批量、简单依赖
  - 示例："删除最上方的节点及其所有连接线"（2+2+1+2+2=9分）
  
- **Hard (困难)**：总分 **13-18分**
  - 典型特征：复合操作、模糊指令、全局批量、复杂依赖
  - 示例："将关键路径上的所有节点高亮显示，并优化整体布局"（3+3+3+3+3=15分）

---

## 三、三个专用Prompt设计

### 3.1 Easy难度指令生成Prompt

```python
def get_easy_instruction_prompt(xml_content: str, rendered_image_path: str) -> str:
    """
    生成Easy难度指令的专用Prompt
    
    目标：生成总分5-8分的简单指令
    典型特征：单操作、明确指令、单元素、独立操作
    """
    prompt = f"""你是一个专业的图表编辑指令生成专家。你的任务是为给定的图表生成一条**Easy难度**的修改指令。

## 输入信息

**XML结构**：
```xml
{xml_content}
```

**渲染图**：请查看提供的渲染图以理解图表的视觉结构。

---

## 难度标准（必须严格遵守）

你需要生成一条**Easy难度**的指令，该指令必须满足以下所有条件：

### Easy难度要求（总分5-8分）

1. **操作复杂度**：必须是**单操作（Level 1, 1分）**
   - 仅涉及一个原子操作
   - 示例："删除节点A"、"将节点B的颜色改为红色"、"在节点C下方添加新节点D"
   - ❌ 禁止：涉及多个操作或需要协调多个元素

2. **指令明确性**：必须是**明确指令（Level 1, 1分）**
   - 直接指定目标元素（通过ID、标签、位置等唯一标识）
   - 示例："删除id为'node_1'的节点"、"将标签为'Start'的节点颜色改为#FF0000"
   - ❌ 禁止：使用描述性特征（如"最上方的节点"）或需要语义推理

3. **修改范围**：必须是**单元素修改（Level 1, 1分）**
   - 仅修改一个元素
   - 示例："删除节点A"、"修改箭头B的颜色"
   - ❌ 禁止：批量修改多个元素

4. **依赖关系复杂度**：必须是**独立操作（Level 1, 1分）**
   - 操作不依赖其他元素的状态
   - 示例："删除节点A"、"修改节点B的颜色"
   - ❌ 禁止：需要检查或更新其他相关元素

5. **操作类型难度**：建议使用**属性修改（Level 1, 1分）**或**简单删除（Level 1, 1分）**
   - 属性修改：仅修改元素属性，不改变结构
   - 简单删除：删除单个元素，不涉及连接处理
   - ❌ 禁止：布局调整、结构重组等复杂操作

**总分范围**：5-8分（1+1+1+1+1=5分 到 2+1+1+1+2=7分）

---

## 指令生成要求

1. **分析图表结构**：
   - 仔细分析XML结构和渲染图，识别所有可修改的元素（节点、连线、文本等）
   - 确保生成的指令针对图表中实际存在的元素

2. **生成Easy难度指令**：
   - 必须严格遵守上述5个维度的Easy难度要求
   - 指令必须**明确、具体、可执行**
   - 使用直接定位方式（ID、标签、位置坐标等）

3. **指令多样性**：
   - 可以生成不同类型的操作（删除、修改属性、添加元素等）
   - 但必须确保所有操作都符合Easy难度标准

4. **可执行性**：
   - 生成的指令必须能够通过规则代码自动执行
   - 目标元素必须在XML中明确存在

---

## 输出格式（严格JSON）

请输出一个JSON对象，格式如下：

```json
{{
  "instruction": "具体的修改指令文本",
  "target_element": {{
    "type": "node|edge|text|container",
    "identifier": "用于定位目标元素的信息（如ID、标签等）",
    "description": "目标元素的简要描述"
  }},
  "operation_type": "delete|modify_attribute|add_element|move",
  "difficulty_analysis": {{
    "operation_complexity": 1,
    "instruction_clarity": 1,
    "modification_scope": 1,
    "dependency_complexity": 1,
    "operation_type_difficulty": 1,
    "total_score": 5,
    "level": "Easy"
  }},
  "executable": true,
  "reasoning": "简要说明为什么这条指令符合Easy难度标准"
}}
```

---

## 示例

**示例1（删除操作）**：
```json
{{
  "instruction": "删除id为'node_1'的节点",
  "target_element": {{
    "type": "node",
    "identifier": "node_1",
    "description": "XML中id属性为'node_1'的节点"
  }},
  "operation_type": "delete",
  "difficulty_analysis": {{
    "operation_complexity": 1,
    "instruction_clarity": 1,
    "modification_scope": 1,
    "dependency_complexity": 1,
    "operation_type_difficulty": 1,
    "total_score": 5,
    "level": "Easy"
  }},
  "executable": true,
  "reasoning": "单操作删除、明确ID定位、单元素修改、独立操作、简单删除类型，总分5分，符合Easy难度"
}}
```

**示例2（属性修改）**：
```json
{{
  "instruction": "将id为'node_2'的节点的填充颜色改为#FF0000",
  "target_element": {{
    "type": "node",
    "identifier": "node_2",
    "description": "XML中id属性为'node_2'的节点"
  }},
  "operation_type": "modify_attribute",
  "difficulty_analysis": {{
    "operation_complexity": 1,
    "instruction_clarity": 1,
    "modification_scope": 1,
    "dependency_complexity": 1,
    "operation_type_difficulty": 1,
    "total_score": 5,
    "level": "Easy"
  }},
  "executable": true,
  "reasoning": "单操作属性修改、明确ID定位、单元素修改、独立操作、属性修改类型，总分5分，符合Easy难度"
}}
```

---

## 重要提醒

1. **严格遵守Easy难度标准**：所有5个维度都必须控制在Level 1（1分），总分不超过8分
2. **使用明确定位**：必须使用ID、标签等唯一标识，禁止使用描述性特征
3. **单元素操作**：只能修改一个元素，不能批量操作
4. **独立操作**：不能涉及其他元素的依赖关系
5. **输出格式**：必须严格按照JSON格式输出，不要包含任何解释文字或Markdown代码块标记

请分析图表并生成一条Easy难度的修改指令：
"""
    return prompt
```

---

### 3.2 Medium难度指令生成Prompt

```python
def get_medium_instruction_prompt(xml_content: str, rendered_image_path: str) -> str:
    """
    生成Medium难度指令的专用Prompt
    
    目标：生成总分9-12分的中等难度指令
    典型特征：双操作、半明确指令、局部批量、简单依赖
    """
    prompt = f"""你是一个专业的图表编辑指令生成专家。你的任务是为给定的图表生成一条**Medium难度**的修改指令。

## 输入信息

**XML结构**：
```xml
{xml_content}
```

**渲染图**：请查看提供的渲染图以理解图表的视觉结构。

---

## 难度标准（必须严格遵守）

你需要生成一条**Medium难度**的指令，该指令必须满足以下条件：

### Medium难度要求（总分9-12分）

1. **操作复杂度**：必须是**双操作（Level 2, 2分）**
   - 涉及两个相关操作，但操作顺序明确
   - 示例："删除节点A及其所有连接线"、"将节点B移动到位置(x, y)并更新连接"
   - ❌ 禁止：单操作（太简单）或复合操作（3个及以上，太复杂）

2. **指令明确性**：建议使用**半明确指令（Level 2, 2分）**，也可以使用明确指令（Level 1, 1分）
   - 半明确指令：通过描述性特征定位元素，需要一次推理
   - 示例："删除最上方的节点"、"将红色节点改为蓝色"、"在最大的节点下方添加新节点"
   - 也可以使用明确指令（Level 1）来平衡总分

3. **修改范围**：建议使用**局部批量修改（Level 2, 2分）**，也可以使用单元素修改（Level 1, 1分）
   - 局部批量：修改同一类型或同一区域的多个元素（2-5个）
   - 示例："将所有矩形节点改为圆形"、"删除左侧区域的所有节点"
   - 也可以使用单元素修改来平衡总分

4. **依赖关系复杂度**：必须是**简单依赖（Level 2, 2分）**
   - 操作需要检查或更新1-2个相关元素
   - 示例："删除节点A及其连接线"、"将节点B移动到新位置并更新连接"
   - ❌ 禁止：独立操作（太简单）或复杂依赖（太复杂）

5. **操作类型难度**：建议使用**元素删除（带连接处理，Level 2, 2分）**、**元素添加（Level 2, 2分）**或**元素移动（简单移动，Level 2, 2分）**
   - 元素删除（带连接处理）：需要处理连接关系
   - 元素添加：需要确定位置和连接关系
   - 元素移动（简单移动）：需要更新连接坐标
   - ❌ 禁止：布局调整、结构重组等Level 3操作

**总分范围**：9-12分
- 最低：2+1+1+2+2=8分（接近Easy，需要调整）→ 建议：2+2+1+2+2=9分
- 最高：2+2+2+2+2=10分 或 2+1+2+2+2=9分 或 2+2+1+2+3=10分（如果操作类型是Level 3，需要降低其他维度）

---

## 指令生成要求

1. **分析图表结构**：
   - 仔细分析XML结构和渲染图，识别所有可修改的元素
   - 特别关注元素之间的关系（连接、包含等），以便生成涉及依赖关系的指令

2. **生成Medium难度指令**：
   - 必须严格遵守上述5个维度的Medium难度要求
   - 指令必须**明确、可执行**，但可以包含描述性定位（如"最上方的节点"）
   - 必须涉及两个相关操作或需要处理依赖关系

3. **指令多样性**：
   - 可以生成不同类型的操作（删除+连接处理、移动+更新连接、批量修改等）
   - 但必须确保所有操作都符合Medium难度标准

4. **可执行性**：
   - 生成的指令必须能够通过规则代码自动执行
   - 如果使用描述性定位，必须确保目标元素可以通过属性匹配唯一确定

---

## 输出格式（严格JSON）

请输出一个JSON对象，格式如下：

```json
{{
  "instruction": "具体的修改指令文本",
  "target_element": {{
    "type": "node|edge|text|container|multiple",
    "identifier": "用于定位目标元素的信息（可以是ID、标签、描述性特征等）",
    "description": "目标元素的简要描述"
  }},
  "operation_type": "delete_with_connections|modify_batch|add_element|move_with_update",
  "difficulty_analysis": {{
    "operation_complexity": 2,
    "instruction_clarity": 1或2,
    "modification_scope": 1或2,
    "dependency_complexity": 2,
    "operation_type_difficulty": 2,
    "total_score": 9-12,
    "level": "Medium"
  }},
  "executable": true,
  "reasoning": "简要说明为什么这条指令符合Medium难度标准，包括各维度的评分理由"
}}
```

---

## 示例

**示例1（删除+连接处理）**：
```json
{{
  "instruction": "删除最上方的节点及其所有连接线",
  "target_element": {{
    "type": "node",
    "identifier": "最上方的节点（通过y坐标最小确定）",
    "description": "图表中y坐标最小的节点"
  }},
  "operation_type": "delete_with_connections",
  "difficulty_analysis": {{
    "operation_complexity": 2,
    "instruction_clarity": 2,
    "modification_scope": 1,
    "dependency_complexity": 2,
    "operation_type_difficulty": 2,
    "total_score": 9,
    "level": "Medium"
  }},
  "executable": true,
  "reasoning": "双操作（删除节点+删除连接）、半明确定位（最上方需要推理）、单元素修改、简单依赖（需要找到并删除连接）、元素删除（带连接处理），总分9分，符合Medium难度"
}}
```

**示例2（批量修改）**：
```json
{{
  "instruction": "将所有矩形节点的填充颜色改为蓝色",
  "target_element": {{
    "type": "multiple",
    "identifier": "所有shape为矩形的节点",
    "description": "图表中所有矩形形状的节点（2-5个）"
  }},
  "operation_type": "modify_batch",
  "difficulty_analysis": {{
    "operation_complexity": 2,
    "instruction_clarity": 1,
    "modification_scope": 2,
    "dependency_complexity": 1,
    "operation_type_difficulty": 1,
    "total_score": 7,
    "level": "Easy"
  }},
  "executable": true,
  "reasoning": "注意：此示例总分7分，不符合Medium难度。需要调整为：操作复杂度2（批量修改需要遍历）+指令明确性2（描述性定位）+修改范围2（批量）+依赖关系复杂度2（需要检查每个节点）+操作类型难度2（批量属性修改）=10分，符合Medium难度"
}}
```

**示例3（移动+更新连接）**：
```json
{{
  "instruction": "将标签为'Start'的节点移动到坐标(200, 300)并更新所有连接线的路径",
  "target_element": {{
    "type": "node",
    "identifier": "标签为'Start'的节点",
    "description": "XML中value或label属性包含'Start'的节点"
  }},
  "operation_type": "move_with_update",
  "difficulty_analysis": {{
    "operation_complexity": 2,
    "instruction_clarity": 1,
    "modification_scope": 1,
    "dependency_complexity": 2,
    "operation_type_difficulty": 2,
    "total_score": 8,
    "level": "Easy"
  }},
  "executable": true,
  "reasoning": "注意：此示例总分8分，处于Easy和Medium边界。需要调整为：操作复杂度2+指令明确性2（使用描述性定位如'最左侧的节点'）+修改范围1+依赖关系复杂度2+操作类型难度2=9分，符合Medium难度"
}}
```

---

## 重要提醒

1. **严格遵守Medium难度标准**：总分必须在9-12分之间，不能低于9分，不能高于12分
2. **必须涉及依赖关系**：必须包含简单依赖（Level 2），不能是独立操作
3. **双操作要求**：必须涉及两个相关操作，不能是单操作
4. **可以灵活组合**：可以在明确性、修改范围等维度上灵活调整，但总分必须控制在9-12分
5. **输出格式**：必须严格按照JSON格式输出，不要包含任何解释文字或Markdown代码块标记

请分析图表并生成一条Medium难度的修改指令：
"""
    return prompt
```

---

### 3.3 Hard难度指令生成Prompt

```python
def get_hard_instruction_prompt(xml_content: str, rendered_image_path: str) -> str:
    """
    生成Hard难度指令的专用Prompt
    
    目标：生成总分13-18分的困难指令
    典型特征：复合操作、模糊指令、全局批量、复杂依赖
    """
    prompt = f"""你是一个专业的图表编辑指令生成专家。你的任务是为给定的图表生成一条**Hard难度**的修改指令。

## 输入信息

**XML结构**：
```xml
{xml_content}
```

**渲染图**：请查看提供的渲染图以理解图表的视觉结构。

---

## 难度标准（必须严格遵守）

你需要生成一条**Hard难度**的指令，该指令必须满足以下条件：

### Hard难度要求（总分13-18分）

1. **操作复杂度**：必须是**复合操作（Level 3, 3分）**
   - 涉及3个及以上操作，或需要协调多个元素
   - 示例："删除节点A，将其所有输入连接指向节点B，输出连接指向节点C"
   - 示例："将布局从纵向改为横向，并重新排列所有节点间距"
   - ❌ 禁止：单操作或双操作（太简单）

2. **指令明确性**：建议使用**模糊指令（Level 3, 3分）**，也可以使用半明确指令（Level 2, 2分）来平衡总分
   - 模糊指令：需要上下文理解、语义推理或多步骤定位
   - 示例："删除流程图的起始节点"（需要理解流程图语义）
   - 示例："将关键路径上的所有节点高亮"（需要计算关键路径）
   - 示例："优化布局使其更美观"（主观判断）
   - 也可以使用半明确指令（Level 2）来平衡总分

3. **修改范围**：建议使用**全局批量修改（Level 3, 3分）**，也可以使用局部批量修改（Level 2, 2分）来平衡总分
   - 全局批量：修改整个图表的大量元素（5个以上）或全局属性
   - 示例："将所有节点的颜色改为红色"、"调整整个图表的布局方向"
   - 也可以使用局部批量（Level 2）来平衡总分

4. **依赖关系复杂度**：必须是**复杂依赖（Level 3, 3分）**
   - 操作需要处理多个元素的依赖关系，或需要维护全局一致性
   - 示例："删除节点A，将其所有输入重新连接到节点B，输出连接到节点C"
   - 示例："合并节点A和B，保留所有连接关系并重新计算布局"
   - ❌ 禁止：独立操作或简单依赖（太简单）

5. **操作类型难度**：建议使用**布局调整（Level 3, 3分）**或**结构重组（Level 3, 3分）**
   - 布局调整：涉及多个元素的协调
   - 结构重组：改变图表拓扑结构
   - 示例："改为横向布局"、"优化间距"、"合并节点"、"拆分节点"
   - 也可以使用元素移动（带布局调整，Level 3）来平衡总分

**总分范围**：13-18分
- 最低：3+2+2+3+3=13分（复合操作+半明确+局部批量+复杂依赖+布局调整）
- 最高：3+3+3+3+3=18分（所有维度都是Level 3）

---

## 指令生成要求

1. **分析图表结构**：
   - 仔细分析XML结构和渲染图，理解图表的整体拓扑结构
   - 识别关键路径、依赖关系、布局模式等，以便生成涉及复杂语义的指令

2. **生成Hard难度指令**：
   - 必须严格遵守上述5个维度的Hard难度要求
   - 指令可以包含语义推理、全局操作、复杂依赖关系
   - 必须涉及3个及以上操作，或需要协调多个元素

3. **指令多样性**：
   - 可以生成不同类型的复杂操作（结构重组、布局优化、全局批量修改等）
   - 但必须确保所有操作都符合Hard难度标准

4. **可执行性**：
   - 生成的指令应该尽可能可执行，但允许包含需要语义理解的复杂操作
   - 如果指令过于复杂无法自动执行，需要在reasoning中说明

---

## 输出格式（严格JSON）

请输出一个JSON对象，格式如下：

```json
{{
  "instruction": "具体的修改指令文本",
  "target_element": {{
    "type": "node|edge|text|container|multiple|global",
    "identifier": "用于定位目标元素的信息（可以是语义描述、全局属性等）",
    "description": "目标元素的简要描述"
  }},
  "operation_type": "restructure|layout_optimization|global_batch|merge|split",
  "difficulty_analysis": {{
    "operation_complexity": 3,
    "instruction_clarity": 2或3,
    "modification_scope": 2或3,
    "dependency_complexity": 3,
    "operation_type_difficulty": 3,
    "total_score": 13-18,
    "level": "Hard"
  }},
  "executable": true或false,
  "reasoning": "简要说明为什么这条指令符合Hard难度标准，包括各维度的评分理由，以及可执行性说明"
}}
```

---

## 示例

**示例1（结构重组）**：
```json
{{
  "instruction": "将关键路径上的所有节点高亮显示为红色，并优化整体布局使其更紧凑",
  "target_element": {{
    "type": "multiple",
    "identifier": "关键路径上的所有节点（需要通过拓扑分析确定）",
    "description": "图表中位于关键路径上的所有节点（需要计算最长路径）"
  }},
  "operation_type": "restructure",
  "difficulty_analysis": {{
    "operation_complexity": 3,
    "instruction_clarity": 3,
    "modification_scope": 3,
    "dependency_complexity": 3,
    "operation_type_difficulty": 3,
    "total_score": 15,
    "level": "Hard"
  }},
  "executable": true,
  "reasoning": "复合操作（高亮+布局优化）、模糊指令（关键路径需要语义推理）、全局批量（多个节点+整体布局）、复杂依赖（需要计算关键路径并维护布局一致性）、结构重组类型，总分15分，符合Hard难度"
}}
```

**示例2（合并节点）**：
```json
{{
  "instruction": "将流程图中所有功能相似的节点合并为一个新节点，并保留所有连接关系，重新计算布局",
  "target_element": {{
    "type": "multiple",
    "identifier": "功能相似的节点（需要通过语义分析确定）",
    "description": "图表中功能或标签相似的多个节点（需要语义理解）"
  }},
  "operation_type": "merge",
  "difficulty_analysis": {{
    "operation_complexity": 3,
    "instruction_clarity": 3,
    "modification_scope": 3,
    "dependency_complexity": 3,
    "operation_type_difficulty": 3,
    "total_score": 15,
    "level": "Hard"
  }},
  "executable": false,
  "reasoning": "复合操作（合并+保留连接+重新布局）、模糊指令（功能相似需要语义推理）、全局批量（多个节点+全局布局）、复杂依赖（需要维护所有连接关系并重新计算布局）、结构重组类型，总分15分，符合Hard难度。但'功能相似'的判断需要语义理解，可能无法完全自动执行"
}}
```

**示例3（布局优化）**：
```json
{{
  "instruction": "将布局从纵向改为横向，并重新排列所有节点间距使其均匀分布，同时调整所有连接线的路径以避免交叉",
  "target_element": {{
    "type": "global",
    "identifier": "整个图表",
    "description": "图表的所有节点和连接线"
  }},
  "operation_type": "layout_optimization",
  "difficulty_analysis": {{
    "operation_complexity": 3,
    "instruction_clarity": 2,
    "modification_scope": 3,
    "dependency_complexity": 3,
    "operation_type_difficulty": 3,
    "total_score": 14,
    "level": "Hard"
  }},
  "executable": true,
  "reasoning": "复合操作（改变方向+重新排列+调整路径）、半明确指令（整体布局描述）、全局批量（所有节点和连接线）、复杂依赖（需要协调所有元素避免交叉）、布局调整类型，总分14分，符合Hard难度"
}}
```

---

## 重要提醒

1. **严格遵守Hard难度标准**：总分必须在13-18分之间，不能低于13分
2. **必须涉及复杂依赖**：必须包含复杂依赖（Level 3），不能是独立操作或简单依赖
3. **复合操作要求**：必须涉及3个及以上操作，或需要协调多个元素
4. **可以灵活组合**：可以在明确性、修改范围等维度上灵活调整，但总分必须控制在13-18分
5. **可执行性说明**：如果指令包含需要语义理解的复杂操作，需要在reasoning中说明可执行性
6. **输出格式**：必须严格按照JSON格式输出，不要包含任何解释文字或Markdown代码块标记

请分析图表并生成一条Hard难度的修改指令：
"""
    return prompt
```

---

## 四、实现建议

### 4.1 Prompt调用流程

```python
# 伪代码示例
for sample in task2_benchmark_samples:
    xml_content = sample.diagram.xml
    rendered_image = sample.rendered.png
    
    # 使用3个不同的Prompt分别生成1条指令
    easy_instruction = llm_client.generate(
        prompt=get_easy_instruction_prompt(xml_content, rendered_image),
        model="gemini-pro"
    )
    
    medium_instruction = llm_client.generate(
        prompt=get_medium_instruction_prompt(xml_content, rendered_image),
        model="gemini-pro"
    )
    
    hard_instruction = llm_client.generate(
        prompt=get_hard_instruction_prompt(xml_content, rendered_image),
        model="gemini-pro"
    )
    
    # 保存3条指令
    save_instructions(sample, [
        {"level": "Easy", "instruction": easy_instruction},
        {"level": "Medium", "instruction": medium_instruction},
        {"level": "Hard", "instruction": hard_instruction}
    ])
```

### 4.2 难度验证

建议在生成指令后，对每条指令进行难度验证：

```python
def validate_instruction_difficulty(instruction_json: dict) -> bool:
    """验证指令是否符合目标难度等级"""
    difficulty = instruction_json["difficulty_analysis"]
    total_score = difficulty["total_score"]
    level = difficulty["level"]
    
    if level == "Easy" and 5 <= total_score <= 8:
        return True
    elif level == "Medium" and 9 <= total_score <= 12:
        return True
    elif level == "Hard" and 13 <= total_score <= 18:
        return True
    else:
        return False
```

### 4.3 数据格式

每条指令应保存为以下格式：

```json
{
  "instruction_id": "inst_001",
  "instruction": "删除id为'node_1'的节点",
  "difficulty_level": "Easy",
  "difficulty_analysis": {
    "operation_complexity": 1,
    "instruction_clarity": 1,
    "modification_scope": 1,
    "dependency_complexity": 1,
    "operation_type_difficulty": 1,
    "total_score": 5,
    "level": "Easy"
  },
  "target_element": {
    "type": "node",
    "identifier": "node_1",
    "description": "XML中id属性为'node_1'的节点"
  },
  "operation_type": "delete",
  "executable": true
}
```

---

## 五、与审稿人的说明

### 5.1 难度划分标准的可解释性

我们采用**五维度综合评分体系**来划分指令难度，确保难度划分的科学性和可解释性：

1. **操作复杂度**：评估指令涉及的操作数量
2. **指令明确性**：评估定位目标元素的难度
3. **修改范围**：评估需要修改的元素数量
4. **依赖关系复杂度**：评估操作涉及的依赖关系
5. **操作类型难度**：评估操作类型的内在复杂度

每个维度都有明确的Level 1-3分级标准，最终通过综合评分（5-18分）划分为Easy（5-8分）、Medium（9-12分）、Hard（13-18分）三个等级。

### 5.2 三个Prompt的一致性

三个Prompt共用同一套难度标准，确保：
- **一致性**：所有指令都基于相同的5个维度进行评估
- **可解释性**：每条指令都有详细的难度分析，包括各维度的评分
- **可复现性**：审稿人可以根据标准自行验证指令难度

### 5.3 数据集的平衡性

通过为每个样本生成3条不同难度的指令，确保：
- **难度覆盖**：每个样本都有Easy/Medium/Hard三个难度等级的指令
- **数据平衡**：三个难度等级的指令数量相等
- **多样性**：同一图表的不同难度指令可以测试模型在不同复杂度下的表现

---

## 六、总结

本方案通过：
1. **统一的难度标准**：五维度综合评分体系，确保可解释性
2. **三个专用Prompt**：分别针对Easy/Medium/Hard设计，确保难度一致性
3. **每样本3条指令**：确保难度覆盖和数据平衡

实现了任务2指令生成的系统化、标准化和可解释化。

