#!/usr/bin/env python3
"""
Task 2: Instruction Generation
使用1个统一Prompt为每个样本生成3条不同难度的指令（Easy/Medium/Hard）
基于原子操作数量的难度划分
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

from src.llm.client import LLMClient
from configs.settings import get_settings

# Setup logging
log_dir = Path(__file__).parent.parent.parent / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'task2_instruction_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _should_retry_error(error_type: str, error_message: str) -> bool:
    """
    判断错误是否应该重试（API请求失败和权限错误都会重试）
    
    Args:
        error_type: 错误类型名称（如 'APITimeoutError', 'ConnectionError', 'PermissionDeniedError' 等）
        error_message: 错误消息
        
    Returns:
        True: 应该重试（网络/超时/权限错误）
        False: 不应该重试（业务逻辑错误，如JSON解析错误）
    """
    error_type_lower = error_type.lower()
    error_message_lower = error_message.lower()
    
    # 应该重试的异常类型（网络/超时/连接错误/权限错误/API错误/速率限制错误）
    retryable_error_types = [
        'apitimeouterror',
        'timeouterror',
        'connecttimeout',
        'readtimeout',
        'connectionerror',
        'connecterror',
        'networkerror',
        'httperror',
        'httpstatuserror',
        'requestexception',
        'connectionrefusederror',
        'connectionreseterror',
        'connectionabortederror',
        'httpxconnecttimeout',
        'httpxreadtimeout',
        'httpxconnecterror',
        'httpxrequesterror',
        'authenticationerror',  # 401错误，API key无效，可能是配置问题，允许重试
        'permissiondeniederror',  # 权限错误（如403），可能是API配置问题，允许重试
        'notfounderror',  # 404错误，可能是模型服务暂时不可用或配置问题，允许重试
        'badrequesterror',  # 400错误，可能是模型配置问题（如context length），允许重试
        'ratelimiterror',  # 429错误，速率限制，应该重试
        'rate limit',  # 速率限制相关错误
        'internalservererror',  # 500/503错误，服务器内部错误，应该重试
    ]
    
    # 检查错误类型
    for retryable_type in retryable_error_types:
        if retryable_type in error_type_lower:
            return True
    
    # 检查错误消息中的关键词（网络/超时/权限/API错误/速率限制相关）
    retryable_keywords = [
        'timeout',
        'timed out',
        'connection',
        'network',
        'connection refused',
        'connection reset',
        'connection aborted',
        '502 bad gateway',
        '503',  # 503 Service Unavailable，服务不可用，应该重试
        '503 service unavailable',
        '504 gateway timeout',
        '524',  # 524 A timeout occurred (Cloudflare timeout error)，应该重试
        'error 524',  # 524错误（更明确的匹配）
        'cloudflare',  # Cloudflare错误（通常是524超时），应该重试
        'http 524',  # HTTP 524错误，应该重试
        'cloudflare timeout',  # Cloudflare超时错误，应该重试
        'api returned html',  # API返回HTML错误页面（通常是服务器错误），应该重试
        'retryable server timeout',  # 可重试的服务器超时错误
        '500',  # 500 Internal Server Error，服务器内部错误，应该重试
        'connection pool',
        'ssl handshake',
        'temporary failure',
        'request timed out',
        'connect timeout',
        'read timeout',
        '401',  # 401 Unauthorized，API key无效，可能是配置问题，允许重试
        'api key is invalid',  # API key无效错误消息
        'api key invalid',  # API key无效（另一种表述）
        'authentication',  # 认证相关错误
        'unauthorized',  # 未授权错误
        '403',  # 403 Forbidden，可能是API配置问题，允许重试
        '404',  # 404 Not Found，可能是模型服务暂时不可用或配置问题，允许重试
        '400',  # 400 Bad Request，可能是模型配置问题（如context length），允许重试
        '429',  # 429 Too Many Requests，速率限制，应该重试
        'too many requests',  # 429错误消息
        'rate limit',  # 速率限制
        '负载已饱和',  # 中文错误消息：负载已饱和（429错误）
        '请稍后再试',  # 中文错误消息：请稍后再试（429错误）
        'permission denied',
        'quota',  # 配额相关错误（配额不足通常是暂时性的，应该重试）
        'insufficient_user_quota',  # 用户配额不足
        'user quota is not enough',  # 用户配额不足（英文错误消息）
        'quota is not enough',  # 配额不足
        'insufficient quota',  # 配额不足
        'account balance',  # 账户余额相关错误（余额不足通常是暂时性的，应该重试）
        'balance is insufficient',  # 余额不足（英文错误消息）
        'account balance is insufficient',  # 账户余额不足
        'insufficient',  # 通用的"不足"关键词（配额、余额等）
        'does not exist',  # 模型不存在错误，可能是服务配置问题，允许重试
        'context length',  # context length相关错误，可能是模型配置问题，允许重试
        'maximum context',  # maximum context length错误，允许重试
        'reduce the length',  # 提示减少输入长度的错误，允许重试
        '暂无可用渠道',  # 中文错误消息中的关键词
        '无可用渠道',  # 中文错误消息：无可用渠道（503错误）
        'model_not_found',  # 模型未找到错误，可能是服务暂时不可用，允许重试
    ]
    
    # 先检查错误消息中的关键词（优先于错误类型检查，因为某些ValueError可能是网络错误）
    for keyword in retryable_keywords:
        if keyword in error_message_lower:
            return True
    
    # 不应该重试的错误类型（业务逻辑错误）
    # 注意：ValueError不在这个列表中，因为某些ValueError可能是网络/服务器错误（如524 HTML错误页面）
    non_retryable_error_types = [
        'jsondecodeerror',
        'keyerror',
        'typeerror',
        'attributeerror',
        'parsingerror',
        'validationerror',
    ]
    
    for non_retryable_type in non_retryable_error_types:
        if non_retryable_type in error_type_lower:
            return False
    
    # 默认不重试（可能是业务逻辑错误）
    return False


def get_unified_instruction_prompt(xml_content: str) -> str:
    """
    统一的指令生成Prompt，一次性生成Easy、Medium、Hard三条指令
    """
    prompt = f"""You are a professional diagram editing instruction generation expert. Your task is to generate **3 instructions of different difficulty levels** for the given diagram.

## Input Information

**XML Structure**:
```xml
{xml_content}
```

**Rendered Image**: Please examine the provided rendered image to understand the visual structure of the diagram.

---

## Atomic Operations Definition

The following are **14 predefined atomic operations**, each being the most basic, indivisible operation unit in diagram editing:

### Category 1: Node Attribute Modification (4 operations)
1. **Modify Node Color**: Change the fill color or border color of a node
   - Example: "Change the 'Start' node to red"

2. **Modify Node Shape**: Change the shape type of a node (rectangle, circle, diamond, etc.)
   - Example: "Change the start node to a circle"

3. **Modify Node Size**: Change the width or height of a node
   - Example: "Make the title box larger"

4. **Modify Node Text**: Change the text content displayed inside a node
   - Example: "Change the text of the first node to 'Begin'"

### Category 2: Node Structure Operations (3 operations)
5. **Delete Node**: Delete a node (without handling connections)
   - Example: "Delete the leftmost rectangle"

6. **Add Node**: Add a new node at a specified location
   - Example: "Add a new node at the start of the flowchart"

7. **Move Node**: Change the position of a node
   - Example: "Move the title box upward a bit"

### Category 3: Connection Line Attribute Modification (3 operations)
8. **Modify Connection Color**: Change the color of a connection line
   - Example: "Change all arrows to blue"

9. **Modify Connection Style**: Change the style of a connection line (solid, dashed, thickness, etc.)
   - Example: "Change the connection line to dashed"

10. **Modify Connection Arrow**: Change the arrow style of a connection line
    - Example: "Change the one-way arrow to a two-way arrow"

### Category 4: Connection Line Structure Operations (4 operations)
11. **Delete Connection**: Delete a connection line
    - Example: "Delete the connection line between the two nodes"

12. **Add Connection**: Add a connection line between two nodes
    - Example: "Add an arrow between the start node and end node"

13. **Redirect Connection**: Change the start or end point of a connection line
    - Example: "Redirect the arrow pointing to A to point to B instead"

14. **Update Connection Path**: Update the connection line path when nodes move
    - Example: "Adjust the connection lines so they don't overlap"

---

## Difficulty Requirements (Strictly Follow)

You need to generate 3 instructions of different difficulty levels, where difficulty is **completely determined by the number of atomic operations**:

### Easy Difficulty (1-2 atomic operations)
- **Requirement**: The instruction must contain **1-2** of the above 14 atomic operations
- **Example 1**: "Change the 'Start' node to red"
  - Atomic operation breakdown: [Modify Node Color]
  - Operation count: 1
- **Example 2**: "Delete the leftmost rectangle and delete all arrows connected to it"
  - Atomic operation breakdown: [Delete Node, Delete Connection]
  - Operation count: 2

### Medium Difficulty (3-4 atomic operations)
- **Requirement**: The instruction must contain **3-4** of the above 14 atomic operations
- **Example 1**: "Move the title box to the right a bit, change it to blue, and adjust the connection lines"
  - Atomic operation breakdown: [Move Node, Modify Node Color, Update Connection Path]
  - Operation count: 3
- **Example 2**: "Delete the start node, delete all arrows connected to it, redirect arrows that originally pointed to it to the second node, and adjust the connection lines"
  - Atomic operation breakdown: [Delete Node, Delete Connection, Redirect Connection, Update Connection Path]
  - Operation count: 4

### Hard Difficulty (5-7 atomic operations)
- **Requirement**: The instruction must contain **5-7** of the above 14 atomic operations
- **Example 1**: "Add a new node at the start of the flowchart, change it to a circle, set the color to red, increase the size, add an arrow between the new node and the next node, set the arrow to dashed, and adjust the connection line layout"
  - Atomic operation breakdown: [Add Node, Modify Node Shape, Modify Node Color, Modify Node Size, Add Connection, Modify Connection Style, Update Connection Path]
  - Operation count: 7
- **Example 2**: "Delete the middle node, delete all arrows connected to it, redirect arrows pointing to it to the left node, redirect arrows originating from it to the right node, and adjust all connection lines"
  - Atomic operation breakdown: [Delete Node, Delete Connection, Redirect Connection (input), Redirect Connection (output), Update Connection Path]
  - Operation count: 5

---

## Atomic Operation Combination Principles

When generating Medium and Hard difficulty instructions, please follow these principles:

1. **Operation Sequence Logic**: Operations should have a reasonable order
   - ✅ Correct: "Move the node to the right, then adjust the connection lines" (move first, then update)
   - ❌ Wrong: "Adjust the connection lines, then move the node to the right" (illogical order)

2. **Operation Target Relevance**: Multiple operations should target related elements
   - ✅ Correct: "Delete the start node and delete the arrows connected to it"
   - ❌ Avoid: "Change the topmost node to red and enlarge the bottommost node" (two unrelated nodes)

3. **Operation Type Diversity**: Combine different types of atomic operations for diversity
   - ✅ Encouraged: Attribute modification + Structure operation (e.g., "change color + delete node")
   - ❌ Avoid: Repetition of same type (e.g., "change first node to red + change second node to blue + change third node to green")

---

## Natural Language Instruction Requirements (Core Requirement)

**Most Important Principle**: Instructions must be based on the **rendered image** that users see, using natural language, not based on XML code or technical identifiers.

### ✅ Recommended Description Methods (Prioritized):

**Highest Priority**: Directly use the text content displayed on nodes

1. **Node Text Content Description (Most natural and accurate)**:
   - "Change the 'Start' node to red"
   - "Delete the 'Data Processing' node"
   - "Change 'User Login' to a circle"
   - "Add an arrow between 'Input' and 'Output'"

   **Why highest priority**: When users look at the diagram, the most intuitive thing is the text on the nodes

2. **Semantic Description** (when nodes don't have clear text but semantics are clear):
   - "Start node", "End node"
   - "Title text", "Description text"

3. **Position Description** (when nodes have no text or text is unclear):
   - "The topmost node", "The leftmost rectangle", "The middle circle"
   - "The first node", "The last node"

4. **Visual Feature Description** (as supplementary positioning):
   - "The largest rectangle", "The red node"
   - "The dashed arrow", "The thick connection line"

5. **Relative Position Description**:
   - "The arrow between 'Start' and 'End'"
   - "The line connecting 'Input' and 'Processing'"

### ❌ Strictly Prohibited Description Methods:

1. **Technical Identifiers** (Prohibited):
   - ❌ "Node with id 'node_1'"
   - ❌ "edge_5"
   - ❌ "value attribute is..."

2. **Coordinate Description** (Prohibited):
   - ❌ "Node at coordinates (200, 300)"
   - ❌ "Position at x=100, y=200"
   - ❌ "Move to (400, 500)"

3. **XML Attribute Reference** (Prohibited):
   - ❌ "Node with shape='rectangle'"
   - ❌ "style attribute contains..."

### Example Comparison:

| ❌ Unnatural (Strictly Prohibited) | ✅ Natural (Must Use) |
|-----------------------------------|----------------------|
| Change color of node with id 'node_1' to red | Change the 'Start' node to red (Highest priority: use node text) |
| Delete node at coordinates (200, 300) | Delete the 'Data Processing' node (Highest priority: use node text) |
| Change color of edge_5 to blue | Change the arrow connecting 'Input' and 'Output' to blue (use text + relative position) |
| Add node at (400, 500) | Add a new node between 'Start' and 'End' (use text + relative position) |
| Move node_2 to the right of node_3 | Move the 'Title' box to the right next to the 'Processing' node (use text + relative position) |

**Important Note**: If nodes have text labels, you must prioritize using text to refer to them; if nodes don't have text, use position, visual features, or other methods.

---

## Instruction Generation Requirements

1. **Analyze Diagram Structure**:
   - Carefully analyze the XML structure and rendered image, identify all modifiable elements (nodes, connections, text, etc.)
   - Ensure generated instructions target elements that actually exist in the diagram

2. **Generate 3 Instructions of Different Difficulty Levels**:
   - Easy instruction: Must contain 1-2 atomic operations
   - Medium instruction: Must contain 3-4 atomic operations
   - Hard instruction: Must contain 5-7 atomic operations

3. **Use Natural Language Description (Most Important)**:
   - **Must** use natural language methods like position description, visual features, semantic content to locate elements
   - **Strictly prohibit** using technical descriptions like id, coordinates, XML attributes
   - Instructions must be what users would naturally say when looking at the rendered image
   - Simulate real user scenario: users look at the image and describe modification needs in conversational language

4. **Instruction Diversity**:
   - The 3 instructions should involve different elements or different types of operations
   - Avoid the 3 instructions operating on exactly the same elements

---

## Output Format (Strict JSON)

Please output a JSON object containing 3 instructions in the following format:

```json
{{
  "instructions": [
    {{
      "difficulty": "Easy",
      "instruction": "Change the 'Start' node to red",
      "atomic_operations": [
        {{
          "operation_id": 1,
          "operation_type": "Modify Node Color",
          "description": "Change the color of the 'Start' node to red"
        }}
      ],
      "atomic_operation_count": 1,
      "target_elements": [
        {{
          "type": "node",
          "visual_description": "The 'Start' node"
        }}
      ],
      "executable": true
    }},
    {{
      "difficulty": "Medium",
      "instruction": "Delete the start node and delete all arrows connected to it",
      "atomic_operations": [
        {{
          "operation_id": 5,
          "operation_type": "Delete Node",
          "description": "Delete the node marked as start"
        }},
        {{
          "operation_id": 11,
          "operation_type": "Delete Connection",
          "description": "Delete all connection lines connected to the start node"
        }}
      ],
      "atomic_operation_count": 2,
      "target_elements": [
        {{
          "type": "node",
          "visual_description": "Start node"
        }},
        {{
          "type": "edge",
          "visual_description": "All connection lines connected to the start node"
        }}
      ],
      "executable": true
    }},
    {{
      "difficulty": "Hard",
      "instruction": "Delete the middle node, delete all arrows connected to it, redirect arrows pointing to it to the left node, redirect arrows originating from it to the right node, and adjust all connection lines",
      "atomic_operations": [
        {{
          "operation_id": 5,
          "operation_type": "Delete Node",
          "description": "Delete the node in the middle position"
        }},
        {{
          "operation_id": 11,
          "operation_type": "Delete Connection",
          "description": "Delete all connection lines connected to the middle node"
        }},
        {{
          "operation_id": 13,
          "operation_type": "Redirect Connection",
          "description": "Redirect connection lines that originally pointed to the middle node to the left node"
        }},
        {{
          "operation_id": 13,
          "operation_type": "Redirect Connection",
          "description": "Redirect connection lines that originally originated from the middle node to originate from the right node"
        }},
        {{
          "operation_id": 14,
          "operation_type": "Update Connection Path",
          "description": "Update all redirected connection line paths"
        }}
      ],
      "atomic_operation_count": 5,
      "target_elements": [
        {{
          "type": "node",
          "visual_description": "The middle node"
        }},
        {{
          "type": "node",
          "visual_description": "The left node"
        }},
        {{
          "type": "node",
          "visual_description": "The right node"
        }},
        {{
          "type": "edge",
          "visual_description": "All related connection lines"
        }}
      ],
      "executable": true
    }}
  ]
}}
```

---

## Important Reminders

1. **Strictly control atomic operation count**:
   - Easy = 1-2 operations
   - Medium = 3-4 operations
   - Hard = 5-7 operations

2. **Must use natural language (Most Important)**:
   - ✅ Use position descriptions: "topmost", "leftmost", "middle"
   - ✅ Use visual features: "red", "largest", "circular"
   - ✅ Use semantic descriptions: "Start node", "Title", "arrow connecting A and B"
   - ❌ Strictly prohibit using id, coordinates, XML attributes, and other technical descriptions

3. **Atomic operation ID correspondence**:
   - operation_id must correspond to the numbers (1-14) of the above 14 atomic operations

4. **Instruction executability**:
   - Target elements must actually exist in the XML
   - Operation sequence must be logical
   - Although using natural language descriptions, elements must be uniquely identifiable through visual features in the rendered image

5. **Output format**:
   - Must strictly follow JSON format
   - Do not include any explanatory text or Markdown code block markers
   - Output a directly parsable JSON object
   - Use visual_description field instead of identifier field to describe target elements

Please analyze the diagram and generate 3 modification instructions of different difficulty levels:
"""
    return prompt


def generate_instructions_for_sample(
    sample_dir: Path,
    llm_client: LLMClient,
    provider: str = 'custom',
    model: str = None,
    temperature: float = 0.7
) -> dict:
    """
    为单个样本生成3条不同难度的指令（Easy/Medium/Hard）
    使用统一Prompt一次性生成

    Args:
        sample_dir: 样本目录
        llm_client: LLM客户端
        provider: LLM provider
        model: 模型名称
        temperature: 温度参数

    Returns:
        生成的指令数据
    """
    logger.info(f"Generating instructions for {sample_dir.name}")

    # 读取Gemini XML和渲染图
    xml_path = sample_dir / "diagram.xml"
    rendered_path = sample_dir / "rendered.png"

    if not xml_path.exists():
        logger.error(f"XML not found: {xml_path}")
        return None

    if not rendered_path.exists():
        logger.error(f"Rendered image not found: {rendered_path}")
        return None

    # 读取XML内容
    with open(xml_path, 'r', encoding='utf-8') as f:
        xml_content = f.read()

    # 生成统一Prompt
    prompt = get_unified_instruction_prompt(xml_content)

    # 调用LLM生成指令（一次生成3条）
    start_time = time.time()
    try:
        # 使用JSON格式输出
        response_text, token_usage = llm_client._call_vision_api(
            prompt=prompt,
            image_input=rendered_path,
            provider=provider,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"}
        )

        processing_time = time.time() - start_time

        # 解析JSON响应
        try:
            response_data = json.loads(response_text)

            # 验证必需字段
            if 'instructions' not in response_data:
                logger.error("Response missing 'instructions' field")
                return None

            instructions = response_data['instructions']

            # 验证指令数量
            if len(instructions) != 3:
                logger.warning(f"Expected 3 instructions, got {len(instructions)}")

            # 验证每条指令
            valid_instructions = []
            for inst in instructions:
                if 'instruction' not in inst:
                    logger.warning("Instruction missing 'instruction' field, skipping")
                    continue

                # 验证原子操作数量
                difficulty = inst.get('difficulty', 'unknown')
                op_count = inst.get('atomic_operation_count', 0)

                if difficulty == 'Easy' and not (1 <= op_count <= 2):
                    logger.warning(f"Easy instruction has {op_count} operations (expected 1-2)")
                elif difficulty == 'Medium' and not (3 <= op_count <= 4):
                    logger.warning(f"Medium instruction has {op_count} operations (expected 3-4)")
                elif difficulty == 'Hard' and not (5 <= op_count <= 7):
                    logger.warning(f"Hard instruction has {op_count} operations (expected 5-7)")

                valid_instructions.append(inst)

            if not valid_instructions:
                logger.error("No valid instructions generated")
                return None

            # 添加元数据
            result = {
                "instructions": valid_instructions,
                "token_usage": token_usage,
                "processing_time_seconds": processing_time,
                "generated_at": datetime.now().isoformat(),
                "model": model or "default",
                "provider": provider
            }

            logger.info(f"✓ Generated {len(valid_instructions)} instructions in {processing_time:.2f}s")
            logger.info(f"Token usage: {token_usage.get('total_tokens', 0)} tokens")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return None

    except Exception as e:
        logger.error(f"Failed to generate instructions: {e}", exc_info=True)
        
        # 保存错误信息到 error.json
        error_info = {
            "status": "failed",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "timestamp": datetime.now().isoformat(),
            "retry_on_next_run": _should_retry_error(type(e).__name__, str(e))
        }
        
        error_path = sample_dir / "error.json"
        with open(error_path, 'w', encoding='utf-8') as f:
            json.dump(error_info, f, indent=2, ensure_ascii=False)
        logger.error(f"Saved error info to {error_path}")
        
        if error_info["retry_on_next_run"]:
            logger.info(f"Error is retryable (API request failure), will retry on next run")
        else:
            logger.info(f"Error is not retryable (likely a logic error: {type(e).__name__}), will not retry on next run")
        
        return None


def save_instructions(
    sample_dir: Path,
    instructions_data: dict
):
    """
    保存生成的指令到文件

    Args:
        sample_dir: 样本目录
        instructions_data: 指令数据
    """
    instructions_dir = sample_dir / "instructions"
    instructions_dir.mkdir(parents=True, exist_ok=True)

    # 为每条指令创建目录
    for idx, inst in enumerate(instructions_data['instructions'], 1):
        # 根据难度等级命名
        difficulty = inst.get('difficulty', 'unknown').lower()
        inst_id = f"inst_{difficulty}_{idx:03d}"
        inst_dir = instructions_dir / inst_id
        inst_dir.mkdir(parents=True, exist_ok=True)

        # 保存指令文本
        instruction_path = inst_dir / "instruction.txt"
        with open(instruction_path, 'w', encoding='utf-8') as f:
            f.write(inst['instruction'])

        # 保存指令元数据
        metadata = {
            "id": inst_id,
            "instruction": inst['instruction'],
            "difficulty": inst.get('difficulty', 'unknown'),
            "atomic_operations": inst.get('atomic_operations', []),
            "atomic_operation_count": inst.get('atomic_operation_count', 0),
            "target_elements": inst.get('target_elements', []),
            "executable": inst.get('executable', True),
            "generated_at": datetime.now().isoformat()
        }

        metadata_path = inst_dir / "instruction_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.debug(f"Saved instruction {inst_id} to {inst_dir}")

    # 保存成本统计到样本元数据
    metadata_path = sample_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
    else:
        metadata = {}

    if 'cost_estimation' not in metadata:
        metadata['cost_estimation'] = {}

    metadata['cost_estimation']['task2'] = {
        "instruction_generation": {
            "tokens": instructions_data['token_usage'],
            "processing_time_seconds": instructions_data['processing_time_seconds'],
            "instructions_count": len(instructions_data['instructions'])
        }
    }

    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def process_all_samples(
    source_dir: Path,
    provider: str = 'custom',
    model: str = None,
    temperature: float = 0.7,
    resume: bool = True,
    domain_filter: list = None,
    skip_render: bool = False
):
    """
    处理所有样本，生成修改指令

    Args:
        source_dir: task2_benchmark目录
        provider: LLM provider
        model: 模型名称（如果为None，默认使用gemini-3-pro-preview）
        temperature: 温度参数
        resume: 是否断点续传
        domain_filter: 领域过滤器（None表示处理所有领域，否则只处理指定的领域列表，如 ['ai', 'biology']）
        skip_render: 是否跳过渲染（HPC环境）
    """
    # 如果没有指定模型，默认使用gemini-3-pro-preview（用于ground truth生成）
    if model is None:
        model = "gemini-3-pro-preview"
        logger.info("No model specified, using default: gemini-3-pro-preview (for ground truth generation)")

    logger.info("=" * 80)
    logger.info("Task 2: Instruction Generation (Unified Prompt - 3 Difficulty Levels)")
    logger.info("=" * 80)
    logger.info(f"Source directory: {source_dir}")
    logger.info(f"Provider: {provider}, Model: {model}")
    logger.info(f"Temperature: {temperature}")
    logger.info(f"Resume: {resume}")
    logger.info(f"Skip render: {skip_render}")

    # 初始化LLM客户端
    llm_client = LLMClient()

    # 扫描所有领域（如果指定了领域，只处理指定的领域）
    if domain_filter:
        # 只处理指定的领域（直接使用目录名）
        domain_dirs = []
        for domain_name in domain_filter:
            # 直接使用用户传入的目录名
            domain_path = source_dir / domain_name
            if domain_path.exists() and domain_path.is_dir():
                domain_dirs.append(domain_path)
            else:
                logger.warning(f"Domain '{domain_name}' not found, skipping")
    else:
        # 处理所有领域
        domain_dirs = sorted([d for d in source_dir.glob('domain_*') if d.is_dir()])

    logger.info(f"\nFound {len(domain_dirs)} domains: {[d.name for d in domain_dirs]}")

    total_processed = 0
    total_instructions = 0

    for domain_dir in domain_dirs:
        domain = domain_dir.name
        logger.info("\n" + "=" * 80)
        logger.info(f"Processing domain: {domain}")
        logger.info("=" * 80)

        # 扫描所有样本
        sample_dirs = sorted([d for d in domain_dir.glob('sample_*') if d.is_dir()])
        logger.info(f"Found {len(sample_dirs)} samples")

        domain_processed = 0
        domain_instructions = 0

        for sample_dir in sample_dirs:
            # 检查是否已处理（断点续传）
            if resume:
                instructions_dir = sample_dir / "instructions"
                if instructions_dir.exists():
                    existing_inst = len(list(instructions_dir.glob('inst_*')))
                    if existing_inst >= 3:  # 应该有3条指令（Easy/Medium/Hard）
                        logger.info(f"Sample {sample_dir.name} already has {existing_inst} instructions, skipping")
                        domain_instructions += existing_inst
                        domain_processed += 1
                        continue
                
                # 检查是否有 error.json，判断是否应该重试
                error_path = sample_dir / "error.json"
                if error_path.exists():
                    try:
                        with open(error_path, 'r', encoding='utf-8') as f:
                            error_info = json.load(f)
                        error_type = error_info.get('error_type', '')
                        error_message = error_info.get('error_message', '')
                        retry_on_next_run = error_info.get('retry_on_next_run', False)
                        
                        # 判断是否是API请求失败的错误（应该重试）
                        if retry_on_next_run or _should_retry_error(error_type, error_message):
                            logger.info(f"Sample {sample_dir.name} has API error, will retry")
                            # 继续处理，不跳过
                        else:
                            # 不是API错误，跳过（可能是JSON解析错误等不应该重试的错误）
                            logger.debug(f"Sample {sample_dir.name} has non-retryable error, skipping")
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to read error.json for {sample_dir.name}: {e}, will retry")
                        # 继续处理，不跳过

            logger.info(f"\n--- Processing {sample_dir.name} ---")

            try:
                # 生成指令（一次生成3条）
                instructions_data = generate_instructions_for_sample(
                    sample_dir,
                    llm_client,
                    provider=provider,
                    model=model,
                    temperature=temperature
                )

                if instructions_data:
                    # 保存指令前，删除可能存在的 error.json（表示重试成功）
                    error_path = sample_dir / "error.json"
                    if error_path.exists():
                        error_path.unlink()
                        logger.info(f"Removed error.json for {sample_dir.name} (retry successful)")
                    
                    # 保存指令
                    save_instructions(sample_dir, instructions_data)
                    domain_processed += 1
                    domain_instructions += len(instructions_data['instructions'])
                    logger.info(f"✓ Generated {len(instructions_data['instructions'])} instructions")
                else:
                    logger.warning(f"Failed to generate instructions for {sample_dir.name}")

            except Exception as e:
                logger.error(f"Error processing {sample_dir.name}: {e}", exc_info=True)
                
                # 保存错误信息
                error_info = {
                    "status": "failed",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "retry_on_next_run": _should_retry_error(type(e).__name__, str(e))
                }
                
                error_path = sample_dir / "error.json"
                with open(error_path, 'w', encoding='utf-8') as f:
                    json.dump(error_info, f, indent=2, ensure_ascii=False)
                logger.error(f"Saved error info to {error_path}")
                
                if error_info["retry_on_next_run"]:
                    logger.info(f"Error is retryable (API request failure), will retry on next run")
                else:
                    logger.info(f"Error is not retryable (likely a logic error: {type(e).__name__}), will not retry on next run")

        total_processed += domain_processed
        total_instructions += domain_instructions

        logger.info(f"\nDomain {domain} summary: {domain_processed} samples, {domain_instructions} instructions")

    # 最终统计
    logger.info("\n" + "=" * 80)
    logger.info("Final Summary")
    logger.info("=" * 80)
    logger.info(f"Total samples processed: {total_processed}")
    logger.info(f"Total instructions generated: {total_instructions}")
    logger.info(f"Average instructions per sample: {total_instructions/total_processed:.1f}" if total_processed > 0 else "N/A")


def main():
    parser = argparse.ArgumentParser(
        description="Task 2: Generate editing instructions using unified prompt (atomic operations-based)"
    )

    parser.add_argument('command', choices=['generate-all'],
                        help='Command to execute')
    parser.add_argument('--source', type=Path, required=True,
                        help='Source directory (task2_benchmark)')
    parser.add_argument('--output', type=Path, required=True,
                        help='Output directory (task2_benchmark, same as source)')
    parser.add_argument('--provider', type=str, default='custom',
                        choices=['siliconflow', 'zhipu', 'custom', 'local'],
                        help='LLM provider')
    parser.add_argument('--model', type=str, default='gemini-3-pro-preview',
                        help='Model name (default: gemini-3-pro-preview for ground truth generation)')
    parser.add_argument('--temperature', type=float, default=0.7,
                        help='LLM temperature (default: 0.7 for more diversity)')
    parser.add_argument('--resume', action='store_true', default=True,
                        help='Resume from last checkpoint (default: True)')
    parser.add_argument('--no-resume', dest='resume', action='store_false',
                        help='Do not resume, reprocess all')
    parser.add_argument('--domain', type=str, nargs='+',
                        help='Specify domain(s) to process using directory names (e.g., --domain domain_ai domain_biology). If not specified, process all domains.')
    parser.add_argument('--skip-render', action='store_true',
                        help='Skip validation rendering (for HPC environments without draw.io)')

    args = parser.parse_args()

    # Validate
    if not args.source.exists():
        logger.error(f"Source directory not found: {args.source}")
        return 1

    # 确保output和source相同（指令直接保存在source目录下）
    if args.output != args.source:
        logger.warning(f"Output directory should be same as source, using source: {args.source}")

    if args.command == 'generate-all':
        try:
            process_all_samples(
                source_dir=args.source,
                provider=args.provider,
                model=args.model,
                temperature=args.temperature,
                resume=args.resume,
                domain_filter=args.domain,
                skip_render=args.skip_render
            )
            return 0
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
