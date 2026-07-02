#!/usr/bin/env python3
"""
Task 2: Generate Question Set for XDRFR Evaluation
Generate question set for each instruction (only decomposed questions, no common questions)
Questions will be verified based on XML code, not rendered images
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
vcgbench_root = Path(__file__).parent.parent.parent
env_path = vcgbench_root / '.env'
if env_path.exists():
    load_dotenv(env_path, override=True)

from src.llm.client import LLMClient

# Setup logging
log_dir = vcgbench_root / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'task2_question_set_generation.log'),
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


def decompose_instruction_to_questions(
    instruction: str,
    decomposition_model: str = "gemini-3-pro-preview",
    llm_client: LLMClient = None
) -> List[str]:
    """
    Decompose modification instruction into a series of Yes/No questions for XDRFR evaluation
    
    **Important**: Instructions use natural language (based on rendered images), but questions need to be converted to XML code-level verification.
    For example, if the instruction says "Change the 'Start' node to red", the question should be converted to "Has the fillColor attribute of the node with value 'Start' been changed to red?"
    
    Args:
        instruction: Modification instruction (natural language, based on rendered image)
        decomposition_model: Decomposition model
        llm_client: LLM client
    
    Returns:
        List[str]: List of decomposed questions (converted to XML code-level verification)
    """
    
    if llm_client is None:
        llm_client = LLMClient()
    
    prompt = f"""Decompose the following diagram modification instruction into a series of Yes/No questions. These questions will be used to verify whether the instruction has been correctly followed.
These questions will be verified based on XML code, not rendered images.

**Important Note**: The instruction uses natural language descriptions (based on rendered images), but questions need to be converted to XML code-level verification.
For example, if the instruction says "Change the 'Start' node to red", the question should be converted to "Has the fillColor attribute of the node with value 'Start' been changed to red?"

Instruction: "{instruction}"

**Requirements:**

**1. Target only the instruction itself**
- Carefully analyze the specific modification content mentioned in the instruction
- Decompose each specific requirement in the instruction into independent Yes/No questions
- Do not add content or checks not mentioned in the instruction

**2. Question format requirements**
- Each question should be answerable with "Yes" or "No"
- Questions should be verifiable by comparing the original XML code and the modified XML code
- Questions should be clear and unambiguous
- Questions should directly correspond to the specific modification requirements in the instruction
- Questions should focus on XML code-level modifications (attribute values, element existence, structural changes, etc.)
- **Key**: Convert natural language descriptions to XML code-level verification methods

**3. Natural language to XML mapping rules**
- **Node text description** (e.g., "Change the 'Start' node...") → Find nodes in XML where the `value` attribute contains that text
- **Position description** (e.g., "the topmost node") → Need to combine `mxGeometry` coordinate information to locate (smallest y coordinate)
- **Semantic description** (e.g., "start node") → Find nodes where the `value` attribute contains related semantics
- **Color description** (e.g., "change to red") → Verify `fillColor` or `strokeColor` in the `style` attribute (support color names or hex codes)
- **Shape description** (e.g., "change to circle") → Verify `shape` or related attributes in the `style` attribute
- **Connection description** (e.g., "arrow connecting 'Input' and 'Output'") → Find nodes where `source` and `target` attributes correspond (match by value attribute)

**4. Decomposition principles**
- If the instruction involves modifying an element's attribute (color, size, position), generate questions targeting that attribute
- If the instruction involves adding an element, generate questions targeting the element's existence and attributes
- If the instruction involves deleting an element, generate questions targeting whether the element has been deleted
- If the instruction involves multiple operations, generate corresponding questions for each operation

**Output Format (JSON):**
{{
    "decomposed_questions": [
        "Has the fillColor attribute of the node with value 'Start' been changed to red (#FF0000 or red)?",
        "Does the node with value 'Start' still exist in the modified XML code?"
    ]
}}

**Examples (Natural Language Instructions):**
- Instruction: "Change the 'Start' node to red"
  - Question 1: "Has the fillColor attribute of the node with value 'Start' been changed to red (#FF0000 or red)?"
  - Question 2: "Does the node with value 'Start' still exist in the modified XML code?"

- Instruction: "Delete the 'Data Processing' node"
  - Question 1: "Has the node with value 'Data Processing' been deleted from the modified XML code?"

- Instruction: "Add a new node between 'Start' and 'End' with label 'Process'"
  - Question 1: "Does a node with value 'Process' exist in the modified XML code?"
  - Question 2: "Is there a connection line where the source node has value 'Start' and the target node has value 'Process'?"
  - Question 3: "Is there a connection line where the source node has value 'Process' and the target node has value 'End'?"

- Instruction: "Move the topmost node to the right a bit"
  - Question 1: "Has the x coordinate of the node with the smallest y coordinate (topmost) in the original XML been increased in the modified XML?"
  - Question 2: "Does this node still exist in the modified XML code?"

- Instruction: "Change the arrow connecting 'Input' and 'Output' to blue"
  - Question 1: "Is there a connection line where the source node has value 'Input' and the target node has value 'Output'?"
  - Question 2: "Has the strokeColor attribute of this connection line been changed to blue (#0000FF or blue)?"

**Important Notes:**
- Only focus on content explicitly mentioned in the instruction, do not add additional checks
- Do not generate questions about "whether other elements remain unchanged" (unless the instruction explicitly requires it)
- Do not generate questions about "whether side effects occurred" (unless the instruction explicitly requires it)
- The number of questions should match the complexity of the instruction: simple instructions may have 1-2 questions, complex instructions may have 3-5 questions
- Questions should focus on XML code-level verification, not visual-level verification
- **Key**: Questions need to convert natural language descriptions to verifiable XML attribute or structure checks
"""
    
    try:
        # Call LLM to decompose instruction (use provider's client to directly call text API)
        provider_obj = llm_client._get_provider('custom')
        client = provider_obj.get_client()
        
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        response = client.chat.completions.create(
            model=decomposition_model,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        response_text = response.choices[0].message.content
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "model": decomposition_model,
            "provider": "custom"
        }
        
        # Parse JSON response (handle markdown code blocks if present)
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                else:
                    raise ValueError(f"Failed to parse JSON from response: {response_text[:500]}")
        
        decomposed_questions_raw = result.get("decomposed_questions", [])
        
        # Log the raw response to diagnose issues (use info level so it's visible)
        logger.info(f"LLM response JSON keys: {list(result.keys())}")
        logger.info(f"decomposed_questions_raw type: {type(decomposed_questions_raw)}, length: {len(decomposed_questions_raw) if isinstance(decomposed_questions_raw, list) else 'N/A'}")
        if isinstance(decomposed_questions_raw, list) and len(decomposed_questions_raw) > 0:
            logger.info(f"First question example: {decomposed_questions_raw[0]}")
        elif isinstance(decomposed_questions_raw, list) and len(decomposed_questions_raw) == 0:
            logger.warning(f"decomposed_questions_raw is an empty list!")
        else:
            logger.warning(f"decomposed_questions_raw is not a list: {type(decomposed_questions_raw)}, value: {decomposed_questions_raw}")
        
        # Handle new format (contains question_type and category) and old format (pure string list)
        decomposed_questions = []
        for q in decomposed_questions_raw:
            if isinstance(q, dict):
                # New format: extract question field
                question_text = q.get("question", "")
                if question_text:
                    decomposed_questions.append(question_text)
            elif isinstance(q, str):
                # Old format: use string directly
                decomposed_questions.append(q)
        
        logger.info(f"After parsing, decomposed_questions count: {len(decomposed_questions)}")
        
        # Validate question format (ensure ends with question mark)
        validated_questions = []
        for q in decomposed_questions:
            q = q.strip()
            if not q:
                continue
            if not q.endswith("?"):
                # Auto-fix: add question mark
                q = f"{q}?"
            validated_questions.append(q)
        
        # If no questions generated, log the raw response for debugging and add default question
        if not validated_questions:
            logger.warning(f"No questions generated from LLM response. Raw response: {response_text[:500]}")
            logger.warning(f"Parsed result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            logger.warning(f"decomposed_questions_raw: {decomposed_questions_raw}")
            default_question = f"Does the modified diagram follow the following instruction: {instruction}?"
            validated_questions = [default_question]
            logger.warning(f"Using default question as fallback")
        
        logger.info(f"Decomposed instruction into {len(validated_questions)} questions")
        
        return validated_questions
        
    except Exception as e:
        logger.error(f"Failed to decompose instruction: {e}", exc_info=True)
        # 重新抛出异常，让调用者（process_all_instructions）处理错误信息保存
        raise


def process_all_instructions(
    source_dir: Path,
    decomposition_model: str = "gemini-3-pro-preview",
    resume: bool = True,
    domain_filter: list = None
):
    """
    处理所有指令，生成问题集合
    
    参数:
        source_dir: task2_benchmark 目录
        decomposition_model: 拆解模型
        resume: 是否断点续传
        domain_filter: 领域过滤器（None表示处理所有领域，否则只处理指定的领域列表，如 ['ai', 'biology']）
    """
    
    logger.info("=" * 80)
    logger.info("Task 2: Generate Question Set for XDRFR")
    logger.info("=" * 80)
    logger.info(f"Source directory: {source_dir}")
    logger.info(f"Decomposition model: {decomposition_model}")
    logger.info(f"Resume: {resume}")
    
    # 初始化 LLM 客户端
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
            # 扫描所有指令
            instructions_dir = sample_dir / "instructions"
            if not instructions_dir.exists():
                logger.warning(f"No instructions directory in {sample_dir}, skipping")
                continue
            
            instruction_dirs = sorted([d for d in instructions_dir.glob('inst_*') if d.is_dir()])
            logger.info(f"Sample {sample_dir.name}: {len(instruction_dirs)} instructions")
            
            for inst_dir in instruction_dirs:
                inst_id = inst_dir.name
                
                # 检查是否已处理（断点续传）
                question_set_path = inst_dir / "question_set.json"
                if resume and question_set_path.exists():
                    try:
                        with open(question_set_path, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                        if existing_data.get("decomposed_questions"):
                            logger.info(f"Instruction {inst_id} already has question set, skipping")
                            domain_instructions += 1
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to read existing question set: {e}")
                
                # 检查是否有 error.json，判断是否应该重试
                error_path = inst_dir / "error.json"
                if error_path.exists():
                    try:
                        with open(error_path, 'r', encoding='utf-8') as f:
                            error_info = json.load(f)
                        error_type = error_info.get('error_type', '')
                        error_message = error_info.get('error_message', '')
                        retry_on_next_run = error_info.get('retry_on_next_run', False)
                        
                        # 判断是否是API请求失败的错误（应该重试）
                        if retry_on_next_run or _should_retry_error(error_type, error_message):
                            logger.info(f"Instruction {inst_id} has API error, will retry")
                            # 继续处理，不跳过
                        else:
                            # 不是API错误，跳过（可能是JSON解析错误等不应该重试的错误）
                            logger.debug(f"Instruction {inst_id} has non-retryable error, skipping")
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to read error.json for {inst_id}: {e}, will retry")
                        # 继续处理，不跳过
                
                # 读取指令文本
                instruction_path = inst_dir / "instruction.txt"
                if not instruction_path.exists():
                    logger.warning(f"Instruction file not found: {instruction_path}, skipping")
                    continue
                
                with open(instruction_path, 'r', encoding='utf-8') as f:
                    instruction_text = f.read().strip()
                
                logger.info(f"\n--- Processing instruction {inst_id} ---")
                logger.info(f"Instruction: {instruction_text[:100]}...")
                
                try:
                    # 拆解指令为问题
                    decomposed_questions = decompose_instruction_to_questions(
                        instruction=instruction_text,
                        decomposition_model=decomposition_model,
                        llm_client=llm_client
                    )
                    
                    if decomposed_questions:
                        # 保存问题集合前，删除可能存在的 error.json（表示重试成功）
                        if error_path.exists():
                            error_path.unlink()
                            logger.info(f"Removed error.json for {inst_id} (retry successful)")
                        
                        # 保存问题集合（只包含拆解问题，不再包含共用问题）
                        question_set_data = {
                            "instruction_id": inst_id,
                            "instruction": instruction_text,
                            "decomposed_questions": decomposed_questions,
                            "total_questions": len(decomposed_questions),
                            "generated_at": datetime.now().isoformat(),
                            "decomposition_model": decomposition_model
                        }
                        
                        with open(question_set_path, 'w', encoding='utf-8') as f:
                            json.dump(question_set_data, f, indent=2, ensure_ascii=False)
                        
                        domain_instructions += 1
                        logger.info(f"✓ Generated question set for {inst_id}: {len(decomposed_questions)} decomposed questions")
                    else:
                        logger.warning(f"Failed to decompose instruction {inst_id}")
                        
                except Exception as e:
                    logger.error(f"Error processing instruction {inst_id}: {e}", exc_info=True)
                    
                    # 保存错误信息
                    error_info = {
                        "status": "failed",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "timestamp": datetime.now().isoformat(),
                        "retry_on_next_run": _should_retry_error(type(e).__name__, str(e))
                    }
                    
                    with open(error_path, 'w', encoding='utf-8') as f:
                        json.dump(error_info, f, indent=2, ensure_ascii=False)
                    logger.error(f"Saved error info to {error_path}")
                    
                    if error_info["retry_on_next_run"]:
                        logger.info(f"Error is retryable (API request failure), will retry on next run")
                    else:
                        logger.info(f"Error is not retryable (likely a logic error: {type(e).__name__}), will not retry on next run")
            
            domain_processed += 1
        
        total_processed += domain_processed
        total_instructions += domain_instructions
        
        logger.info(f"\nDomain {domain} summary: {domain_processed} samples, {domain_instructions} instructions processed")
    
    # 最终统计
    logger.info("\n" + "=" * 80)
    logger.info("Final Summary")
    logger.info("=" * 80)
    logger.info(f"Total samples processed: {total_processed}")
    logger.info(f"Total instructions processed: {total_instructions}")
    logger.info(f"Average decomposed questions per instruction: {total_instructions/total_processed:.1f}" if total_processed > 0 else "N/A")
    
    logger.info("\nNote: Question sets saved to individual question_set.json files.")
    logger.info("Run export_dataset_json to update dataset.json with question sets.")


def main():
    parser = argparse.ArgumentParser(
        description="Task 2: Generate question set for XDRFR evaluation (decomposed questions only)"
    )
    
    parser.add_argument('command', choices=['generate-all'],
                        help='Command to execute')
    parser.add_argument('--source', type=Path, required=True,
                        help='Source directory (task2_benchmark)')
    parser.add_argument('--model', type=str, default='gemini-3-pro-preview',
                        help='Instruction decomposition model (default: gemini-3-pro-preview)')
    parser.add_argument('--resume', action='store_true', default=True,
                        help='Resume from last checkpoint (default: True)')
    parser.add_argument('--no-resume', dest='resume', action='store_false',
                        help='Do not resume, reprocess all')
    parser.add_argument('--domain', type=str, nargs='+',
                        help='Specify domain(s) to process using directory names (e.g., --domain domain_ai domain_biology). If not specified, process all domains.')
    
    args = parser.parse_args()
    
    # Validate
    if not args.source.exists():
        logger.error(f"Source directory not found: {args.source}")
        return 1
    
    if args.command == 'generate-all':
        try:
            process_all_instructions(
                source_dir=args.source,
                decomposition_model=args.model,
                resume=args.resume,
                domain_filter=args.domain
            )
            return 0
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
