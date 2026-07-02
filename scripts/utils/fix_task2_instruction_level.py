#!/usr/bin/env python3
"""
修复 Task2 评估结果文件中的 instruction_level 字段
从 instruction_id 中提取难度级别（inst_easy_001 -> Easy, inst_medium_002 -> Medium, inst_hard_003 -> Hard）
"""

import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_instruction_level(instruction_id: str) -> str:
    """
    从 instruction_id 中提取难度级别
    
    Args:
        instruction_id: 指令ID（如 "inst_easy_001", "inst_medium_002", "inst_hard_003"）
        
    Returns:
        难度级别（"Easy", "Medium", "Hard" 或 "unknown"）
    """
    if not instruction_id or not isinstance(instruction_id, str):
        return "unknown"
    
    if instruction_id.startswith("inst_"):
        parts = instruction_id.split("_")
        if len(parts) >= 2:
            difficulty = parts[1].capitalize()  # easy -> Easy, medium -> Medium, hard -> Hard
            return difficulty
    
    return "unknown"


def fix_json_file(json_file: Path) -> bool:
    """
    修复单个 JSON 文件中的 instruction_level
    
    Args:
        json_file: JSON 文件路径
        
    Returns:
        是否成功修复
    """
    try:
        # 读取文件
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 处理 instructions 列表
        instructions = data.get('instructions', [])
        if not instructions:
            logger.debug(f"{json_file.name}: No instructions found")
            return False
        
        fixed_count = 0
        for inst in instructions:
            instruction_id = inst.get('instruction_id', '')
            current_level = inst.get('instruction_level', 'unknown')
            
            # 如果已经是正确的，跳过
            if current_level != 'unknown':
                continue
            
            # 从 instruction_id 提取
            extracted_level = extract_instruction_level(instruction_id)
            if extracted_level != 'unknown' and extracted_level != current_level:
                inst['instruction_level'] = extracted_level
                fixed_count += 1
                logger.debug(f"  Fixed {instruction_id}: unknown -> {extracted_level}")
        
        if fixed_count == 0:
            logger.debug(f"{json_file.name}: No fixes needed")
            return False
        
        # 备份原文件
        backup_file = json_file.with_suffix('.json.bak2')
        if not backup_file.exists():
            import shutil
            shutil.copy2(json_file, backup_file)
            logger.info(f"Created backup: {backup_file.name}")
        
        # 保存修复后的文件
        temp_file = json_file.with_suffix('.json.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # 原子替换
        temp_file.replace(json_file)
        logger.info(f"Fixed {json_file.name}: {fixed_count} instruction_level(s) updated")
        return True
        
    except Exception as e:
        logger.error(f"Error processing {json_file.name}: {e}", exc_info=True)
        return False


def main():
    """主函数"""
    fragments_dir = Path('data/task2_evaluation/fragments')
    
    if not fragments_dir.exists():
        logger.error(f"Directory not found: {fragments_dir}")
        return
    
    # 查找所有 JSON 文件
    json_files = list(fragments_dir.glob('*.json'))
    json_files = [f for f in json_files if not f.name.endswith('.bak') and not f.name.endswith('.bak2')]
    
    logger.info(f"Found {len(json_files)} JSON files to process")
    
    # 处理每个文件
    fixed_count = 0
    for json_file in json_files:
        if fix_json_file(json_file):
            fixed_count += 1
    
    logger.info(f"Fixed {fixed_count} out of {len(json_files)} files")
    
    # 验证修复结果
    logger.info("\nVerifying fixes...")
    for json_file in json_files[:3]:  # 验证前3个文件
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            instructions = data.get('instructions', [])
            unknown_count = sum(1 for inst in instructions if inst.get('instruction_level') == 'unknown')
            total_count = len(instructions)
            logger.info(f"  {json_file.name}: {total_count - unknown_count}/{total_count} have valid instruction_level")
        except Exception as e:
            logger.warning(f"  Error verifying {json_file.name}: {e}")


if __name__ == '__main__':
    main()

