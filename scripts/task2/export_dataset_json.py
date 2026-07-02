#!/usr/bin/env python3
"""
Export task2_benchmark dataset to a consolidated JSON file.

Each sample includes:
  - Gemini XML (diagram.xml)
  - Gemini 渲染图 (rendered.png)
  - 修改指令 (instructions/*/instruction.txt)
  - 模型修改XML (instructions/*/model_*/modified.xml)
  - 模型修改渲染图 (instructions/*/model_*/modified.png)
  - 图片领域 (domain)

Usage:
  python scripts/task2/export_dataset_json.py \
    --source VCG-Bench/data/task2_benchmark \
    --output VCG-Bench/data/task2_benchmark/dataset.json
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def read_file_content(file_path: Path) -> Optional[str]:
    """Read file content, return None if file doesn't exist."""
    if not file_path.exists():
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
        return None


def get_relative_path(file_path: Path, base_dir: Path) -> Optional[str]:
    """Get relative path from base_dir, return None if file doesn't exist."""
    if not file_path.exists():
        return None
    try:
        return str(file_path.relative_to(base_dir))
    except ValueError:
        # If file_path is not relative to base_dir, return absolute path
        return str(file_path)


def collect_sample_data(sample_dir: Path, domain: str, base_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Collect all data for a single sample.
    
    Args:
        sample_dir: Sample directory (e.g., domain_ai/sample_0001)
        domain: Domain name (e.g., domain_ai)
        base_dir: Base directory for relative paths (task2_benchmark)
        
    Returns:
        Sample data dictionary or None if sample is invalid
    """
    sample_id = sample_dir.name
    
    # Read Gemini XML
    gemini_xml_path = sample_dir / "diagram.xml"
    gemini_xml = read_file_content(gemini_xml_path)
    if gemini_xml is None:
        logger.warning(f"Missing diagram.xml in {sample_dir}, skipping")
        return None
    
    # Get Gemini rendered image path
    gemini_rendered_path = sample_dir / "rendered.png"
    gemini_rendered_rel = get_relative_path(gemini_rendered_path, base_dir)
    
    # Collect instructions and model outputs
    instructions_dir = sample_dir / "instructions"
    if not instructions_dir.exists():
        logger.warning(f"No instructions directory in {sample_dir}, skipping")
        return None
    
    instructions_data = []
    instruction_dirs = sorted([d for d in instructions_dir.glob('inst_*') if d.is_dir()])
    
    for inst_dir in instruction_dirs:
        inst_id = inst_dir.name
        
        # Read instruction text
        instruction_path = inst_dir / "instruction.txt"
        instruction_text = read_file_content(instruction_path)
        if instruction_text is None:
            logger.warning(f"Missing instruction.txt in {inst_dir}, skipping instruction")
            continue
        
        # Read instruction metadata
        inst_metadata_path = inst_dir / "instruction_metadata.json"
        inst_metadata = None
        if inst_metadata_path.exists():
            try:
                with open(inst_metadata_path, 'r', encoding='utf-8') as f:
                    inst_metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read instruction metadata: {e}")
        
        # Collect model outputs
        model_outputs = []
        model_dirs = sorted([d for d in inst_dir.glob('model_*') if d.is_dir()])
        
        for model_dir in model_dirs:
            model_name = model_dir.name.replace('model_', '')
            
            # Check if there's an error
            error_path = model_dir / "error.json"
            has_error = error_path.exists()
            
            # Get model modified XML
            model_xml_path = model_dir / "modified.xml"
            model_xml = read_file_content(model_xml_path)
            model_xml_rel = get_relative_path(model_xml_path, base_dir)
            
            # Get model modified rendered image
            model_rendered_path = model_dir / "modified.png"
            model_rendered_rel = get_relative_path(model_rendered_path, base_dir)
            
            # Read model output JSON if exists
            model_output_json_path = model_dir / "model_output.json"
            model_output_json = None
            if model_output_json_path.exists():
                try:
                    with open(model_output_json_path, 'r', encoding='utf-8') as f:
                        model_output_json = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read model output JSON: {e}")
            
            # Read token usage if exists
            token_usage_path = model_dir / "token_usage.json"
            token_usage = None
            if token_usage_path.exists():
                try:
                    with open(token_usage_path, 'r', encoding='utf-8') as f:
                        token_usage = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read token usage: {e}")
            
            model_output = {
                "model_name": model_name,
                "modified_xml": model_xml,  # Full XML content
                "modified_xml_path": model_xml_rel,  # Relative path
                "modified_rendered_path": model_rendered_rel,  # Relative path
                "has_error": has_error,
                "model_output_json": model_output_json,  # Incremental changes JSON
                "token_usage": token_usage
            }
            
            if has_error:
                try:
                    with open(error_path, 'r', encoding='utf-8') as f:
                        model_output["error"] = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read error JSON: {e}")
            
            model_outputs.append(model_output)
        
        instructions_data.append({
            "instruction_id": inst_id,
            "instruction": instruction_text,
            "instruction_metadata": inst_metadata,
            "model_outputs": model_outputs
        })
    
    if not instructions_data:
        logger.warning(f"No valid instructions in {sample_dir}, skipping")
        return None
    
    # Read sample metadata if exists
    metadata_path = sample_dir / "metadata.json"
    metadata = None
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read sample metadata: {e}")
    
    sample_data = {
        "domain": domain,
        "sample_id": sample_id,
        "sample_path": str(sample_dir.relative_to(base_dir)),
        "gemini_xml": gemini_xml,  # Full XML content
        "gemini_xml_path": get_relative_path(gemini_xml_path, base_dir),  # Relative path
        "gemini_rendered_path": gemini_rendered_rel,  # Relative path
        "instructions": instructions_data,
        "metadata": metadata
    }
    
    return sample_data


def export_dataset_json(source_dir: Path, output_path: Path, domain_filter: list = None) -> Dict[str, Any]:
    """
    Export task2_benchmark dataset to JSON file.
    
    Args:
        source_dir: task2_benchmark directory
        output_path: Output JSON file path
        domain_filter: 领域过滤器（None表示处理所有领域，否则只处理指定的领域列表，如 ['ai', 'biology']）
        
    Returns:
        Summary dictionary
    """
    logger.info("=" * 80)
    logger.info("Task 2: Export Dataset JSON")
    logger.info("=" * 80)
    logger.info(f"Source directory: {source_dir}")
    logger.info(f"Output file: {output_path}")
    
    if not source_dir.exists():
        raise ValueError(f"Source directory not found: {source_dir}")
    
    # Collect all samples
    samples = []
    domain_stats = {}
    
    # Scan all domains
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
    
    for domain_dir in domain_dirs:
        domain = domain_dir.name
        logger.info(f"\nProcessing domain: {domain}")
        
        # Scan all samples
        sample_dirs = sorted([d for d in domain_dir.glob('sample_*') if d.is_dir()])
        logger.info(f"Found {len(sample_dirs)} samples")
        
        domain_count = 0
        for sample_dir in sample_dirs:
            sample_data = collect_sample_data(sample_dir, domain, source_dir)
            if sample_data:
                samples.append(sample_data)
                domain_count += 1
                logger.debug(f"Collected data for {sample_dir.name}")
        
        domain_stats[domain] = domain_count
        logger.info(f"Collected {domain_count} samples from {domain}")
    
    # Create dataset structure
    dataset = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "task": "task2",
        "source": str(source_dir.relative_to(source_dir.parent)) if source_dir.parent else str(source_dir),
        "total_samples": len(samples),
        "statistics": {
            "by_domain": domain_stats,
            "total_instructions": sum(len(s["instructions"]) for s in samples),
            "total_model_outputs": sum(
                sum(len(inst["model_outputs"]) for inst in s["instructions"])
                for s in samples
            )
        },
        "samples": samples
    }
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    
    logger.info("\n" + "=" * 80)
    logger.info("Export Summary")
    logger.info("=" * 80)
    logger.info(f"Total samples: {len(samples)}")
    logger.info(f"Total instructions: {dataset['statistics']['total_instructions']}")
    logger.info(f"Total model outputs: {dataset['statistics']['total_model_outputs']}")
    logger.info(f"Output file: {output_path}")
    
    return {
        "output_path": str(output_path),
        "total_samples": len(samples),
        "statistics": dataset['statistics']
    }


def main():
    parser = argparse.ArgumentParser(
        description="Export task2_benchmark dataset to consolidated JSON file"
    )
    
    parser.add_argument('--source', type=Path, required=True,
                        help='Source directory (task2_benchmark)')
    parser.add_argument('--output', type=Path, required=True,
                        help='Output JSON file path')
    parser.add_argument('--domain', type=str, nargs='+',
                        help='Specify domain(s) to process using directory names (e.g., --domain domain_ai domain_biology). If not specified, process all domains.')
    
    args = parser.parse_args()
    
    try:
        summary = export_dataset_json(args.source, args.output, domain_filter=args.domain)
        logger.info("\n✓ Export completed successfully!")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

