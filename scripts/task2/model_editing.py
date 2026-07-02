#!/usr/bin/env python3
"""
Task 2: Model Editing
多个模型根据指令编辑XML，输出增量JSON格式以节省token
"""

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
# Note: override=False (default) means environment variables take precedence over .env file
# This allows command-line specified API keys/URLs to override .env values
from dotenv import load_dotenv
load_dotenv(project_root / '.env', override=False)

from src.llm.client import LLMClient
from src.renderer.drawio_renderer import DrawioRenderer
from src.core.models import DiagramXML
from configs.settings import get_settings

# Setup logging
log_dir = Path(__file__).parent.parent.parent / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'task2_model_editing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_model_dir_name(model_name: str) -> str:
    """
    从模型名提取目录名
    对于带斜杠的模型名（如 zai-org/GLM-4.7），只取最后一个斜杠后的部分
    例如: zai-org/GLM-4.7 -> GLM-4.7
          Pro/deepseek-ai/DeepSeek-V3.2 -> DeepSeek-V3.2
          gemini-3-flash-preview -> gemini-3-flash-preview
    """
    if '/' in model_name:
        return model_name.split('/')[-1]
    return model_name


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


def merge_incremental_changes(
    original_xml: str,
    incremental_changes: List[Dict[str, str]]
) -> str:
    """
    将增量修改合并到完整XML
    
    Args:
        original_xml: 原始完整XML
        incremental_changes: 增量修改列表，每个元素包含：
            {
                "original_fragment": "原始XML片段",
                "modified_fragment": "修改后的XML片段"
            }
            
    Returns:
        合并后的完整XML
    """
    result_xml = original_xml
    
    # 按顺序应用每个增量修改
    for change in incremental_changes:
        original_fragment = change.get("original_fragment", "")
        modified_fragment = change.get("modified_fragment", "")
        
        if not original_fragment:
            logger.warning("Empty original_fragment in change, skipping")
            continue
        
        # 在原始XML中查找并替换对应的片段
        if original_fragment in result_xml:
            result_xml = result_xml.replace(original_fragment, modified_fragment, 1)
            logger.debug(f"Applied change: replaced {len(original_fragment)} chars")
        else:
            # 如果找不到精确匹配，尝试模糊匹配（处理空白字符差异）
            # 移除空白字符进行匹配
            original_clean = re.sub(r'\s+', ' ', original_fragment.strip())
            pattern = re.escape(original_clean)
            pattern = pattern.replace(r'\ ', r'\s+')
            
            match = re.search(pattern, result_xml, re.DOTALL)
            if match:
                result_xml = result_xml[:match.start()] + modified_fragment + result_xml[match.end():]
                logger.debug(f"Applied change with fuzzy matching: replaced {len(original_fragment)} chars")
            else:
                logger.warning(f"Could not find fragment to replace: {original_fragment[:100]}...")
    
    return result_xml


def edit_xml_with_model(
    sample_dir: Path,
    instruction_dir: Path,
    model_name: str,
    llm_client: LLMClient,
    provider: str = 'custom',
    model: str = None,
    temperature: float = 0.0,
    stream: bool = False
) -> dict:
    """
    使用模型编辑XML（增量格式）
    
    Args:
        sample_dir: 样本目录
        instruction_dir: 指令目录
        model_name: 模型名称
        llm_client: LLM客户端
        provider: LLM provider
        model: 模型名称（如果与model_name不同）
        temperature: 温度参数
        
    Returns:
        编辑结果（包含token使用和时间）
    """
    logger.info(f"Editing XML with {model_name} for instruction {instruction_dir.name}")
    
    # 读取输入文件
    original_xml_path = sample_dir / "diagram.xml"
    instruction_path = instruction_dir / "instruction.txt"
    
    if not original_xml_path.exists():
        logger.error(f"Original XML not found: {original_xml_path}")
        return None
    
    if not instruction_path.exists():
        logger.error(f"Instruction not found: {instruction_path}")
        return None
    
    # 读取文件
    with open(original_xml_path, 'r', encoding='utf-8') as f:
        original_xml = f.read()
    
    with open(instruction_path, 'r', encoding='utf-8') as f:
        instruction = f.read().strip()
    
    # 调用LLM编辑XML（增量格式，只使用XML+指令，不使用图片）
    start_time = time.time()
    try:
        incremental_changes = llm_client.edit_xml_incremental(
            original_xml=original_xml,
            instruction=instruction,
            provider=provider,
            model=model or model_name,
            temperature=temperature,
            stream=stream
        )
        
        processing_time = time.time() - start_time
        
        # 使用模型名的最后部分作为目录名（处理带斜杠的情况）
        model_dir_name = get_model_dir_name(model_name)
        model_dir = instruction_dir / f"model_{model_dir_name}"
        model_dir.mkdir(parents=True, exist_ok=True)
        
        if not incremental_changes:
            # 即使返回空结果，也要保存错误信息
            logger.error(f"Model {model_name} returned empty incremental changes")
            
            # 判断错误类型：空结果可能是模型问题（不可重试）
            error_info = {
                "status": "failed",
                "error_type": "EmptyResult",
                "error_message": "Model returned empty incremental changes",
                "timestamp": datetime.now().isoformat(),
                "retry_on_next_run": False,  # 空结果通常是模型问题，不可重试
                "processing_time_seconds": processing_time
            }
            error_path = model_dir / "error.json"
            with open(error_path, 'w', encoding='utf-8') as f:
                json.dump(error_info, f, indent=2, ensure_ascii=False)
            logger.error(f"Saved error info to {error_path}")
            return None
        
        # 保存模型输出的增量JSON
        
        output_path = model_dir / "model_output.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(incremental_changes, f, indent=2, ensure_ascii=False)
        
        # 如果成功生成输出，删除之前可能存在的error.json（表示重试成功）
        error_path = model_dir / "error.json"
        if error_path.exists():
            error_path.unlink()
            logger.info(f"✓ Deleted previous error.json (retry succeeded)")
        
        # 合并增量修改到完整XML
        modified_xml = merge_incremental_changes(original_xml, incremental_changes)
        
        # 保存完整XML
        modified_xml_path = model_dir / "modified.xml"
        with open(modified_xml_path, 'w', encoding='utf-8') as f:
            f.write(modified_xml)
        
        # 渲染修改后的XML
        renderer = DrawioRenderer()
        modified_png_path = model_dir / "modified.png"
        
        # 尝试从metadata获取diagram_type，否则使用默认值
        diagram_type = 'flowchart'  # 默认值
        metadata_path = sample_dir / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    diagram_type = metadata.get('diagram_type', 'flowchart')
            except Exception as e:
                logger.debug(f"Failed to load metadata for diagram_type: {e}")
        
        diagram = DiagramXML(xml_content=modified_xml, diagram_type=diagram_type)
        render_success = renderer.render(diagram, modified_png_path)
        
        if not render_success:
            logger.warning(f"Failed to render modified XML for {model_name}")
        
        # 保存token使用和时间
        token_usage_data = {
            "tokens": getattr(llm_client, '_last_token_usage', {}),
            "processing_time_seconds": processing_time,
            "timestamp": datetime.now().isoformat()
        }
        token_usage_path = model_dir / "token_usage.json"
        with open(token_usage_path, 'w', encoding='utf-8') as f:
            json.dump(token_usage_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Model {model_name} editing completed in {processing_time:.2f}s")
        logger.info(f"Applied {len(incremental_changes)} incremental changes")
        
        return {
            "status": "success",
            "xml_path": str(modified_xml_path),
            "png_path": str(modified_png_path),
            "json_path": str(output_path),
            "change_count": len(incremental_changes),
            "processing_time_seconds": processing_time
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Model {model_name} failed: {e}", exc_info=True)
        
        # 保存错误信息（确保目录存在）
        # 使用模型名的最后部分作为目录名（处理带斜杠的情况）
        model_dir_name = get_model_dir_name(model_name)
        model_dir = instruction_dir / f"model_{model_dir_name}"
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # 判断错误是否应该重试
        error_type = type(e).__name__
        error_message = str(e)
        should_retry = _should_retry_error(error_type, error_message)
        
        # 检查是否是 JSON 截断错误（可重试）
        # 现在使用 DEFAULT_MAX_TOKENS（无限制），主要通过错误消息判断截断
        if "truncated" in error_message.lower() or "unterminated" in error_message.lower():
            # 如果错误消息中包含 "truncated" 或 "unterminated"，说明是截断错误，可以重试
            should_retry = True  # 截断错误可以重试
        
        error_info = {
            "status": "failed",
            "error_type": error_type,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat(),
            "retry_on_next_run": should_retry,  # API 错误或截断错误可重试，模型错误不可重试
            "processing_time_seconds": processing_time
        }
        
        # 如果有 token 使用信息，也保存
        if hasattr(llm_client, '_last_token_usage'):
            usage = getattr(llm_client, '_last_token_usage', {})
            if usage:
                error_info["token_usage"] = usage
        
        error_path = model_dir / "error.json"
        with open(error_path, 'w', encoding='utf-8') as f:
            json.dump(error_info, f, indent=2, ensure_ascii=False)
        logger.error(f"Saved error info to {error_path}")
        
        if should_retry:
            logger.info(f"Error is retryable (API request failure or truncated response), will retry on next run")
        else:
            logger.info(f"Error is not retryable (model issue), will skip on next run")
        
        return None


def process_all_samples(
    source_dir: Path,
    models: list,
    provider: str = 'custom',
    model_config: dict = None,
    temperature: float = 0.0,
    resume: bool = True,
    domain_filter: list = None,
    stream: bool = False
):
    """
    处理所有样本和指令，使用多个模型编辑XML
    
    Args:
        source_dir: task2_benchmark目录
        models: 模型列表
        provider: LLM provider
        model_config: 模型配置字典（key为模型名，value为模型配置）
        temperature: 温度参数
        resume: 是否断点续传
        domain_filter: 领域过滤器（None表示处理所有领域，否则只处理指定的领域列表，如 ['ai', 'biology']）
        stream: 是否使用流式API调用（默认False，非流式）
    """
    logger.info("=" * 80)
    logger.info("Task 2: Model Editing (Incremental JSON Format)")
    logger.info("=" * 80)
    logger.info(f"Source directory: {source_dir}")
    logger.info(f"Models: {models}")
    logger.info(f"Provider: {provider}, Temperature: {temperature}")
    logger.info(f"Resume: {resume}")
    logger.info(f"Stream: {stream}")
    
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
    
    # 预先统计总任务数（用于显示总体进度）
    total_tasks = 0
    domain_task_counts = {}
    for domain_dir in domain_dirs:
        domain = domain_dir.name
        domain_tasks = 0
        sample_dirs = sorted([d for d in domain_dir.glob('sample_*') if d.is_dir()])
        for sample_dir in sample_dirs:
            instructions_dir = sample_dir / "instructions"
            if instructions_dir.exists():
                instruction_dirs = sorted([d for d in instructions_dir.glob('inst_*') if d.is_dir()])
                domain_tasks += len(instruction_dirs) * len(models)
        domain_task_counts[domain] = domain_tasks
        total_tasks += domain_tasks
    
    logger.info(f"Total tasks to process: {total_tasks} (instruction-model pairs across all domains)")
    
    total_processed = 0
    total_success = 0
    total_failed = 0
    
    # 进度统计文件路径
    progress_file = source_dir / "task2_progress.json"
    
    # 领域统计字典
    domain_stats = {}
    
    def save_progress():
        """保存当前进度到文件"""
        progress_data = {
            "timestamp": datetime.now().isoformat(),
            "models": models,
            "total_processed": total_processed,
            "total_success": total_success,
            "total_failed": total_failed,
            "success_rate": total_success/(total_success+total_failed)*100 if (total_success+total_failed) > 0 else 0.0,
            "domains": domain_stats
        }
        try:
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save progress: {e}")
    
    for current_domain_index, domain_dir in enumerate(domain_dirs, 1):
        domain = domain_dir.name
        logger.info("\n" + "=" * 80)
        logger.info(f"[{current_domain_index}/{len(domain_dirs)}] Processing domain: {domain}")
        logger.info("=" * 80)
        
        # 扫描所有样本
        sample_dirs = sorted([d for d in domain_dir.glob('sample_*') if d.is_dir()])
        logger.info(f"Found {len(sample_dirs)} samples in domain {domain}")
        
        domain_processed = 0
        domain_success = 0
        domain_failed = 0
        
        # 统计该领域的总任务数
        domain_total_tasks = domain_task_counts.get(domain, 0)
        domain_current_task = 0
        
        for current_sample_index, sample_dir in enumerate(sample_dirs, 1):
            # 扫描所有指令
            instructions_dir = sample_dir / "instructions"
            if not instructions_dir.exists():
                logger.warning(f"[{current_domain_index}/{len(domain_dirs)}] [{current_sample_index}/{len(sample_dirs)}] No instructions found for {sample_dir.name}, skipping")
                continue
            
            instruction_dirs = sorted([d for d in instructions_dir.glob('inst_*') if d.is_dir()])
            logger.info(f"[{current_domain_index}/{len(domain_dirs)}] [{current_sample_index}/{len(sample_dirs)}] Sample {sample_dir.name}: {len(instruction_dirs)} instructions")
            
            for current_instruction_index, instruction_dir in enumerate(instruction_dirs, 1):
                instruction_id = instruction_dir.name
                logger.info(f"[{current_domain_index}/{len(domain_dirs)}] [{current_sample_index}/{len(sample_dirs)}] [{current_instruction_index}/{len(instruction_dirs)}] Processing instruction: {instruction_id}")
                
                # 对每个模型编辑XML
                for current_model_index, model_name in enumerate(models, 1):
                    # 使用模型名的最后部分作为目录名（处理带斜杠的情况）
                    model_dir_name = get_model_dir_name(model_name)
                    model_dir = instruction_dir / f"model_{model_dir_name}"
                    
                    # 更新任务进度
                    domain_current_task += 1
                    total_current_task = total_processed + domain_current_task
                    progress_info = f"[{current_domain_index}/{len(domain_dirs)}] [{current_sample_index}/{len(sample_dirs)}] [{current_instruction_index}/{len(instruction_dirs)}] [{current_model_index}/{len(models)}] [{domain_current_task}/{domain_total_tasks}] [{total_current_task}/{total_tasks}]"
                    
                    # 检查是否已处理（断点续传）
                    if resume:
                        output_path = model_dir / "model_output.json"
                        error_path = model_dir / "error.json"
                        
                        # 如果model_output.json存在，说明已成功处理，跳过
                        if output_path.exists():
                            logger.info(f"{progress_info} Model {model_name} already processed, skipping")
                            domain_success += 1
                            total_success += 1
                            domain_processed += 1
                            total_processed += 1
                            continue
                        
                        # 如果存在error.json，检查是否是应该重试的错误
                        if error_path.exists():
                            try:
                                with open(error_path, 'r', encoding='utf-8') as f:
                                    error_info = json.load(f)
                                error_type = error_info.get('error_type', '')
                                error_message = error_info.get('error_message', '')
                                retry_on_next_run = error_info.get('retry_on_next_run', False)
                                
                                # 判断是否是API请求失败的错误（应该重试）
                                if retry_on_next_run or _should_retry_error(error_type, error_message):
                                    logger.info(f"{progress_info} Sample {sample_dir.name} has API error for {model_name}, will retry")
                                    # 继续处理，不跳过
                                else:
                                    # 不是API错误，跳过（可能是JSON解析错误等不应该重试的错误）
                                    logger.debug(f"{progress_info} Sample {sample_dir.name} has non-retryable error for {model_name}, skipping")
                                    domain_failed += 1
                                    total_failed += 1
                                    domain_processed += 1
                                    total_processed += 1
                                    continue
                            except Exception as e:
                                logger.warning(f"{progress_info} Failed to read error.json for {model_name}: {e}, will retry")
                                # 继续处理，不跳过
                    
                    logger.info(f"{progress_info} Editing with {model_name}...")
                    
                    try:
                        # 获取模型配置
                        model_cfg = model_config.get(model_name, {}) if model_config else {}
                        model_provider = model_cfg.get('provider', provider)
                        model_model = model_cfg.get('model', model_name)  # 使用模型名作为默认值
                        model_temp = model_cfg.get('temperature', temperature)
                        
                        result = edit_xml_with_model(
                            sample_dir,
                            instruction_dir,
                            model_name,
                            llm_client,
                            provider=model_provider,
                            model=model_model,
                            temperature=model_temp,
                            stream=stream
                        )
                        
                        if result:
                            domain_success += 1
                            total_success += 1
                            domain_processed += 1
                            total_processed += 1
                            # 每成功处理一个指令就保存进度（实时更新）
                            save_progress()
                        else:
                            domain_failed += 1
                            total_failed += 1
                            domain_processed += 1
                            total_processed += 1
                            # 失败也保存进度
                            save_progress()
                            
                    except Exception as e:
                        logger.error(f"{progress_info} Error editing with {model_name}: {e}", exc_info=True)
                        domain_failed += 1
                        total_failed += 1
                        domain_processed += 1
                        total_processed += 1
        
        logger.info(f"\nDomain {domain} summary: {domain_processed} instruction-model pairs processed")
        logger.info(f"  Success: {domain_success}, Failed: {domain_failed}")
        
        # 更新领域统计
        domain_stats[domain] = {
            "processed": domain_processed,
            "success": domain_success,
            "failed": domain_failed,
            "success_rate": domain_success/(domain_success+domain_failed)*100 if (domain_success+domain_failed) > 0 else 0.0
        }
        
        # 保存进度（每个领域处理完后）
        save_progress()
    
    # 最终统计
    logger.info("\n" + "=" * 80)
    logger.info("Final Summary")
    logger.info("=" * 80)
    logger.info(f"Total instruction-model pairs processed: {total_processed}")
    logger.info(f"Success: {total_success}, Failed: {total_failed}")
    logger.info(f"Success rate: {total_success/(total_success+total_failed)*100:.1f}%" if (total_success+total_failed) > 0 else "N/A")
    
    # 保存最终进度
    save_progress()
    logger.info(f"Progress saved to: {progress_file}")
    
    # 自动导出dataset.json
    try:
        logger.info("\n" + "=" * 80)
        logger.info("Exporting dataset.json...")
        logger.info("=" * 80)
        # Import export function from the same directory
        import importlib.util
        export_script_path = Path(__file__).parent / "export_dataset_json.py"
        if export_script_path.exists():
            spec = importlib.util.spec_from_file_location("export_dataset_json", export_script_path)
            export_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(export_module)
            dataset_json_path = source_dir / "dataset.json"
            summary = export_module.export_dataset_json(source_dir, dataset_json_path)
            logger.info(f"✓ Successfully exported dataset.json: {dataset_json_path}")
            logger.info(f"  Total samples: {summary['total_samples']}")
            logger.info(f"  Total instructions: {summary['statistics']['total_instructions']}")
            logger.info(f"  Total model outputs: {summary['statistics']['total_model_outputs']}")
        else:
            logger.warning(f"Export script not found: {export_script_path}")
    except Exception as e:
        logger.warning(f"Failed to export dataset.json: {e}", exc_info=True)
        logger.warning("You can manually export it later using: python scripts/task2/export_dataset_json.py --source <path> --output <path>")


def main():
    parser = argparse.ArgumentParser(
        description="Task 2: Model Editing (outputs incremental JSON format to save tokens)"
    )
    
    parser.add_argument('command', choices=['process-all'],
                        help='Command to execute')
    parser.add_argument('--source', type=Path, required=True,
                        help='Source directory (task2_benchmark)')
    parser.add_argument('--output', type=Path, required=True,
                        help='Output directory (task2_benchmark, same as source)')
    parser.add_argument('--models', type=str, nargs='+', required=True,
                        help='List of models to evaluate')
    parser.add_argument('--provider', type=str, default='custom',
                        choices=['siliconflow', 'zhipu', 'custom', 'local'],
                        help='LLM provider')
    parser.add_argument('--temperature', type=float, default=0.0,
                        help='LLM temperature')
    parser.add_argument('--resume', action='store_true', default=True,
                        help='Resume from last checkpoint (default: True)')
    parser.add_argument('--no-resume', dest='resume', action='store_false',
                        help='Do not resume, reprocess all')
    parser.add_argument('--domain', type=str, nargs='+',
                        help='Specify domain(s) to process using directory names (e.g., --domain domain_ai domain_biology). If not specified, process all domains.')
    parser.add_argument('--stream', action='store_true',
                        help='Use streaming API calls (default: False, non-streaming)')
    
    args = parser.parse_args()
    
    # Validate
    if not args.source.exists():
        logger.error(f"Source directory not found: {args.source}")
        return 1
    
    # 确保output和source相同
    if args.output != args.source:
        logger.warning(f"Output directory should be same as source, using source: {args.source}")
    
    if args.command == 'process-all':
        try:
            process_all_samples(
                source_dir=args.source,
                models=args.models,
                provider=args.provider,
                temperature=args.temperature,
                resume=args.resume,
                domain_filter=args.domain,
                stream=args.stream
            )
            return 0
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
