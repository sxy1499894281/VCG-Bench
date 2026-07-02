#!/usr/bin/env python3
"""
Task 1: Generate XML from images (multiple models)
基于 workflow2_images.py 扩展，支持多模型和领域扫描
"""

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
import time

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load .env file before importing other modules
# Note: override=False (default) means environment variables take precedence over .env file
# This allows command-line specified API keys/URLs to override .env values
from dotenv import load_dotenv
load_dotenv(project_root / '.env', override=False)

from src.core.models import ProcessingResult, ImageInfo
from src.processors import DescriptionGenerator, DiagramGenerator
from src.llm.client import LLMClient
from src.renderer import DrawioRenderer
from src.utils import find_images
from src.utils.file_ops import get_file_hash
from configs.settings import get_settings

# Setup logging
log_dir = Path(__file__).parent.parent.parent / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'task1_generate.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_model_dir_name(model_name: str) -> str:
    """
    从模型名提取目录名
    对于带斜杠的模型名（如 zai-org/GLM-4.6V），只取最后一个斜杠后的部分
    例如: zai-org/GLM-4.6V -> GLM-4.6V
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
        True: 应该重试（网络/超时/权限错误/API响应格式问题等）
        False: 不应该重试（业务逻辑错误，如JSON解析错误）
    """
    error_type_lower = error_type.lower()
    error_message_lower = error_message.lower()
    
    # 特殊处理：某些AttributeError是由于API响应格式问题导致的，应该重试
    # 例如：'str' object has no attribute 'choices' - 这是API返回字符串而不是对象的问题
    if error_type_lower == 'attributeerror':
        api_response_format_issues = [
            "'str' object has no attribute 'choices'",
            "str' object has no attribute 'choices'",
            "has no attribute 'choices'",
            "has no attribute 'usage'",
            "object has no attribute 'choices'",
            "object has no attribute 'usage'",
            "response.choices",
            "response.usage",
        ]
        for issue in api_response_format_issues:
            if issue in error_message:
                # API响应格式问题，现在代码已修复，应该重试
                return True
    
    # 应该重试的异常类型（网络/超时/连接错误/权限错误/API错误）
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
        'permissiondeniederror',  # 权限错误（如403），可能是API配置问题，允许重试
        'notfounderror',  # 404错误，可能是模型服务暂时不可用或配置问题，允许重试
        'badrequesterror',  # 400错误，可能是模型配置问题（如context length），允许重试
    ]
    
    # 检查错误类型
    for retryable_type in retryable_error_types:
        if retryable_type in error_type_lower:
            return True
    
    # 检查错误消息中的关键词（网络/超时/权限/API错误相关）
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
        'insufficient_user_quota',  # 用户配额不足（错误代码）
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
        'parsingerror',
        'validationerror',
    ]
    # 注意：AttributeError 现在需要特殊处理，不在这里直接排除
    
    for non_retryable_type in non_retryable_error_types:
        if non_retryable_type in error_type_lower:
            return False
    
    # 对于 AttributeError，如果不在特殊处理列表中，默认不重试
    if error_type_lower == 'attributeerror':
        return False
    
    # 默认不重试（可能是业务逻辑错误）
    return False


def is_gemini_model(model_name: str) -> bool:
    """
    检查模型名是否是 Gemini 模型（支持 'gemini' 和 'gemini-3-pro-preview' 等）
    
    Args:
        model_name: 模型名称
    
    Returns:
        bool: 如果是 Gemini 模型返回 True
    """
    if not model_name:
        return False
    model_name_lower = model_name.lower()
    return 'gemini' in model_name_lower


def build_image_hash_to_sample_mapping(domain_output_dir: Path) -> dict:
    """
    构建图片哈希值到 sample_id 的映射（用于防止追加图片时挤占已有 sample_id）
    
    优先从 metadata.json 读取哈希值，如果不存在则计算并保存。
    
    Args:
        domain_output_dir: 领域输出目录（如 task1_benchmark/domain_ai）
    
    Returns:
        字典：{image_hash: sample_id}
    """
    mapping = {}
    
    if not domain_output_dir.exists():
        return mapping
    
    # 扫描所有已有的 sample_dir
    for sample_dir in sorted(domain_output_dir.glob('sample_*')):
        if not sample_dir.is_dir():
            continue
        
        original_path = sample_dir / "original.png"
        if not original_path.exists():
            continue
        
        sample_id = sample_dir.name
        image_hash = None
        
        # 优先从 metadata.json 读取哈希值（避免重复计算）
        metadata_path = sample_dir / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    image_hash = metadata.get('image_hash_md5')
                    if image_hash:
                        mapping[image_hash] = sample_id
                        logger.debug(f"Mapped hash {image_hash[:8]}... to {sample_id} (from metadata.json)")
                        continue
            except Exception as e:
                logger.debug(f"Failed to read metadata.json for {sample_id}: {e}")
        
        # 如果 metadata.json 中没有哈希值，计算并保存
        try:
            image_hash = get_file_hash(original_path, algorithm='md5')
            mapping[image_hash] = sample_id
            logger.debug(f"Calculated hash {image_hash[:8]}... for {sample_id}")
            
            # 保存哈希值到 metadata.json（如果文件存在则更新，不存在则创建）
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                except:
                    metadata = {}
                metadata['image_hash_md5'] = image_hash
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
            else:
                # 如果 metadata.json 不存在，创建一个只包含哈希值的文件
                metadata = {'image_hash_md5': image_hash}
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to hash {original_path}: {e}")
    
    logger.info(f"Built image hash mapping: {len(mapping)} samples")
    return mapping


def find_next_available_sample_id(domain_output_dir: Path, start_from: int = 1) -> str:
    """
    找到下一个可用的 sample_id（用于新图片）
    
    Args:
        domain_output_dir: 领域输出目录
        start_from: 从哪个编号开始查找（默认从1开始）
    
    Returns:
        sample_id 字符串（如 "sample_0011"）
    """
    # 找到所有已有的 sample_id
    existing_ids = set()
    if domain_output_dir.exists():
        for sample_dir in domain_output_dir.glob('sample_*'):
            if sample_dir.is_dir():
                existing_ids.add(sample_dir.name)
    
    # 从 start_from 开始查找第一个可用的编号
    idx = start_from
    while True:
        candidate_id = f"sample_{idx:04d}"
        if candidate_id not in existing_ids:
            return candidate_id
        idx += 1


def calculate_metadata(diagram_xml: str) -> dict:
    """
    计算样本元数据（元素数、token数等）
    
    Args:
        diagram_xml: XML内容
        
    Returns:
        元数据字典
    """
    try:
        import xml.etree.ElementTree as ET
        
        # 解析XML
        root = ET.fromstring(diagram_xml)
        
        # 计算元素数
        all_elements = list(root.iter())
        element_count = len(all_elements)
        
        # 计算节点数（mxCell with vertex=1）
        nodes = root.findall(".//mxCell[@vertex='1']")
        node_count = len(nodes)
        
        # 计算边数（mxCell with edge=1）
        edges = root.findall(".//mxCell[@edge='1']")
        edge_count = len(edges)
        
        # 计算XML token数（简单估算：按空格和标签分割）
        xml_tokens = len(diagram_xml.split())
        
        return {
            "element_count": element_count,
            "node_count": node_count,
            "edge_count": edge_count,
            "xml_token_count": xml_tokens,
            "calculated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.warning(f"Failed to calculate metadata: {e}")
        return {
            "element_count": 0,
            "node_count": 0,
            "edge_count": 0,
            "xml_token_count": 0,
            "error": str(e),
            "calculated_at": datetime.now().isoformat()
        }


def process_single_image(
    image_path: Path,
    sample_dir: Path,
    models: list,
    llm_client: LLMClient = None,
    desc_generators: dict = None,
    diagram_generators: dict = None,
    renderer: DrawioRenderer = None
) -> dict:
    """
    处理单张图片，运行多个模型（每个模型独立生成描述）
    
    Args:
        image_path: 图片路径
        sample_dir: 样本输出目录
        models: 模型列表
        llm_client: LLM客户端
        desc_generators: 字典，key为模型名，value为DescriptionGenerator
        diagram_generators: 字典，key为模型名，value为DiagramGenerator
        renderer: 渲染器
        
    Returns:
        处理结果统计
    """
    logger.info(f"Processing image: {image_path.name}")
    
    # 确保sample_dir存在
    sample_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制原始图片
    original_path = sample_dir / "original.png"
    if not original_path.exists():
        shutil.copy2(image_path, original_path)
        logger.debug(f"Copied original image to {original_path}")
        
        # 如果是新图片，立即计算并保存哈希值到 metadata.json（用于后续匹配）
        try:
            image_hash = get_file_hash(original_path, algorithm='md5')
            metadata_path = sample_dir / "metadata.json"
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                except:
                    metadata = {}
            else:
                metadata = {}
            metadata['image_hash_md5'] = image_hash
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved image hash to metadata.json: {image_hash[:8]}...")
        except Exception as e:
            logger.debug(f"Failed to save image hash to metadata.json: {e}")
    
    # 创建ImageInfo
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            width, height = img.size
            img_format = img.format
    except Exception as e:
        logger.warning(f"Failed to read image {image_path}: {e}")
        width, height, img_format = None, None, None
    
    image_info = ImageInfo(
        path=image_path,
        filename=image_path.name,
        width=width,
        height=height,
        format=img_format,
        size_bytes=image_path.stat().st_size
    )
    
    # 先使用Gemini生成描述（所有模型复用）
    shared_description = None
    shared_desc_token_usage = {}
    shared_desc_time = 0.0
    
    # 检查是否已有Gemini的描述（使用 gemini-3-pro-preview 目录）
    desc_model_name = "gemini-3-pro-preview"
    gemini_desc_path = sample_dir / f"model_{desc_model_name}" / "llm_description.txt"
    if gemini_desc_path.exists():
        logger.info("Loading existing Gemini description...")
        try:
            with open(gemini_desc_path, 'r', encoding='utf-8') as f:
                desc_text = f.read()
            # 尝试解析为JSON并重建StructuredDescription
            try:
                desc_dict = json.loads(desc_text)
                from src.core.models import StructuredDescription
                from src.processors import DescriptionGenerator
                
                # Use DescriptionGenerator to parse JSON properly
                desc_gen = DescriptionGenerator()
                shared_description = desc_gen._parse_json_to_structured_description(
                    desc_dict,
                    image_info,
                    {}  # No usage stats for loaded description
                )
                logger.info("✓ Loaded existing Gemini description (JSON parsed)")
            except Exception as parse_error:
                # 如果解析失败，尝试直接创建StructuredDescription
                try:
                    from src.core.models import StructuredDescription
                    desc_dict = json.loads(desc_text)
                    # Try to create from dict directly
                    shared_description = StructuredDescription(**desc_dict)
                    logger.info("✓ Loaded existing Gemini description (direct from dict)")
                except:
                    # 如果都失败，创建一个简单的描述对象
                    from src.core.models import StructuredDescription
                    shared_description = StructuredDescription(
                        diagram_type="unknown",
                        title=image_info.figure_label or image_info.filename,
                        summary=desc_text[:500] if len(desc_text) > 500 else desc_text,
                        metadata={"from_file": True, "parse_error": str(parse_error)}
                    )
                    logger.warning(f"✓ Loaded existing Gemini description (as text, parse error: {parse_error})")
        except Exception as e:
            logger.warning(f"Failed to load existing description: {e}")
    
    # 如果没有描述，使用Gemini生成（总是使用 gemini-3-pro-preview，不管用户传入什么模型）
    if shared_description is None:
        logger.info("Generating description with Gemini (gemini-3-pro-preview, shared for all models)...")
        try:
            # 创建专门的描述生成器，使用 gemini-3-pro-preview
            # 如果没有传入 llm_client，创建一个新的
            if llm_client is None:
                from src.llm.client import LLMClient
                llm_client = LLMClient()
            
            from src.processors import DescriptionGenerator
            desc_gen = DescriptionGenerator(
                llm_client=llm_client,
                provider='custom',  # 使用默认 provider
                model='gemini-3-pro-preview',  # 固定使用 gemini-3-pro-preview 生成描述
                temperature=0.7  # 使用默认温度
            )
            
            desc_start_time = time.time()
            desc, desc_tokens = desc_gen.generate_description(
                image_info,
                use_llm=True
            )
            shared_desc_time = time.time() - desc_start_time
            shared_description = desc
            shared_desc_token_usage = desc_tokens or {}
            logger.info(f"✓ Gemini description generated (time: {shared_desc_time:.2f}s, tokens: {shared_desc_token_usage.get('total_tokens', 0)})")
            
            # 保存描述到 gemini-3-pro-preview 目录
            desc_model_name = "gemini-3-pro-preview"
            desc_model_dir_name = get_model_dir_name(desc_model_name)
            desc_model_dir = sample_dir / f"model_{desc_model_dir_name}"
            desc_model_dir.mkdir(parents=True, exist_ok=True)
            if shared_description:
                # Prefer raw JSON from metadata (complete structured description)
                if isinstance(shared_description.metadata, dict) and 'raw_json' in shared_description.metadata:
                    desc_text = json.dumps(shared_description.metadata['raw_json'], indent=2, ensure_ascii=False)
                elif hasattr(shared_description, 'to_json'):
                    desc_text = shared_description.to_json()
                elif hasattr(shared_description, 'to_dict'):
                    desc_text = json.dumps(shared_description.to_dict(), indent=2, ensure_ascii=False)
                else:
                    desc_text = str(shared_description)
                
                desc_path = desc_model_dir / "llm_description.txt"
                with open(desc_path, 'w', encoding='utf-8') as f:
                    f.write(desc_text)
                logger.debug(f"Saved Gemini description to {desc_path}")
        except Exception as e:
            shared_desc_time = time.time() - desc_start_time if 'desc_start_time' in locals() else 0.0
            logger.error(f"Failed to generate Gemini description: {e}", exc_info=True)
            shared_description = None
            shared_desc_token_usage = {}
    
    if shared_description is None:
        logger.warning("No description available (Gemini failed or not in models), proceeding without description")
    
    # 对每个模型生成XML（复用Gemini的描述）
    results = {}
    metadata_stats = []
    
    for model_name in models:
        logger.info(f"\n--- Processing with {model_name} ---")
        # 使用模型名的最后部分作为目录名（处理带斜杠的情况）
        model_dir_name = get_model_dir_name(model_name)
        model_dir = sample_dir / f"model_{model_dir_name}"
        model_dir.mkdir(parents=True, exist_ok=True)
        
        model_result = {
            "status": "pending",
            "model": model_name,
            "timestamp": datetime.now().isoformat()
        }
        
        # 记录模型处理开始时间（在try之前，确保except中能访问）
        model_start_time = time.time()
        
        # 初始化变量（在try之前，确保except中能访问）
        description = shared_description  # 所有模型复用Gemini的描述
        desc_token_usage = {}  # 描述token只统计Gemini的
        desc_time = 0.0  # 描述时间只统计Gemini的
        xml_token_usage = {}
        xml_time = 0.0
        
        try:
            # 如果是Gemini，使用已生成的描述和token统计
            if is_gemini_model(model_name):
                desc_token_usage = shared_desc_token_usage
                desc_time = shared_desc_time
                # 保存描述到Gemini目录（如果还没保存）
                if description and not (model_dir / "llm_description.txt").exists():
                    # Prefer raw JSON from metadata (complete structured description)
                    if isinstance(description.metadata, dict) and 'raw_json' in description.metadata:
                        desc_text = json.dumps(description.metadata['raw_json'], indent=2, ensure_ascii=False)
                    elif hasattr(description, 'to_json'):
                        desc_text = description.to_json()
                    elif hasattr(description, 'to_dict'):
                        desc_text = json.dumps(description.to_dict(), indent=2, ensure_ascii=False)
                    else:
                        desc_text = str(description)
                    
                    desc_path = model_dir / "llm_description.txt"
                    with open(desc_path, 'w', encoding='utf-8') as f:
                        f.write(desc_text)
                    logger.debug(f"Saved description to {desc_path}")
            else:
                # 其他模型复用Gemini的描述，但不统计token和时间
                # 描述已经设置为shared_description，这里只需要保存一份副本（可选）
                if description and not (model_dir / "llm_description.txt").exists():
                    # 可选：为其他模型也保存一份描述副本，标记为复用
                    # Prefer raw JSON from metadata (complete structured description)
                    if isinstance(description.metadata, dict) and 'raw_json' in description.metadata:
                        desc_dict = description.metadata['raw_json'].copy()
                        desc_dict['metadata'] = desc_dict.get('metadata', {})
                        if not isinstance(desc_dict['metadata'], dict):
                            desc_dict['metadata'] = {}
                        desc_dict['metadata']['reused_from'] = 'gemini'
                        desc_text = json.dumps(desc_dict, indent=2, ensure_ascii=False)
                    elif hasattr(description, 'to_dict'):
                        desc_dict = description.to_dict()
                        desc_dict['metadata'] = desc_dict.get('metadata', {})
                        desc_dict['metadata']['reused_from'] = 'gemini'
                        desc_text = json.dumps(desc_dict, indent=2, ensure_ascii=False)
                    elif hasattr(description, 'to_json'):
                        desc_text = description.to_json()
                    else:
                        desc_text = str(description)
                    
                    desc_path = model_dir / "llm_description.txt"
                    with open(desc_path, 'w', encoding='utf-8') as f:
                        f.write(desc_text)
                    logger.debug(f"Saved reused description to {desc_path}")
            
            # 2. 生成XML
            if model_name not in diagram_generators:
                logger.warning(f"No diagram generator for {model_name}, skipping")
                model_result["status"] = "skipped"
                model_result["error"] = "No diagram generator configured"
                results[model_name] = model_result
                continue
            
            logger.info(f"Generating XML with {model_name}...")
            xml_start_time = time.time()
            diagram_gen = diagram_generators[model_name]
            diagram, xml_tokens = diagram_gen.generate_diagram(
                image_info,
                description=description,
                use_llm=True
            )
            xml_time = time.time() - xml_start_time
            xml_token_usage = xml_tokens or {}
            
            # 保存XML
            xml_path = model_dir / "diagram.xml"
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(diagram.xml_content)
            logger.info(f"✓ XML generated and saved to {xml_path} (time: {xml_time:.2f}s, tokens: {xml_token_usage.get('total_tokens', 0)})")
            
            # 如果成功生成XML，删除之前可能存在的error.json（表示重试成功）
            error_path = model_dir / "error.json"
            if error_path.exists():
                error_path.unlink()
                logger.info(f"✓ Deleted previous error.json (retry succeeded)")
            
            # 渲染
            render_time = 0.0
            if renderer:
                logger.info(f"Rendering with {model_name}...")
                render_start_time = time.time()
                rendered_path = model_dir / "rendered.png"
                if renderer.render(diagram, rendered_path):
                    render_time = time.time() - render_start_time
                    logger.info(f"✓ Rendered to {rendered_path} (time: {render_time:.2f}s)")
                    model_result["rendered"] = True
                else:
                    render_time = time.time() - render_start_time
                    logger.warning(f"Failed to render {model_name} XML (time: {render_time:.2f}s)")
                    model_result["rendered"] = False
            else:
                model_result["rendered"] = False
            
            # 计算总时间
            total_time = time.time() - model_start_time
            
            # 计算元数据（使用Gemini的XML，如果Gemini成功）
            # 注意：metadata只使用Gemini的结果作为基准
            if is_gemini_model(model_name) and diagram:
                metadata = calculate_metadata(diagram.xml_content)
                
                # 添加图片哈希值到元数据（用于图片匹配）
                try:
                    original_path = sample_dir / "original.png"
                    if original_path.exists():
                        image_hash = get_file_hash(original_path, algorithm='md5')
                        metadata['image_hash_md5'] = image_hash
                except Exception as e:
                    logger.debug(f"Failed to calculate image hash for metadata: {e}")
                
                metadata_path = sample_dir / "metadata.json"
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                metadata_stats.append(metadata)
                logger.debug(f"Saved metadata to {metadata_path}")
            
            # 为Gemini创建筛选状态文件
            if is_gemini_model(model_name):
                screening_status = {
                    "status": "pending",
                    "screened_date": None,
                    "screener_notes": None
                }
                screening_path = model_dir / "screening_status.json"
                with open(screening_path, 'w', encoding='utf-8') as f:
                    json.dump(screening_status, f, indent=2, ensure_ascii=False)
                logger.debug(f"Created screening status file: {screening_path}")
            
            # 合并token使用量（描述+XML）
            total_token_usage = {
                "description": desc_token_usage,
                "xml": xml_token_usage,
                "total_prompt_tokens": desc_token_usage.get('prompt_tokens', 0) + xml_token_usage.get('prompt_tokens', 0),
                "total_completion_tokens": desc_token_usage.get('completion_tokens', 0) + xml_token_usage.get('completion_tokens', 0),
                "total_tokens": desc_token_usage.get('total_tokens', 0) + xml_token_usage.get('total_tokens', 0)
            }
            
            model_result["status"] = "success"
            model_result["xml_path"] = str(xml_path)
            if renderer:
                model_result["rendered_path"] = str(rendered_path)
            model_result["token_usage"] = total_token_usage
            model_result["timing"] = {
                "description_time_seconds": desc_time,
                "xml_time_seconds": xml_time,
                "render_time_seconds": render_time,
                "total_time_seconds": total_time
            }
            
            # 保存每个模型的性能统计到文件
            performance_info = {
                "model": model_name,
                "sample": sample_dir.name,
                "status": "success",
                "token_usage": total_token_usage,
                "timing": model_result["timing"],
                "timestamp": datetime.now().isoformat()
            }
            performance_path = model_dir / "performance.json"
            with open(performance_path, 'w', encoding='utf-8') as f:
                json.dump(performance_info, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved performance stats to {performance_path}")
            
            logger.info(f"✓ {model_name} completed: total_time={total_time:.2f}s, total_tokens={total_token_usage['total_tokens']}")
            
        except Exception as e:
            # 记录失败时的总时间
            total_time = time.time() - model_start_time
            
            logger.error(f"Model {model_name} failed for {image_path.name}: {e}", exc_info=True)
            model_result["status"] = "failed"
            model_result["error_type"] = type(e).__name__
            model_result["error_message"] = str(e)
            model_result["timing"] = {
                "total_time_seconds": total_time
            }
            model_result["token_usage"] = {
                "description": desc_token_usage,
                "xml": {},
                "total_tokens": desc_token_usage.get('total_tokens', 0)
            }
            
            # 判断错误是否应该重试（只有API请求失败才重试）
            error_type = type(e).__name__
            error_message = str(e)
            should_retry = _should_retry_error(error_type, error_message)
            
            # 保存错误信息（包含性能统计）
            error_info = {
                "status": "failed",
                "error_type": error_type,
                "error_message": error_message,
                "timestamp": datetime.now().isoformat(),
                "time_seconds": total_time,
                "token_usage": model_result.get("token_usage", {}),
                "timing": model_result.get("timing", {}),
                "retry_on_next_run": should_retry  # 只有API请求失败才标记为需要重试
            }
            error_path = model_dir / "error.json"
            with open(error_path, 'w', encoding='utf-8') as f:
                json.dump(error_info, f, indent=2, ensure_ascii=False)
            logger.error(f"Saved error info to {error_path}")
            
            # 如果错误可以重试（API请求失败），删除可能存在的旧diagram.xml
            if should_retry:
                xml_path = model_dir / "diagram.xml"
                if xml_path.exists():
                    xml_path.unlink()
                    logger.info(f"Removed incomplete diagram.xml for retry")
                logger.info(f"Error is retryable (API request failure), will retry on next run")
            else:
                logger.info(f"Error is not retryable (likely a logic error: {error_type}), will not retry on next run")
            
            # 即使失败也保存性能统计
            performance_info = {
                "model": model_name,
                "sample": sample_dir.name,
                "status": "failed",
                "token_usage": model_result.get("token_usage", {}),
                "timing": model_result.get("timing", {}),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            performance_path = model_dir / "performance.json"
            with open(performance_path, 'w', encoding='utf-8') as f:
                json.dump(performance_info, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved performance stats to {performance_path}")
        
        results[model_name] = model_result
    
    return {
        "results": results,
        "metadata": metadata_stats[0] if metadata_stats else None
    }


def generate_dataset_json(target_dir: Path, generate_qa: bool = False):
    """
    生成task1_benchmark的dataset.json文件
    
    Args:
        target_dir: task1_benchmark目录
        generate_qa: 是否读取QA对（默认False，因为QA对应该由generate_qa_pairs.py单独生成）
    """
    logger.info("\n" + "=" * 80)
    logger.info("Generating dataset.json")
    logger.info("=" * 80)
    
    # 检查是否已有dataset.json（支持断点续传）
    dataset_path = target_dir / "dataset.json"
    existing_qa_samples = {}
    if dataset_path.exists():
        try:
            with open(dataset_path, 'r', encoding='utf-8') as f:
                existing_dataset = json.load(f)
                for sample in existing_dataset.get("samples", []):
                    sample_key = f"{sample.get('domain')}/{sample.get('sample_id')}"
                    if sample.get("qa_pairs"):
                        existing_qa_samples[sample_key] = sample.get("qa_pairs")
                        logger.debug(f"Found existing QA pairs for {sample_key}")
        except Exception as e:
            logger.warning(f"Failed to load existing dataset.json: {e}")
    
    dataset = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "task": "task1",
        "total_samples": 0,
        "statistics": {
            "by_domain": {}
        },
        "samples": []
    }
    
    # 扫描所有领域
    domain_dirs = sorted([d for d in target_dir.glob('domain_*') if d.is_dir()])
    
    for domain_dir in domain_dirs:
        domain = domain_dir.name
        domain_samples = []
        
        # 扫描所有样本
        sample_dirs = sorted([d for d in domain_dir.glob('sample_*') if d.is_dir()])
        
        for sample_dir in sample_dirs:
            sample_id = sample_dir.name
            sample_key = f"{domain}/{sample_id}"
            
            # 检查Gemini数据是否存在（查找包含 gemini 的模型目录，优先 gemini-3-pro-preview）
            gemini_dir = None
            original_path = sample_dir / "original.png"
            preferred_dir = sample_dir / "model_gemini-3-pro-preview"
            if preferred_dir.exists():
                gemini_dir = preferred_dir
            else:
                for model_dir in sample_dir.glob("model_*"):
                    if "gemini" in model_dir.name.lower():
                        gemini_dir = model_dir
                        break
            
            if gemini_dir is None or not gemini_dir.exists():
                logger.warning(f"Skipping {sample_id} in {domain}: no Gemini data")
                continue
            
            # 读取Gemini描述
            desc_path = gemini_dir / "llm_description.txt"
            description = None
            if desc_path.exists():
                try:
                    with open(desc_path, 'r', encoding='utf-8') as f:
                        description = f.read()
                except Exception as e:
                    logger.warning(f"Failed to read description for {sample_id}: {e}")
            
            # 读取XML
            xml_path = gemini_dir / "diagram.xml"
            xml_content = None
            if xml_path.exists():
                try:
                    with open(xml_path, 'r', encoding='utf-8') as f:
                        xml_content = f.read()
                except Exception as e:
                    logger.warning(f"Failed to read XML for {sample_id}: {e}")
            
            # 检查渲染图
            rendered_path = gemini_dir / "rendered.png"
            rendered_exists = rendered_path.exists()
            
            # 构建相对路径（相对于target_dir）
            def get_relative_path(path: Path) -> str:
                try:
                    return str(path.relative_to(target_dir))
                except:
                    return str(path)
            
            # 读取QA对（从qa_pairs.json文件或已有dataset.json）
            qa_pairs = None
            if generate_qa:
                # 优先从已有dataset.json读取
                if sample_key in existing_qa_samples:
                    qa_pairs = existing_qa_samples[sample_key]
                    logger.debug(f"Using existing QA pairs from dataset.json for {sample_key}")
                else:
                    # 从qa_pairs.json文件读取（由generate_qa_pairs.py生成）
                    qa_pairs_path = sample_dir / "qa_pairs.json"
                    if qa_pairs_path.exists():
                        try:
                            with open(qa_pairs_path, 'r', encoding='utf-8') as f:
                                qa_data = json.load(f)
                                qa_pairs = qa_data.get("qa_pairs", [])
                                logger.debug(f"Loaded QA pairs from {qa_pairs_path} for {sample_key}")
                        except Exception as e:
                            logger.warning(f"Failed to read QA pairs from {qa_pairs_path}: {e}")
                    else:
                        logger.debug(f"No QA pairs found for {sample_key} (qa_pairs.json not found)")
            
            sample_data = {
                "domain": domain,
                "sample_id": sample_id,
                "path": get_relative_path(sample_dir),
                "original_image": get_relative_path(original_path) if original_path.exists() else None,
                "gemini_description": description,
                "xml": xml_content,
                "rendered_image": get_relative_path(rendered_path) if rendered_exists else None
            }
            
            # 添加QA对（如果有）
            if qa_pairs:
                sample_data["qa_pairs"] = qa_pairs

            domain_samples.append(sample_data)
        
        # 更新统计
        dataset["statistics"]["by_domain"][domain] = len(domain_samples)
        dataset["samples"].extend(domain_samples)
    
    dataset["total_samples"] = len(dataset["samples"])
    
    # 更新统计信息（包含QA对统计）
    if generate_qa:
        total_qa_pairs = sum(len(s.get("qa_pairs", [])) for s in dataset["samples"])
        dataset["statistics"]["total_qa_pairs"] = total_qa_pairs
    
    # 保存dataset.json
    with open(dataset_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✓ Generated dataset.json: {dataset['total_samples']} samples from {len(domain_dirs)} domains")
    if dataset['statistics'].get('total_qa_pairs', 0) > 0:
        logger.info(f"  Total QA pairs: {dataset['statistics'].get('total_qa_pairs', 0)}")
    logger.info(f"  Saved to: {dataset_path}")


def process_all_domains(
    source_dir: Path,
    target_dir: Path,
    models: list,
    provider: str = 'custom',
    model_config: dict = None,
    temperature: float = 0.0,
    resume: bool = True,
    limit_per_domain: int = None,
    domain_filter: list = None,
    skip_render: bool = False
):
    """
    处理所有领域的图片

    Args:
        source_dir: 源目录（raw_picture）
        target_dir: 目标目录（task1_benchmark）
        models: 模型列表
        provider: LLM provider
        model_config: 模型配置字典（key为模型名，value为模型配置）
        temperature: 温度参数
        resume: 是否断点续传
        limit_per_domain: 每个领域限制处理的图片数
        domain_filter: 领域过滤器（None表示处理所有领域，否则只处理指定的领域列表，如 ['ai', 'biology']）
        skip_render: 跳过渲染（用于HPC环境）
    """
    logger.info("=" * 80)
    logger.info("Task 1: Generate XML from images (multiple models)")
    logger.info("=" * 80)
    logger.info(f"Source directory: {source_dir}")
    logger.info(f"Target directory: {target_dir}")
    logger.info(f"Models: {models}")
    logger.info(f"Provider: {provider}, Temperature: {temperature}")
    logger.info(f"Resume: {resume}, Limit per domain: {limit_per_domain}")
    
    # 初始化组件
    llm_client = LLMClient()
    
    # 为每个模型创建描述生成器和XML生成器
    desc_generators = {}
    diagram_generators = {}
    for model_name in models:
        model_cfg = model_config.get(model_name, {}) if model_config else {}
        
        # 创建描述生成器（每个模型独立）
        desc_generators[model_name] = DescriptionGenerator(
            llm_client=llm_client,
            provider=model_cfg.get('provider', provider),
            model=model_cfg.get('model', model_name),  # 使用模型名作为默认值
            temperature=model_cfg.get('temperature', temperature)
        )
        
        # 创建XML生成器
        diagram_generators[model_name] = DiagramGenerator(
            llm_client=llm_client,
            provider=model_cfg.get('provider', provider),
            model=model_cfg.get('model', model_name),  # 使用模型名作为默认值
            temperature=model_cfg.get('temperature', temperature),
            max_repair_attempts=model_cfg.get('max_repair_attempts', 1)
        )

    renderer = DrawioRenderer(skip_render=skip_render)
    if not skip_render and not renderer.can_render():
        logger.warning("Drawio renderer not available, rendering will be skipped")
        renderer = None

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
    
    if not domain_dirs:
        logger.error("No domain directories found. Expected format: domain_*/")
        return
    
    total_processed = 0
    total_success = 0
    total_failed = 0
    
    # 统计每个模型的token和时间
    model_stats = {model_name: {
        "samples": 0,
        "success": 0,
        "failed": 0,
        "total_tokens": 0,
        "total_time": 0.0,
        "description_tokens": 0,
        "xml_tokens": 0,
        "description_time": 0.0,
        "xml_time": 0.0,
        "render_time": 0.0
    } for model_name in models}
    
    for domain_dir in domain_dirs:
        domain = domain_dir.name
        logger.info("\n" + "=" * 80)
        logger.info(f"Processing domain: {domain}")
        logger.info("=" * 80)
        
        # 查找图片（不按难度分层）
        try:
            image_paths = find_images(domain_dir, recursive=False)
            logger.info(f"Found {len(image_paths)} images in {domain}")
            
            if limit_per_domain and len(image_paths) > limit_per_domain:
                image_paths = image_paths[:limit_per_domain]
                logger.info(f"Limited to {limit_per_domain} images")
            
            if not image_paths:
                logger.warning(f"No images found in {domain}, skipping")
                continue
                
        except Exception as e:
            logger.error(f"Failed to find images in {domain}: {e}", exc_info=True)
            continue
        
        # 创建领域输出目录
        domain_output_dir = target_dir / domain
        domain_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建图片哈希到 sample_id 的映射（用于匹配已有图片）
        logger.info("Building image hash mapping for existing samples...")
        image_hash_to_sample = build_image_hash_to_sample_mapping(domain_output_dir)
        
        # 找到当前最大的 sample_id 编号（用于新图片）
        max_existing_idx = 0
        if image_hash_to_sample:
            for sample_id in image_hash_to_sample.values():
                try:
                    idx = int(sample_id.replace('sample_', ''))
                    max_existing_idx = max(max_existing_idx, idx)
                except ValueError:
                    pass
        next_new_idx = max_existing_idx + 1
        
        # 处理每张图片
        domain_processed = 0
        domain_success = 0
        domain_failed = 0
        
        for img_idx, img_path in enumerate(image_paths, 1):
            # 计算图片哈希值
            try:
                image_hash = get_file_hash(img_path, algorithm='md5')
            except Exception as e:
                logger.error(f"Failed to hash image {img_path}: {e}")
                image_hash = None
            
            # 通过哈希值匹配已有的 sample_id，或分配新的
            if image_hash and image_hash in image_hash_to_sample:
                # 图片已存在，使用已有的 sample_id
                sample_id = image_hash_to_sample[image_hash]
                logger.info(f"Image {img_path.name} (hash: {image_hash[:8]}...) matches existing {sample_id}")
            else:
                # 新图片，分配新的 sample_id
                sample_id = find_next_available_sample_id(domain_output_dir, start_from=next_new_idx)
                next_new_idx = int(sample_id.replace('sample_', '')) + 1
                if image_hash:
                    logger.info(f"Image {img_path.name} (hash: {image_hash[:8]}...) is new, assigned {sample_id}")
                else:
                    logger.info(f"Image {img_path.name} is new, assigned {sample_id}")
            
            sample_dir = domain_output_dir / sample_id
            
            # 检查是否已处理（断点续传）
            if resume:
                # 检查是否所有模型都已完成（成功生成diagram.xml）
                # 如果存在error.json，需要检查错误类型，只有API请求失败才重新处理
                all_done = True
                for model_name in models:
                    model_dir_name = get_model_dir_name(model_name)
                    model_dir = sample_dir / f"model_{model_dir_name}"
                    error_path = model_dir / "error.json"
                    
                    # 如果diagram.xml不存在，需要处理
                    if not (model_dir / "diagram.xml").exists():
                        # 如果有error.json，检查是否是应该重试的错误
                        if error_path.exists():
                            try:
                                with open(error_path, 'r', encoding='utf-8') as f:
                                    error_info = json.load(f)
                                error_type = error_info.get('error_type', '')
                                error_message = error_info.get('error_message', '')
                                retry_on_next_run = error_info.get('retry_on_next_run', None)
                                error_type_lower = error_type.lower()
                                
                                # 判断是否应该重试
                                should_retry = False
                                
                                # 优先检查 retry_on_next_run 字段（如果存在）
                                if retry_on_next_run is not None:
                                    should_retry = retry_on_next_run
                                    # 但是，如果错误消息显示是应该重试的错误（代码已修复或新增重试逻辑），即使 retry_on_next_run=False 也应该重试
                                    if not should_retry and _should_retry_error(error_type, error_message):
                                        # 使用当前的 _should_retry_error 重新判断（可能代码已修复或新增了重试逻辑）
                                        should_retry = True
                                        logger.info(f"Sample {sample_id} has retryable error for {model_name} (code updated), will retry despite retry_on_next_run=False. Error: {error_type} - {error_message[:100]}...")
                                else:
                                    # 如果没有 retry_on_next_run 字段，使用 _should_retry_error 判断（兼容旧的错误文件）
                                    should_retry = _should_retry_error(error_type, error_message)
                                
                                if should_retry:
                                    logger.info(f"Sample {sample_id} has retryable error for {model_name}, will retry")
                                    all_done = False
                                    break
                                else:
                                    # 不是API错误，跳过（可能是JSON解析错误等不应该重试的错误）
                                    logger.debug(f"Sample {sample_id} has non-retryable error for {model_name}, skipping")
                            except Exception as e:
                                logger.warning(f"Failed to read error.json for {model_name}: {e}, will retry")
                                all_done = False
                                break
                        else:
                            # 既没有diagram.xml也没有error.json，需要处理
                            all_done = False
                            break
                
                if all_done:
                    logger.info(f"Sample {sample_id} already processed, skipping")
                    domain_processed += 1
                    domain_success += 1
                    continue
            
            logger.info(f"\n--- Processing {img_idx}/{len(image_paths)}: {sample_id} ---")
            
            try:
                result = process_single_image(
                    img_path,
                    sample_dir,
                    models,
                    llm_client=llm_client,
                    desc_generators=desc_generators,
                    diagram_generators=diagram_generators,
                    renderer=renderer
                )
                
                # 统计结果
                success_count = sum(1 for r in result['results'].values() if r.get('status') == 'success')
                failed_count = sum(1 for r in result['results'].values() if r.get('status') == 'failed')
                
                # 收集每个模型的统计信息
                for model_name, model_result in result['results'].items():
                    if model_name not in model_stats:
                        continue
                    
                    model_stats[model_name]["samples"] += 1
                    
                    if model_result.get('status') == 'success':
                        model_stats[model_name]["success"] += 1
                        
                        # 统计token和时间
                        token_usage = model_result.get('token_usage', {})
                        timing = model_result.get('timing', {})
                        
                        # Token统计
                        if isinstance(token_usage, dict):
                            desc_tokens = token_usage.get('description', {}).get('total_tokens', 0)
                            xml_tokens = token_usage.get('xml', {}).get('total_tokens', 0)
                            total_tokens = token_usage.get('total_tokens', 0)
                            
                            model_stats[model_name]["description_tokens"] += desc_tokens
                            model_stats[model_name]["xml_tokens"] += xml_tokens
                            model_stats[model_name]["total_tokens"] += total_tokens
                        
                        # 时间统计
                        if isinstance(timing, dict):
                            desc_time = timing.get('description_time_seconds', 0.0)
                            xml_time = timing.get('xml_time_seconds', 0.0)
                            render_time = timing.get('render_time_seconds', 0.0)
                            total_time = timing.get('total_time_seconds', 0.0)
                            
                            model_stats[model_name]["description_time"] += desc_time
                            model_stats[model_name]["xml_time"] += xml_time
                            model_stats[model_name]["render_time"] += render_time
                            model_stats[model_name]["total_time"] += total_time
                    else:
                        model_stats[model_name]["failed"] += 1
                
                domain_processed += 1
                domain_success += success_count
                domain_failed += failed_count
                
                logger.info(f"✓ Sample {sample_id} completed: {success_count} success, {failed_count} failed")
                
            except Exception as e:
                logger.error(f"Failed to process sample {sample_id}: {e}", exc_info=True)
                domain_failed += len(models)
        
        total_processed += domain_processed
        total_success += domain_success
        total_failed += domain_failed
        
        logger.info(f"\nDomain {domain} summary: {domain_processed} samples, {domain_success} success, {domain_failed} failed")
    
    # 最终统计
    logger.info("\n" + "=" * 80)
    logger.info("Final Summary")
    logger.info("=" * 80)
    logger.info(f"Total samples processed: {total_processed}")
    logger.info(f"Total model runs (success): {total_success}")
    logger.info(f"Total model runs (failed): {total_failed}")
    logger.info(f"Success rate: {total_success/(total_success+total_failed)*100:.1f}%" if (total_success+total_failed) > 0 else "N/A")
    logger.info(f"Output directory: {target_dir}")
    
    # 每个模型的详细统计
    logger.info("\n" + "=" * 80)
    logger.info("Model Statistics (Average per Sample)")
    logger.info("=" * 80)
    
    stats_summary = {}
    for model_name, stats in model_stats.items():
        if stats["success"] == 0:
            logger.info(f"\n{model_name}: No successful samples")
            stats_summary[model_name] = {
                "samples": stats["samples"],
                "success": stats["success"],
                "failed": stats["failed"],
                "success_rate": 0.0
            }
            continue
        
        # 计算平均值
        avg_total_tokens = stats["total_tokens"] / stats["success"]
        avg_total_time = stats["total_time"] / stats["success"]
        avg_desc_tokens = stats["description_tokens"] / stats["success"]
        avg_xml_tokens = stats["xml_tokens"] / stats["success"]
        avg_desc_time = stats["description_time"] / stats["success"]
        avg_xml_time = stats["xml_time"] / stats["success"]
        avg_render_time = stats["render_time"] / stats["success"]
        success_rate = stats["success"] / stats["samples"] * 100 if stats["samples"] > 0 else 0.0
        
        logger.info(f"\n{model_name}:")
        logger.info(f"  Samples: {stats['samples']} (success: {stats['success']}, failed: {stats['failed']}, rate: {success_rate:.1f}%)")
        logger.info(f"  Average Time per Sample:")
        logger.info(f"    Description: {avg_desc_time:.2f}s")
        logger.info(f"    XML Generation: {avg_xml_time:.2f}s")
        logger.info(f"    Rendering: {avg_render_time:.2f}s")
        logger.info(f"    Total: {avg_total_time:.2f}s")
        logger.info(f"  Average Tokens per Sample:")
        logger.info(f"    Description: {avg_desc_tokens:.0f}")
        logger.info(f"    XML Generation: {avg_xml_tokens:.0f}")
        logger.info(f"    Total: {avg_total_tokens:.0f}")
        
        stats_summary[model_name] = {
            "samples": stats["samples"],
            "success": stats["success"],
            "failed": stats["failed"],
            "success_rate": success_rate,
            "average_time_seconds": {
                "description": avg_desc_time,
                "xml": avg_xml_time,
                "render": avg_render_time,
                "total": avg_total_time
            },
            "average_tokens": {
                "description": avg_desc_tokens,
                "xml": avg_xml_tokens,
                "total": avg_total_tokens
            },
            "total_time_seconds": stats["total_time"],
            "total_tokens": stats["total_tokens"]
        }
    
    # 保存统计信息到JSON文件（追加模式，合并已有数据）
    stats_file = target_dir / "model_statistics.json"
    
    # 读取已有数据（如果存在）
    existing_data = {}
    if stats_file.exists():
        try:
            with open(stats_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            logger.info(f"Loaded existing statistics from {stats_file}")
        except Exception as e:
            logger.warning(f"Failed to load existing statistics: {e}, will create new file")
            existing_data = {}
    
    # 合并数据：保留已有的模型统计，添加新的模型统计
    existing_models = existing_data.get("models", {})
    
    # 合并模型统计（新数据覆盖旧数据，但如果新数据为空则保留旧数据）
    merged_models = existing_models.copy()
    for model_name, new_stats in stats_summary.items():
        # 如果新模型有数据，使用新数据；否则保留旧数据
        if new_stats.get("samples", 0) > 0 or new_stats.get("success", 0) > 0:
            merged_models[model_name] = new_stats
        elif model_name not in merged_models:
            # 如果新模型没有数据但旧数据中有，保留旧数据
            existing_stats = existing_models.get(model_name)
            if existing_stats is not None:
                merged_models[model_name] = existing_stats
    
    # 过滤掉 None 值，确保所有值都是字典
    merged_models = {k: v for k, v in merged_models.items() if v is not None and isinstance(v, dict)}
    
    # 计算合并后的总统计（基于所有模型的数据）
    merged_total_samples = max(
        existing_data.get("total_samples", 0),
        total_processed
    )
    merged_total_success = sum(
        stats.get("success", 0) for stats in merged_models.values()
    )
    merged_total_failed = sum(
        stats.get("failed", 0) for stats in merged_models.values()
    )
    
    # 保存合并后的统计信息
    final_stats = {
        "generated_at": datetime.now().isoformat(),
        "total_samples": merged_total_samples,
        "total_success": merged_total_success,
        "total_failed": merged_total_failed,
        "models": merged_models
    }
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(final_stats, f, indent=2, ensure_ascii=False)
    logger.info(f"\n✓ Statistics saved to {stats_file} (merged with existing data)")
    
    # 生成dataset.json（包含QA pairs，如果存在qa_pairs.json文件）
    generate_dataset_json(target_dir, generate_qa=True)


def main():
    parser = argparse.ArgumentParser(
        description="Task 1: Generate XML from images (multiple models)"
    )
    
    # Input/output
    parser.add_argument('--source', type=Path, required=True,
                        help='Source directory (raw_picture)')
    parser.add_argument('--target', type=Path, required=True,
                        help='Target directory (task1_benchmark)')
    
    # Models
    parser.add_argument('--models', type=str, nargs='+', required=True,
                        help='List of models to evaluate (e.g., gemini claude gpt4)')
    
    # LLM options
    parser.add_argument('--provider', type=str, default='custom',
                        choices=['siliconflow', 'zhipu', 'custom', 'local'],
                        help='LLM provider')
    parser.add_argument('--temperature', type=float, default=0.0,
                        help='LLM temperature')
    
    # Processing options
    parser.add_argument('--resume', action='store_true', default=True,
                        help='Resume from last checkpoint (default: True)')
    parser.add_argument('--no-resume', dest='resume', action='store_false',
                        help='Do not resume, reprocess all')
    parser.add_argument('--limit-per-domain', type=int,
                        help='Limit number of images per domain')
    parser.add_argument('--domain', type=str, nargs='+',
                        help='Specify domain(s) to process using directory names (e.g., --domain domain_ai domain_biology). If not specified, process all domains.')

    # Rendering options
    parser.add_argument('--skip-render', action='store_true',
                        help='Skip rendering (only generate XML, for HPC environments)')

    args = parser.parse_args()
    
    # Validate
    if not args.source.exists():
        logger.error(f"Source directory not found: {args.source}")
        return 1
    
    # 创建目标目录
    args.target.mkdir(parents=True, exist_ok=True)
    
    # 运行处理
    try:
        process_all_domains(
            source_dir=args.source,
            target_dir=args.target,
            models=args.models,
            provider=args.provider,
            temperature=args.temperature,
            resume=args.resume,
            limit_per_domain=args.limit_per_domain,
            domain_filter=args.domain,
            skip_render=args.skip_render
        )
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
