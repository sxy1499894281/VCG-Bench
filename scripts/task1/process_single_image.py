#!/usr/bin/env python3
"""
单独处理一张图片，生成 task1 的 LLM 描述和 XML 代码
Usage: python scripts/task1/process_single_image.py <image_path> [--model MODEL] [--output OUTPUT_DIR]
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
from dotenv import load_dotenv
load_dotenv(project_root / '.env', override=False)

from src.core.models import ImageInfo
from src.processors import DescriptionGenerator, DiagramGenerator
from src.llm.client import LLMClient
from src.renderer import DrawioRenderer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_model_dir_name(model_name: str) -> str:
    """Match evaluation layout for provider model names that include slashes."""
    return model_name.split("/")[-1] if "/" in model_name else model_name


def process_single_image_standalone(
    image_path: Path,
    output_dir: Path,
    model: str = 'gemini-3-pro-preview',
    provider: str = 'custom',
    temperature: float = 0.0,
    skip_render: bool = False
):
    """
    单独处理一张图片，生成 LLM 描述和 XML 代码
    
    Args:
        image_path: 图片路径
        output_dir: 输出目录
        model: 模型名称（默认使用 gemini-3-pro-preview）
        provider: LLM provider
        temperature: 温度参数
        skip_render: 是否跳过渲染
    """
    logger.info("=" * 80)
    logger.info("Processing Single Image for Task 1")
    logger.info("=" * 80)
    logger.info(f"Image: {image_path}")
    logger.info(f"Model: {model}")
    logger.info(f"Output: {output_dir}")
    
    # 验证图片路径
    if not image_path.exists():
        logger.error(f"Image not found: {image_path}")
        return False
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制原始图片
    original_path = output_dir / "original.png"
    shutil.copy2(image_path, original_path)
    logger.info(f"Copied original image to {original_path}")
    
    # 创建 ImageInfo
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
    
    # 初始化 LLM 客户端
    llm_client = LLMClient()
    
    # 创建模型目录
    model_dir = output_dir / f"model_{get_model_dir_name(model)}"
    model_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 1. 生成描述
        logger.info("\n--- Step 1: Generating Description ---")
        desc_gen = DescriptionGenerator(
            llm_client=llm_client,
            provider=provider,
            model=model,
            temperature=temperature
        )
        
        desc_start_time = time.time()
        description, desc_tokens = desc_gen.generate_description(
            image_info,
            use_llm=True
        )
        desc_time = time.time() - desc_start_time
        
        logger.info(f"✓ Description generated (time: {desc_time:.2f}s, tokens: {desc_tokens.get('total_tokens', 0)})")
        
        # 保存描述
        if description:
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
            logger.info(f"✓ Saved description to {desc_path}")
        
        # 2. 生成 XML
        logger.info("\n--- Step 2: Generating XML ---")
        diagram_gen = DiagramGenerator(
            llm_client=llm_client,
            provider=provider,
            model=model,
            temperature=temperature
        )
        
        xml_start_time = time.time()
        diagram, xml_tokens = diagram_gen.generate_diagram(
            image_info,
            description=description,
            use_llm=True
        )
        xml_time = time.time() - xml_start_time
        
        logger.info(f"✓ XML generated (time: {xml_time:.2f}s, tokens: {xml_tokens.get('total_tokens', 0)})")
        
        # 保存 XML
        xml_path = model_dir / "diagram.xml"
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(diagram.xml_content)
        logger.info(f"✓ Saved XML to {xml_path}")

        render_success = False
        render_time = 0.0
        if not skip_render:
            logger.info("\n--- Step 3: Rendering XML ---")
            render_start_time = time.time()
            renderer = DrawioRenderer()
            rendered_path = model_dir / "rendered.png"
            if renderer.can_render() and renderer.render(diagram, rendered_path):
                render_time = time.time() - render_start_time
                render_success = True
                logger.info(f"✓ Rendered PNG to {rendered_path} (time: {render_time:.2f}s)")
            else:
                render_time = time.time() - render_start_time
                logger.warning(f"Rendering skipped or failed (time: {render_time:.2f}s)")
        
        # 保存统计信息
        stats = {
            "model": model,
            "image": str(image_path),
            "status": "success",
            "token_usage": {
                "description": desc_tokens,
                "xml": xml_tokens,
                "total_tokens": desc_tokens.get('total_tokens', 0) + xml_tokens.get('total_tokens', 0)
            },
            "timing": {
                "description_time_seconds": desc_time,
                "xml_time_seconds": xml_time,
                "render_time_seconds": render_time,
                "total_time_seconds": desc_time + xml_time + render_time
            },
            "rendered": render_success,
            "timestamp": datetime.now().isoformat()
        }
        
        stats_path = output_dir / "stats.json"
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ Saved stats to {stats_path}")
        
        logger.info("\n" + "=" * 80)
        logger.info("Processing Completed Successfully!")
        logger.info("=" * 80)
        logger.info(f"Description: {model_dir / 'llm_description.txt'}")
        logger.info(f"XML: {model_dir / 'diagram.xml'}")
        if render_success:
            logger.info(f"Rendered PNG: {model_dir / 'rendered.png'}")
        logger.info(f"Output directory: {output_dir}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to process image: {e}", exc_info=True)
        
        # 保存错误信息
        error_info = {
            "status": "failed",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "timestamp": datetime.now().isoformat()
        }
        error_path = output_dir / "error.json"
        with open(error_path, 'w', encoding='utf-8') as f:
            json.dump(error_info, f, indent=2, ensure_ascii=False)
        logger.error(f"Saved error info to {error_path}")
        
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Process a single image for Task 1 (generate LLM description and XML)"
    )
    
    parser.add_argument('image_path', type=Path,
                        help='Path to the input image')
    parser.add_argument('--model', type=str, default='gemini-3-pro-preview',
                        help='Model name (default: gemini-3-pro-preview)')
    parser.add_argument('--output', type=Path, default=None,
                        help='Output directory (default: /tmp/task1_single_image_<timestamp>)')
    parser.add_argument('--provider', type=str, default='custom',
                        choices=['siliconflow', 'zhipu', 'custom', 'local'],
                        help='LLM provider (default: custom)')
    parser.add_argument('--temperature', type=float, default=0.0,
                        help='LLM temperature (default: 0.0)')
    parser.add_argument('--skip-render', action='store_true',
                        help='Skip Draw.io rendering and only write description/XML')
    
    args = parser.parse_args()
    
    # 设置默认输出目录
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = Path(f"/tmp/task1_single_image_{timestamp}")
    
    # 确保输出目录是绝对路径
    args.output = args.output.resolve()
    
    # 运行处理
    success = process_single_image_standalone(
        image_path=args.image_path.resolve(),
        output_dir=args.output,
        model=args.model,
        provider=args.provider,
        temperature=args.temperature,
        skip_render=args.skip_render
    )
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
