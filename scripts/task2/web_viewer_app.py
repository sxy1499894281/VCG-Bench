#!/usr/bin/env python3
"""
Web Viewer Application for Task 2
网页查看应用，用于查看和编辑 Task 2 数据
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from flask import Flask, jsonify, request, render_template, send_file

# Setup logging
logger = logging.getLogger(__name__)

# Flask app
app = Flask(
    __name__,
    template_folder=Path(__file__).parent / 'templates',
    static_folder=Path(__file__).parent / 'templates' / 'static'
)

# Global variables
SOURCE_DIR = None
EVALUATION_DIR = None

# Cache for evaluation scores
EVALUATION_SCORES_CACHE = {}


def load_evaluation_scores(model_name: str, domain: str, evaluation_dir: Path) -> Dict[str, Any]:
    """
    加载评估结果中的分数
    
    Args:
        model_name: 模型名称（从benchmark目录中提取的，如 "DeepSeek-V3.2"）
        domain: 领域名称
        evaluation_dir: 评估结果目录
        
    Returns:
        字典，key为instruction_id，value为分数字典 {xdrfr, scs, xdrfr_results}
    """
    cache_key = f"{model_name}_{domain}"
    if cache_key in EVALUATION_SCORES_CACHE:
        return EVALUATION_SCORES_CACHE[cache_key]
    
    scores = {}
    
    # 首先尝试从 fragments 目录加载
    file_name = f"{model_name}_{domain}_results.json"
    file_path = evaluation_dir / "fragments" / file_name
    
    if not file_path.exists():
        # 尝试模糊匹配
        fragments_dir = evaluation_dir / "fragments"
        if not fragments_dir.exists():
            logger.debug(f"Fragments directory does not exist: {fragments_dir}")
            EVALUATION_SCORES_CACHE[cache_key] = scores
            return scores
        
        domain_pattern = f"*_{domain}_results.json"
        best_match = None
        # 规范化模型名称：转换为小写，替换特殊字符
        model_name_normalized = model_name.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
        
        logger.debug(f"Looking for evaluation file: model={model_name}, domain={domain}, normalized={model_name_normalized}")
        
        for f in fragments_dir.glob(domain_pattern):
            file_stem = f.stem
            domain_suffix = f"_{domain}_results"
            if file_stem.endswith(domain_suffix):
                file_model_name = file_stem[:-len(domain_suffix)]
                file_model_normalized = file_model_name.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
                
                logger.debug(f"Checking file: {f.name}, file_model_name={file_model_name}, normalized={file_model_normalized}")
                
                # 精确匹配
                if model_name_normalized == file_model_normalized:
                    best_match = f
                    logger.debug(f"Exact match found: {f.name}")
                    break
                # 检查模型名称是否在文件名中（处理前缀情况，如 Pro_deepseek-ai_DeepSeek-V3.2 包含 DeepSeek-V3.2）
                elif model_name_normalized in file_model_normalized:
                    if best_match is None:
                        best_match = f
                        logger.debug(f"Partial match found (contains): {f.name}")
                    elif file_model_normalized.endswith(model_name_normalized):
                        best_match = f
                        logger.debug(f"Better match found (ends with): {f.name}")
                # 检查文件名是否以模型名称结尾（处理带前缀的情况）
                elif file_model_normalized.endswith(model_name_normalized):
                    best_match = f
                    logger.debug(f"Match found (file ends with model): {f.name}")
                    break
                # 检查文件名是否以模型名称开头（处理后缀情况）
                elif file_model_normalized.startswith(model_name_normalized):
                    if best_match is None:
                        best_match = f
                        logger.debug(f"Match found (file starts with model): {f.name}")
        
        if best_match:
            file_path = best_match
            logger.info(f"✓ Matched evaluation file: {file_path.name} for model={model_name}, domain={domain}")
        else:
            # 列出所有可用的文件，帮助调试
            available_files = [f.name for f in fragments_dir.glob(domain_pattern)]
            logger.warning(f"✗ No evaluation file found for model={model_name}, domain={domain}")
            logger.warning(f"  Searched pattern: {domain_pattern}")
            logger.warning(f"  Available files for this domain: {len(available_files)} files")
            if available_files:
                logger.warning(f"  Example files: {available_files[:3]}")
            # 如果 fragments 目录中找不到，尝试从 detailed_results.json 加载
            detailed_results_file = evaluation_dir / "detailed_results.json"
            if detailed_results_file.exists():
                logger.info(f"Fragments file not found, trying detailed_results.json for model={model_name}, domain={domain}")
                try:
                    with open(detailed_results_file, 'r', encoding='utf-8') as f:
                        detailed_data = json.load(f)
                    
                    all_instructions = detailed_data.get('instructions', [])
                    logger.debug(f"Loading from detailed_results.json, found {len(all_instructions)} total instructions")
                    
                    # 规范化模型名称用于匹配
                    model_name_normalized = model_name.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
                    
                    # 匹配模型名称的辅助函数
                    def model_name_matches(file_model: str, search_model: str) -> bool:
                        """检查文件中的模型名称是否匹配搜索的模型名称"""
                        file_model_normalized = file_model.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
                        search_model_normalized = search_model.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
                        
                        # 精确匹配
                        if file_model_normalized == search_model_normalized:
                            return True
                        # 检查搜索模型是否在文件模型中（处理前缀情况）
                        if search_model_normalized in file_model_normalized:
                            return True
                        # 检查文件模型是否以搜索模型结尾
                        if file_model_normalized.endswith(search_model_normalized):
                            return True
                        # 检查文件模型是否以搜索模型开头
                        if file_model_normalized.startswith(search_model_normalized):
                            return True
                        return False
                    
                    matched_count = 0
                    for inst in all_instructions:
                        # 检查 domain 和 model 是否匹配
                        inst_domain = inst.get('domain')
                        inst_model = inst.get('model', '')
                        
                        if inst_domain != domain:
                            continue
                        
                        if not model_name_matches(inst_model, model_name):
                            continue
                        
                        instruction_id = inst.get('instruction_id')
                        if not instruction_id:
                            continue
                        
                        metrics = inst.get('metrics', {})
                        
                        # 提取XDRFR分数和详细结果
                        xdrfr = None
                        xdrfr_results = None
                        xdrfr_metric = metrics.get('xdrfr')
                        if xdrfr_metric and xdrfr_metric.get('success', False):
                            xdrfr = xdrfr_metric.get('score')
                            xdrfr_results = xdrfr_metric.get('details', {}).get('per_question_results', [])
                        
                        # 提取SCS分数
                        scs = None
                        scs_metric = metrics.get('style_consistency_score_task2')
                        if scs_metric and scs_metric.get('success', False):
                            scs = scs_metric.get('score')
                        
                        if xdrfr is not None or scs is not None:
                            scores[instruction_id] = {
                                'xdrfr': xdrfr,
                                'scs': scs,
                                'xdrfr_results': xdrfr_results
                            }
                            matched_count += 1
                    
                    logger.info(f"Loaded {matched_count} instructions from detailed_results.json for model={model_name}, domain={domain}")
                    EVALUATION_SCORES_CACHE[cache_key] = scores
                    return scores
                except Exception as e:
                    logger.warning(f"Failed to load from detailed_results.json: {e}", exc_info=True)
            
            EVALUATION_SCORES_CACHE[cache_key] = scores
            return scores
    
    # 从 fragments 文件加载
    loaded_from_fragments = False
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        instructions = data.get('instructions', [])
        logger.debug(f"Loading evaluation scores from {file_path}, found {len(instructions)} instructions")
        
        for inst in instructions:
            instruction_id = inst.get('instruction_id')
            if not instruction_id:
                continue
            
            metrics = inst.get('metrics', {})
            
            # 提取XDRFR分数和详细结果
            xdrfr = None
            xdrfr_results = None
            xdrfr_metric = metrics.get('xdrfr')
            if xdrfr_metric and xdrfr_metric.get('success', False):
                xdrfr = xdrfr_metric.get('score')
                xdrfr_results = xdrfr_metric.get('details', {}).get('per_question_results', [])
                logger.debug(f"Found xdrfr results for {instruction_id}: {len(xdrfr_results) if xdrfr_results else 0} results")
            else:
                logger.debug(f"No xdrfr metric or metric failed for {instruction_id}: success={xdrfr_metric.get('success') if xdrfr_metric else 'N/A'}")
            
            # 提取SCS分数
            scs = None
            scs_metric = metrics.get('style_consistency_score_task2')
            if scs_metric and scs_metric.get('success', False):
                scs = scs_metric.get('score')
            
            if xdrfr is not None or scs is not None:
                scores[instruction_id] = {
                    'xdrfr': xdrfr,
                    'scs': scs,
                    'xdrfr_results': xdrfr_results
                }
        
        loaded_from_fragments = True
        logger.info(f"✓ Loaded {len(scores)} instructions from fragments file: {file_path.name}")
    except Exception as e:
        logger.warning(f"Failed to load evaluation scores from {file_path}: {e}", exc_info=True)
        # 如果 fragments 文件加载失败，尝试从 detailed_results.json 加载
        loaded_from_fragments = False
    
    # 如果从 fragments 加载失败或没有找到数据，尝试从 detailed_results.json 加载
    if not loaded_from_fragments or len(scores) == 0:
        detailed_results_file = evaluation_dir / "detailed_results.json"
        if detailed_results_file.exists():
            logger.info(f"Trying to load from detailed_results.json for model={model_name}, domain={domain}")
            try:
                with open(detailed_results_file, 'r', encoding='utf-8') as f:
                    detailed_data = json.load(f)
                
                all_instructions = detailed_data.get('instructions', [])
                logger.debug(f"Loading from detailed_results.json, found {len(all_instructions)} total instructions")
                
                # 规范化模型名称用于匹配
                model_name_normalized = model_name.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
                
                # 匹配模型名称的辅助函数
                def model_name_matches(file_model: str, search_model: str) -> bool:
                    """检查文件中的模型名称是否匹配搜索的模型名称"""
                    file_model_normalized = file_model.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
                    search_model_normalized = search_model.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
                    
                    # 精确匹配
                    if file_model_normalized == search_model_normalized:
                        return True
                    # 检查搜索模型是否在文件模型中（处理前缀情况）
                    if search_model_normalized in file_model_normalized:
                        return True
                    # 检查文件模型是否以搜索模型结尾
                    if file_model_normalized.endswith(search_model_normalized):
                        return True
                    # 检查文件模型是否以搜索模型开头
                    if file_model_normalized.startswith(search_model_normalized):
                        return True
                    return False
                
                matched_count = 0
                for inst in all_instructions:
                    # 检查 domain 和 model 是否匹配
                    inst_domain = inst.get('domain')
                    inst_model = inst.get('model', '')
                    
                    if inst_domain != domain:
                        continue
                    
                    if not model_name_matches(inst_model, model_name):
                        continue
                    
                    instruction_id = inst.get('instruction_id')
                    if not instruction_id:
                        continue
                    
                    metrics = inst.get('metrics', {})
                    
                    # 提取XDRFR分数和详细结果
                    xdrfr = None
                    xdrfr_results = None
                    xdrfr_metric = metrics.get('xdrfr')
                    if xdrfr_metric and xdrfr_metric.get('success', False):
                        xdrfr = xdrfr_metric.get('score')
                        xdrfr_results = xdrfr_metric.get('details', {}).get('per_question_results', [])
                    
                    # 提取SCS分数
                    scs = None
                    scs_metric = metrics.get('style_consistency_score_task2')
                    if scs_metric and scs_metric.get('success', False):
                        scs = scs_metric.get('score')
                    
                    if xdrfr is not None or scs is not None:
                        scores[instruction_id] = {
                            'xdrfr': xdrfr,
                            'scs': scs,
                            'xdrfr_results': xdrfr_results
                        }
                        matched_count += 1
                
                logger.info(f"✓ Loaded {matched_count} instructions from detailed_results.json for model={model_name}, domain={domain}")
            except Exception as e:
                logger.warning(f"Failed to load from detailed_results.json: {e}", exc_info=True)
    
    EVALUATION_SCORES_CACHE[cache_key] = scores
    return scores


def get_instruction_scores(model_name: str, domain: str, instruction_id: str, evaluation_dir: Path, sample_id: str = None) -> Dict[str, Any]:
    """
    获取单个指令的评估分数
    
    必须同时匹配4个维度才能唯一确定一个评估结果：
    1. 模型名称 (model_name)
    2. 领域 (domain)
    3. 样本ID (sample_id)
    4. 指令ID (instruction_id)
    
    Args:
        model_name: 模型名称
        domain: 领域名称
        instruction_id: 指令ID
        evaluation_dir: 评估结果目录
        sample_id: 样本ID（必需，用于精确匹配）
        
    Returns:
        分数字典 {xdrfr, scs, xdrfr_results}，如果不存在则返回None值
    """
    if not sample_id:
        logger.warning(f"sample_id is required for precise matching. model={model_name}, domain={domain}, instruction_id={instruction_id}")
        return {'xdrfr': None, 'scs': None, 'xdrfr_results': None}
    
    # 构建文件路径
    file_name = f"{model_name}_{domain}_results.json"
    file_path = evaluation_dir / "fragments" / file_name
    
    if not file_path.exists():
        # 尝试模糊匹配模型名称
        fragments_dir = evaluation_dir / "fragments"
        if not fragments_dir.exists():
            logger.debug(f"Fragments directory does not exist: {fragments_dir}")
            return {'xdrfr': None, 'scs': None, 'xdrfr_results': None}
        
        domain_pattern = f"*_{domain}_results.json"
        best_match = None
        model_name_normalized = model_name.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
        
        for f in fragments_dir.glob(domain_pattern):
            file_stem = f.stem
            domain_suffix = f"_{domain}_results"
            if file_stem.endswith(domain_suffix):
                file_model_name = file_stem[:-len(domain_suffix)]
                file_model_normalized = file_model_name.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
                
                if model_name_normalized == file_model_normalized:
                    best_match = f
                    break
                elif model_name_normalized in file_model_normalized:
                    if best_match is None:
                        best_match = f
                    elif file_model_normalized.endswith(model_name_normalized):
                        best_match = f
                elif file_model_normalized.endswith(model_name_normalized):
                    best_match = f
                    break
        
        if best_match:
            file_path = best_match
            logger.debug(f"Matched evaluation file: {file_path.name} for model={model_name}, domain={domain}")
        else:
            logger.warning(f"No evaluation file found for model={model_name}, domain={domain}")
            # 尝试从 detailed_results.json 加载
            return _load_from_detailed_results(model_name, domain, instruction_id, sample_id, evaluation_dir)
    
    # 从 fragments 文件加载并精确匹配
    try:
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        instructions = data.get('instructions', [])
        logger.debug(f"Loading from {file_path.name}, found {len(instructions)} instructions")
        
        # 精确匹配4个维度：model_name, domain, sample_id, instruction_id
        for inst in instructions:
            inst_model = inst.get('model', '')
            inst_domain = inst.get('domain', '')
            inst_sample_id = inst.get('sample_id', '')
            inst_instruction_id = inst.get('instruction_id', '')
            
            # 检查 domain 和 sample_id 和 instruction_id 是否匹配
            if (inst_domain != domain or 
                inst_sample_id != sample_id or 
                inst_instruction_id != instruction_id):
                continue
            
            # 检查模型名称是否匹配
            if not _model_name_matches(inst_model, model_name):
                continue
            
            # 找到匹配的指令，提取分数
            metrics = inst.get('metrics', {})
            
            xdrfr = None
            xdrfr_results = None
            xdrfr_metric = metrics.get('xdrfr')
            if xdrfr_metric and xdrfr_metric.get('success', False):
                xdrfr = xdrfr_metric.get('score')
                xdrfr_results = xdrfr_metric.get('details', {}).get('per_question_results', [])
                logger.debug(f"Found xdrfr results: {len(xdrfr_results) if xdrfr_results else 0} results")
            
            scs = None
            scs_metric = metrics.get('style_consistency_score_task2')
            if scs_metric and scs_metric.get('success', False):
                scs = scs_metric.get('score')
            
            if xdrfr is not None or scs is not None:
                logger.info(f"✓ Matched instruction: model={model_name}, domain={domain}, sample_id={sample_id}, instruction_id={instruction_id}")
                return {
                    'xdrfr': xdrfr,
                    'scs': scs,
                    'xdrfr_results': xdrfr_results
                }
        
        logger.warning(f"No matching instruction found: model={model_name}, domain={domain}, sample_id={sample_id}, instruction_id={instruction_id}")
        # 尝试从 detailed_results.json 加载
        return _load_from_detailed_results(model_name, domain, instruction_id, sample_id, evaluation_dir)
        
    except Exception as e:
        logger.warning(f"Failed to load evaluation scores from {file_path}: {e}", exc_info=True)
        # 尝试从 detailed_results.json 加载
        return _load_from_detailed_results(model_name, domain, instruction_id, sample_id, evaluation_dir)


def _model_name_matches(file_model: str, search_model: str) -> bool:
    """检查文件中的模型名称是否匹配搜索的模型名称"""
    file_model_normalized = file_model.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
    search_model_normalized = search_model.replace('-', '_').replace(' ', '_').replace('/', '_').lower()
    
    # 精确匹配
    if file_model_normalized == search_model_normalized:
        return True
    # 检查搜索模型是否在文件模型中（处理前缀情况）
    if search_model_normalized in file_model_normalized:
        return True
    # 检查文件模型是否以搜索模型结尾
    if file_model_normalized.endswith(search_model_normalized):
        return True
    # 检查文件模型是否以搜索模型开头
    if file_model_normalized.startswith(search_model_normalized):
        return True
    return False


def _load_from_detailed_results(model_name: str, domain: str, instruction_id: str, sample_id: str, evaluation_dir: Path) -> Dict[str, Any]:
    """从 detailed_results.json 加载评估结果"""
    detailed_results_file = evaluation_dir / "detailed_results.json"
    if not detailed_results_file.exists():
        return {'xdrfr': None, 'scs': None, 'xdrfr_results': None}
    
    try:
        import json
        with open(detailed_results_file, 'r', encoding='utf-8') as f:
            detailed_data = json.load(f)
        
        all_instructions = detailed_data.get('instructions', [])
        logger.debug(f"Loading from detailed_results.json, found {len(all_instructions)} total instructions")
        
        # 精确匹配4个维度
        for inst in all_instructions:
            inst_model = inst.get('model', '')
            inst_domain = inst.get('domain', '')
            inst_sample_id = inst.get('sample_id', '')
            inst_instruction_id = inst.get('instruction_id', '')
            
            # 检查所有4个维度是否匹配
            if (inst_domain != domain or 
                inst_sample_id != sample_id or 
                inst_instruction_id != instruction_id):
                continue
            
            if not _model_name_matches(inst_model, model_name):
                continue
            
            # 找到匹配的指令
            metrics = inst.get('metrics', {})
            
            xdrfr = None
            xdrfr_results = None
            xdrfr_metric = metrics.get('xdrfr')
            if xdrfr_metric and xdrfr_metric.get('success', False):
                xdrfr = xdrfr_metric.get('score')
                xdrfr_results = xdrfr_metric.get('details', {}).get('per_question_results', [])
            
            scs = None
            scs_metric = metrics.get('style_consistency_score_task2')
            if scs_metric and scs_metric.get('success', False):
                scs = scs_metric.get('score')
            
            if xdrfr is not None or scs is not None:
                logger.info(f"✓ Loaded from detailed_results.json: model={model_name}, domain={domain}, sample_id={sample_id}, instruction_id={instruction_id}")
                return {
                    'xdrfr': xdrfr,
                    'scs': scs,
                    'xdrfr_results': xdrfr_results
                }
        
        logger.warning(f"No matching instruction in detailed_results.json: model={model_name}, domain={domain}, sample_id={sample_id}, instruction_id={instruction_id}")
        return {'xdrfr': None, 'scs': None, 'xdrfr_results': None}
        
    except Exception as e:
        logger.warning(f"Failed to load from detailed_results.json: {e}", exc_info=True)
        return {'xdrfr': None, 'scs': None, 'xdrfr_results': None}


def load_manual_edits(instruction_dir: Path) -> Dict[str, Any]:
    """
    加载手动编辑的历史记录
    
    Args:
        instruction_dir: 指令目录
        
    Returns:
        编辑历史字典
    """
    edits_file = instruction_dir / "manual_edits.json"
    if edits_file.exists():
        try:
            with open(edits_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load manual edits from {edits_file}: {e}")
    
    return {}


def save_manual_edits(instruction_dir: Path, edits: Dict[str, Any]):
    """
    保存手动编辑的历史记录
    
    Args:
        instruction_dir: 指令目录
        edits: 编辑历史字典
    """
    edits_file = instruction_dir / "manual_edits.json"
    try:
        with open(edits_file, 'w', encoding='utf-8') as f:
            json.dump(edits, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save manual edits to {edits_file}: {e}")
        raise


def get_available_models(source_dir: Path) -> List[str]:
    """
    获取所有可用的模型列表
    
    Args:
        source_dir: task2_benchmark目录
        
    Returns:
        模型名称列表
    """
    models = set()
    
    for domain_dir in source_dir.glob('domain_*'):
        if not domain_dir.is_dir():
            continue
        
        for sample_dir in domain_dir.glob('sample_*'):
            if not sample_dir.is_dir():
                continue
            
            instructions_dir = sample_dir / "instructions"
            if not instructions_dir.exists():
                continue
            
            for inst_dir in instructions_dir.glob('inst_*'):
                if not inst_dir.is_dir():
                    continue
                
                # 查找所有模型目录
                for model_dir in inst_dir.glob('model_*'):
                    if model_dir.is_dir():
                        # 去除 "model_" 前缀
                        model_name = model_dir.name.replace('model_', '', 1)
                        models.add(model_name)
    
    return sorted(list(models))


def load_all_instructions(
    source_dir: Path,
    model_name: str = None,
    model_names: List[str] = None,
    filter_manually_modified: bool = False
) -> List[Dict[str, Any]]:
    """
    加载所有指令
    
    Args:
        source_dir: task2_benchmark目录
        model_name: 模型名称，如果为None则使用默认模型
        model_names: 模型名称列表，如果指定则只返回所有模型都存在的指令（多模型筛选）
        filter_manually_modified: 是否只返回手动修改过的指令
        
    Returns:
        指令列表
    """
    instructions = []
    
    # 如果指定了多模型筛选，先找出所有包含这些模型的指令
    if model_names and len(model_names) > 0:
        valid_instructions = set()
        
        for domain_dir in source_dir.glob('domain_*'):
            if not domain_dir.is_dir():
                continue
            
            for sample_dir in domain_dir.glob('sample_*'):
                if not sample_dir.is_dir():
                    continue
                
                instructions_dir = sample_dir / "instructions"
                if not instructions_dir.exists():
                    continue
                
                for inst_dir in instructions_dir.glob('inst_*'):
                    if not inst_dir.is_dir():
                        continue
                    
                    # 检查该指令是否包含所有指定的模型
                    has_all_models = True
                    for m_name in model_names:
                        model_dir = inst_dir / f"model_{m_name}"
                        modified_png = model_dir / "modified.png"
                        if not model_dir.exists() or not modified_png.exists():
                            has_all_models = False
                            break
                    
                    if has_all_models:
                        valid_instructions.add((domain_dir.name, sample_dir.name, inst_dir.name))
        
        instructions_to_process = valid_instructions
    else:
        instructions_to_process = None
    
    for domain_dir in source_dir.glob('domain_*'):
        if not domain_dir.is_dir():
            continue
        
        for sample_dir in domain_dir.glob('sample_*'):
            if not sample_dir.is_dir():
                continue
            
            instructions_dir = sample_dir / "instructions"
            if not instructions_dir.exists():
                continue
            
            # 检查原始渲染图是否存在
            rendered_path = sample_dir / "rendered.png"
            if not rendered_path.exists():
                continue
            
            for inst_dir in instructions_dir.glob('inst_*'):
                if not inst_dir.is_dir():
                    continue
                
                # 如果是多模型筛选模式，检查该指令是否在有效列表中
                if instructions_to_process is not None:
                    if (domain_dir.name, sample_dir.name, inst_dir.name) not in instructions_to_process:
                        continue
                
                # 读取指令文件
                instruction_file = inst_dir / "instruction.txt"
                if not instruction_file.exists():
                    continue
                
                try:
                    with open(instruction_file, 'r', encoding='utf-8') as f:
                        instruction_text = f.read().strip()
                except Exception as e:
                    logger.warning(f"Failed to read instruction from {instruction_file}: {e}")
                    continue
                
                # 读取指令元数据
                metadata_file = inst_dir / "instruction_metadata.json"
                instruction_level = None
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            instruction_level = metadata.get('difficulty_level', None)
                    except Exception as e:
                        logger.warning(f"Failed to read instruction metadata from {metadata_file}: {e}")
                
                # 如果没有元数据，尝试从instruction_id提取
                if not instruction_level:
                    inst_id = inst_dir.name
                    if inst_id.startswith('inst_easy_'):
                        instruction_level = 'Easy'
                    elif inst_id.startswith('inst_medium_'):
                        instruction_level = 'Medium'
                    elif inst_id.startswith('inst_hard_'):
                        instruction_level = 'Hard'
                
                # 检查是否有手动编辑
                manual_edits = load_manual_edits(inst_dir)
                is_manually_modified = len(manual_edits) > 0
                
                if filter_manually_modified and not is_manually_modified:
                    continue
                
                # 对于多模型筛选，使用第一个模型来显示
                display_model_name = None
                if model_names and len(model_names) > 0:
                    display_model_name = model_names[0]
                else:
                    display_model_name = model_name
                
                # 查找模型目录
                model_dir = None
                if display_model_name:
                    candidate_dir = inst_dir / f"model_{display_model_name}"
                    if candidate_dir.exists():
                        model_dir = candidate_dir
                
                if model_dir is None:
                    # 如果没有找到指定模型，查找第一个可用的模型
                    for m_dir in inst_dir.glob('model_*'):
                        if m_dir.is_dir():
                            model_dir = m_dir
                            break
                
                if model_dir is None:
                    continue
                
                # 检查修改后的渲染图是否存在
                modified_png = model_dir / "modified.png"
                if not modified_png.exists():
                    continue
                
                # 计算相对路径
                try:
                    rendered_rel_path = rendered_path.relative_to(source_dir)
                    modified_rel_path = modified_png.relative_to(source_dir)
                except ValueError:
                    logger.warning(f"Path not relative to source_dir: {sample_dir}")
                    continue
                
                # 获取模型名称（去除 "model_" 前缀）
                actual_model_name = model_dir.name.replace('model_', '', 1)
                
                # 对于多模型筛选，添加所有可用模型信息
                available_models_in_instruction = []
                all_models_modified_paths = {}
                
                if model_names and len(model_names) > 0:
                    for m_name in model_names:
                        m_dir = inst_dir / f"model_{m_name}"
                        m_modified_png = m_dir / "modified.png"
                        if m_dir.exists() and m_modified_png.exists():
                            available_models_in_instruction.append(m_name)
                            try:
                                m_modified_rel_path = m_modified_png.relative_to(source_dir)
                                all_models_modified_paths[m_name] = str(m_modified_rel_path).replace('\\', '/')
                            except ValueError:
                                logger.warning(f"Path not relative to source_dir: {m_modified_png}")
                                continue
                
                # 加载评估分数
                scores = {'xdrfr': None, 'scs': None, 'xdrfr_results': None}
                if EVALUATION_DIR and EVALUATION_DIR.exists():
                    scores = get_instruction_scores(actual_model_name, domain_dir.name, inst_dir.name, EVALUATION_DIR, sample_id=sample_dir.name)
                
                instruction_data = {
                    "sample_id": sample_dir.name,
                    "domain": domain_dir.name,
                    "instruction_id": inst_dir.name,
                    "instruction": instruction_text,
                    "instruction_level": instruction_level,
                    "model_name": actual_model_name,
                    "rendered_path": str(rendered_rel_path).replace('\\', '/'),
                    "modified_path": str(modified_rel_path).replace('\\', '/'),
                    "scores": scores,
                    "is_manually_modified": is_manually_modified,
                    "available_models": available_models_in_instruction if available_models_in_instruction else [actual_model_name],
                    "all_models_modified_paths": all_models_modified_paths if all_models_modified_paths else {actual_model_name: str(modified_rel_path).replace('\\', '/')}
                }
                instructions.append(instruction_data)
    
    # 按domain, sample_id, instruction_id排序
    return sorted(instructions, key=lambda x: (x['domain'], x['sample_id'], x['instruction_id']))


@app.route('/')
def index():
    """返回主页面"""
    return render_template('task2_viewer.html')


@app.route('/api/models')
def get_models():
    """获取可用模型列表"""
    try:
        models = get_available_models(SOURCE_DIR)
        return jsonify({
            "models": models,
            "default": models[0] if models else None
        })
    except Exception as e:
        logger.error(f"Error loading models: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/instructions')
def get_instructions():
    """获取指令列表"""
    try:
        # 支持单模型和多模型筛选
        model_name = request.args.get('model', None)
        models_param = request.args.get('models', None)
        
        # 解析多模型参数
        model_names = None
        if models_param:
            model_names = [m.strip() for m in models_param.split(',') if m.strip()]
            model_name = None
        
        filter_manually_modified = request.args.get('manually_modified', 'false').lower() == 'true'
        
        instructions = load_all_instructions(
            SOURCE_DIR,
            model_name=model_name,
            model_names=model_names,
            filter_manually_modified=filter_manually_modified
        )
        
        return jsonify({
            "instructions": instructions,
            "total": len(instructions)
        })
    except Exception as e:
        logger.error(f"Error loading instructions: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/instruction/<domain>/<sample_id>/<instruction_id>')
def get_instruction(domain: str, sample_id: str, instruction_id: str):
    """获取单个指令详情"""
    try:
        model_name = request.args.get('model', None)
        
        sample_dir = SOURCE_DIR / domain / sample_id
        if not sample_dir.exists():
            return jsonify({"error": "Sample not found"}), 404
        
        inst_dir = sample_dir / "instructions" / instruction_id
        if not inst_dir.exists():
            return jsonify({"error": "Instruction not found"}), 404
        
        # 读取指令文件
        instruction_file = inst_dir / "instruction.txt"
        if not instruction_file.exists():
            return jsonify({"error": "Instruction file not found"}), 404
        
        with open(instruction_file, 'r', encoding='utf-8') as f:
            instruction_text = f.read().strip()
        
        # 读取指令元数据
        metadata_file = inst_dir / "instruction_metadata.json"
        instruction_level = None
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    instruction_level = metadata.get('difficulty_level', None)
            except Exception as e:
                logger.warning(f"Failed to read instruction metadata: {e}")
        
        # 读取问题集
        question_set_file = inst_dir / "question_set.json"
        decomposed_questions = []
        if question_set_file.exists():
            try:
                with open(question_set_file, 'r', encoding='utf-8') as f:
                    question_set = json.load(f)
                    decomposed_questions = question_set.get('decomposed_questions', [])
            except Exception as e:
                logger.warning(f"Failed to read question set: {e}")
        
        # 查找模型目录
        model_dir = None
        if model_name:
            candidate_dir = inst_dir / f"model_{model_name}"
            if candidate_dir.exists():
                model_dir = candidate_dir
        
        if model_dir is None:
            # 查找第一个可用的模型
            for m_dir in inst_dir.glob('model_*'):
                if m_dir.is_dir():
                    model_dir = m_dir
                    break
        
        if model_dir is None:
            return jsonify({"error": "Model directory not found"}), 404
        
        # 获取模型名称
        actual_model_name = model_dir.name.replace('model_', '', 1)
        
        # 计算路径
        rendered_path = sample_dir / "rendered.png"
        modified_png = model_dir / "modified.png"
        
        rendered_rel_path = rendered_path.relative_to(SOURCE_DIR)
        modified_rel_path = modified_png.relative_to(SOURCE_DIR)
        
        # 加载评估分数
        scores = {'xdrfr': None, 'scs': None, 'xdrfr_results': None}
        if EVALUATION_DIR and EVALUATION_DIR.exists():
            scores = get_instruction_scores(actual_model_name, domain, instruction_id, EVALUATION_DIR, sample_id=sample_id)
            # 添加调试日志
            if scores.get('xdrfr_results') is None or len(scores.get('xdrfr_results', [])) == 0:
                logger.warning(f"⚠ No xdrfr_results found for model={actual_model_name}, domain={domain}, instruction_id={instruction_id}")
                logger.warning(f"  Scores: xdrfr={scores.get('xdrfr')}, scs={scores.get('scs')}, xdrfr_results={scores.get('xdrfr_results')}")
                logger.warning(f"  Evaluation dir: {EVALUATION_DIR}")
                logger.warning(f"  Model name: {actual_model_name}, Domain: {domain}")
            else:
                logger.info(f"✓ Loaded {len(scores.get('xdrfr_results', []))} xdrfr_results for {actual_model_name}/{domain}/{instruction_id}")
                # 输出第一个结果的详细信息用于调试
                first_result = scores.get('xdrfr_results', [])[0] if scores.get('xdrfr_results') else None
                if first_result:
                    logger.debug(f"  First result: question={first_result.get('question', '')[:80]}..., answer={first_result.get('answer')}")
        else:
            logger.warning(f"⚠ Evaluation directory not set or does not exist: {EVALUATION_DIR}, scores will be None")
        
        # 加载手动编辑历史
        manual_edits = load_manual_edits(inst_dir)
        
        return jsonify({
            "sample_id": sample_id,
            "domain": domain,
            "instruction_id": instruction_id,
            "instruction": instruction_text,
            "instruction_level": instruction_level,
            "decomposed_questions": decomposed_questions,
            "model_name": actual_model_name,
            "rendered_path": str(rendered_rel_path).replace('\\', '/'),
            "modified_path": str(modified_rel_path).replace('\\', '/'),
            "scores": scores,
            "manual_edits": manual_edits
        })
    except Exception as e:
        logger.error(f"Error loading instruction: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/image/rendered/<path:image_path>')
def serve_rendered_image(image_path: str):
    """提供原始渲染图"""
    try:
        image_path = image_path.replace('%2F', '/').replace('%5C', '/')
        full_path = SOURCE_DIR / image_path
        
        try:
            full_path.resolve().relative_to(SOURCE_DIR.resolve())
        except ValueError:
            return jsonify({"error": "Invalid path"}), 403
        
        if not full_path.exists():
            return jsonify({"error": "Image not found"}), 404
        
        return send_file(full_path, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error serving rendered image: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/image/modified/<path:image_path>')
def serve_modified_image(image_path: str):
    """提供修改后的渲染图"""
    try:
        image_path = image_path.replace('%2F', '/').replace('%5C', '/')
        full_path = SOURCE_DIR / image_path
        
        try:
            full_path.resolve().relative_to(SOURCE_DIR.resolve())
        except ValueError:
            return jsonify({"error": "Invalid path"}), 403
        
        if not full_path.exists():
            return jsonify({"error": "Image not found"}), 404
        
        return send_file(full_path, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error serving modified image: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/edits', methods=['POST'])
def save_edits():
    """保存手动编辑"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        domain = data.get('domain')
        sample_id = data.get('sample_id')
        instruction_id = data.get('instruction_id')
        question = data.get('question')
        original_answer = data.get('original_answer')
        modified_answer = data.get('modified_answer')
        
        if not all([domain, sample_id, instruction_id, question, original_answer, modified_answer]):
            return jsonify({"error": "Missing required fields"}), 400
        
        sample_dir = SOURCE_DIR / domain / sample_id
        if not sample_dir.exists():
            return jsonify({"error": "Sample not found"}), 404
        
        inst_dir = sample_dir / "instructions" / instruction_id
        if not inst_dir.exists():
            return jsonify({"error": "Instruction not found"}), 404
        
        # 加载现有编辑历史
        manual_edits = load_manual_edits(inst_dir)
        
        # 添加新的编辑记录
        edit_key = question
        if edit_key not in manual_edits:
            manual_edits[edit_key] = {
                "history": []
            }
        
        edit_record = {
            "timestamp": datetime.now().isoformat(),
            "original_answer": original_answer,
            "modified_answer": modified_answer
        }
        
        manual_edits[edit_key]["history"].append(edit_record)
        manual_edits[edit_key]["latest"] = edit_record
        
        # 保存编辑历史
        save_manual_edits(inst_dir, manual_edits)
        
        logger.info(f"Saved manual edit for {domain}/{sample_id}/{instruction_id}: {question}")
        
        return jsonify({
            "success": True,
            "manual_edits": manual_edits
        })
    except Exception as e:
        logger.error(f"Error saving edits: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def run_server(source_dir: str, host: str = '127.0.0.1', port: int = 5000, evaluation_dir: str = None):
    """
    启动服务器
    
    Args:
        source_dir: task2_benchmark目录路径
        host: 主机地址
        port: 端口号
        evaluation_dir: task2_evaluation目录路径（可选）
    """
    global SOURCE_DIR, EVALUATION_DIR
    SOURCE_DIR = Path(source_dir).resolve()
    
    if not SOURCE_DIR.exists():
        raise ValueError(f"Source directory does not exist: {SOURCE_DIR}")
    
    # 设置评估结果目录
    if evaluation_dir:
        EVALUATION_DIR = Path(evaluation_dir).resolve()
    else:
        # 默认尝试在source_dir的父目录下查找task2_evaluation
        default_eval_dir = SOURCE_DIR.parent / "task2_evaluation"
        if default_eval_dir.exists():
            EVALUATION_DIR = default_eval_dir
        else:
            EVALUATION_DIR = None
            logger.info("Evaluation directory not found, scores will not be displayed")
    
    import webbrowser
    url = f'http://{host}:{port}'
    logger.info(f"Starting web server at {url}")
    logger.info(f"Source directory: {SOURCE_DIR}")
    if EVALUATION_DIR:
        logger.info(f"Evaluation directory: {EVALUATION_DIR}")
    logger.info("Press Ctrl+C to stop the server")
    
    # 延迟打开浏览器，给服务器启动时间
    import threading
    def open_browser():
        import time
        time.sleep(1.5)
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.warning(f"Failed to open browser: {e}")
    
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python web_viewer_app.py <source_dir> [host] [port] [evaluation_dir]")
        sys.exit(1)
    
    source_dir = sys.argv[1]
    host = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
    evaluation_dir = sys.argv[4] if len(sys.argv) > 4 else None
    
    run_server(source_dir, host, port, evaluation_dir)

