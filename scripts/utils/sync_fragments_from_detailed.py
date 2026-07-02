#!/usr/bin/env python3
"""
同步 detailed_results.json 中的数据到分片文件

1. 检查 detailed_results.json 汇总文件，看看哪些模型运行完了哪些数据
2. 检查所有模型的分片文件，看看还有哪些数据是在 detailed_results.json 汇总文件里面，但是没有在分片文件里面的
3. 把 detailed_results.json 汇总文件里面没有在分片文件里面的数据，添加到分片文件里面，没有的分片文件就自己创建然后添加进去
4. 补充进去的数据为0的记录 success 为 false，score 为 none。其他正常数据记录 success 为 true，score 为正常值
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Set
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_detailed_results(detailed_path: Path) -> List[Dict[str, Any]]:
    """加载 detailed_results.json"""
    if not detailed_path.exists():
        logger.error(f"detailed_results.json not found: {detailed_path}")
        return []
    
    try:
        with open(detailed_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            return data.get("samples", [])
        elif isinstance(data, list):
            return data
        else:
            logger.error(f"Unexpected data format in {detailed_path}")
            return []
    except Exception as e:
        logger.error(f"Failed to load detailed_results.json: {e}")
        return []


def load_fragment_files(fragments_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    加载所有分片文件
    
    Returns:
        {sample_key: sample_data} 格式的字典
    """
    if not fragments_dir.exists():
        logger.warning(f"Fragments directory not found: {fragments_dir}")
        return {}
    
    existing = {}
    fragment_files = list(fragments_dir.glob("*_results.json"))
    
    for fragment_file in fragment_files:
        try:
            with open(fragment_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            samples = []
            if isinstance(data, dict):
                samples = data.get("samples", [])
            elif isinstance(data, list):
                samples = data
            
            for sample in samples:
                if not isinstance(sample, dict):
                    continue
                
                sample_id = sample.get("sample_id", "")
                model_name = sample.get("model", "")
                if not sample_id or not model_name:
                    continue
                
                sample_key = f"{sample_id}/{model_name}"
                # 如果已存在，合并指标（保留已有指标，更新新指标）
                if sample_key in existing:
                    existing_metrics = existing[sample_key].get("metrics", {})
                    new_metrics = sample.get("metrics", {})
                    for metric_name, metric_value in new_metrics.items():
                        existing_metrics[metric_name] = metric_value
                    existing[sample_key]["metrics"] = existing_metrics
                else:
                    existing[sample_key] = sample
        
        except Exception as e:
            logger.warning(f"Failed to load fragment file {fragment_file}: {e}")
            continue
    
    return existing


def get_existing_fragment_files(fragments_dir: Path) -> Set[tuple]:
    """
    获取已存在的分片文件对应的 (model, domain) 组合
    通过读取文件内容获取，更可靠
    
    Returns:
        {(model, domain)} 集合
    """
    if not fragments_dir.exists():
        return set()
    
    existing = set()
    fragment_files = list(fragments_dir.glob("*_results.json"))
    
    for fragment_file in fragment_files:
        try:
            with open(fragment_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            samples = []
            if isinstance(data, dict):
                samples = data.get("samples", [])
            elif isinstance(data, list):
                samples = data
            
            # 从样本中提取 model 和 domain（更可靠）
            for sample in samples:
                if not isinstance(sample, dict):
                    continue
                
                model = sample.get("model", "")
                domain = sample.get("domain", "")
                if model and domain:
                    existing.add((model, domain))
                    break  # 一个文件中的所有样本应该有相同的 model 和 domain
        
        except Exception as e:
            logger.warning(f"Failed to load fragment file {fragment_file}: {e}")
            continue
    
    return existing


def get_missing_fragments_by_filename(detailed_by_model_domain: Dict, fragments_dir: Path) -> List[tuple]:
    """
    通过文件名检查缺失的分片文件
    
    Returns:
        [(model, domain, samples, expected_filename)] 列表
    """
    if not fragments_dir.exists():
        return []
    
    fragment_files = list(fragments_dir.glob("*_results.json"))
    existing_filenames = {f.stem.replace('_results', '') for f in fragment_files}
    
    missing = []
    for (model, domain), samples in detailed_by_model_domain.items():
        safe_model = model.replace('/', '_').replace('\\', '_')
        safe_domain = domain.replace('/', '_').replace('\\', '_')
        expected_filename = f"{safe_model}_{safe_domain}"
        
        if expected_filename not in existing_filenames:
            missing.append((model, domain, samples, expected_filename))
    
    return missing


def normalize_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    规范化指标数据：
    - 如果 score 为 0，设置 success=False, score=None
    - 其他正常数据设置 success=True, score 为正常值
    """
    normalized = {}
    
    for metric_name, metric_value in metrics.items():
        if metric_value is None:
            normalized[metric_name] = None
            continue
        
        if not isinstance(metric_value, dict):
            # 如果不是字典，保持原样
            normalized[metric_name] = metric_value
            continue
        
        score = metric_value.get("score")
        success = metric_value.get("success")
        
        # 如果 score 为 0 或 0.0，设置 success=False, score=None
        if score == 0.0 or score == 0:
            normalized[metric_name] = {
                "score": None,
                "success": False,
                "details": metric_value.get("details", {})
            }
            # 如果有 error_message，也保留
            if "error_message" in metric_value:
                normalized[metric_name]["error_message"] = metric_value["error_message"]
        else:
            # 其他正常数据，确保 success=True
            normalized[metric_name] = {
                "score": score,
                "success": True if success is None else success,
                "details": metric_value.get("details", {})
            }
            # 如果有 error_message，也保留
            if "error_message" in metric_value:
                normalized[metric_name]["error_message"] = metric_value["error_message"]
    
    return normalized


def save_fragment_file(fragments_dir: Path, model_name: str, domain: str, samples: List[Dict[str, Any]]):
    """保存分片文件"""
    fragments_dir.mkdir(parents=True, exist_ok=True)
    
    safe_model_name = model_name.replace("/", "_").replace("\\", "_")
    safe_domain = domain.replace("/", "_").replace("\\", "_")
    fragment_file = fragments_dir / f"{safe_model_name}_{safe_domain}_results.json"
    
    try:
        # 如果文件已存在，加载并合并
        existing_samples = []
        if fragment_file.exists():
            try:
                with open(fragment_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    existing_samples = data.get("samples", [])
                elif isinstance(data, list):
                    existing_samples = data
            except Exception as e:
                logger.warning(f"Failed to load existing fragment file {fragment_file}: {e}")
        
        # 合并样本（以新数据为准）
        existing_keys = {f"{s.get('sample_id')}/{s.get('model')}" for s in existing_samples}
        for sample in samples:
            sample_key = f"{sample.get('sample_id')}/{sample.get('model')}"
            if sample_key in existing_keys:
                # 更新已有样本
                for i, existing_sample in enumerate(existing_samples):
                    existing_key = f"{existing_sample.get('sample_id')}/{existing_sample.get('model')}"
                    if existing_key == sample_key:
                        existing_samples[i] = sample
                        break
            else:
                # 添加新样本
                existing_samples.append(sample)
        
        # 保存
        with open(fragment_file, 'w', encoding='utf-8') as f:
            json.dump({"samples": existing_samples}, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(existing_samples)} samples to {fragment_file.name}")
    
    except Exception as e:
        logger.error(f"Failed to save fragment file {fragment_file}: {e}")


def main():
    """主函数"""
    import sys
    
    # 默认路径
    if len(sys.argv) > 1:
        evaluation_dir = Path(sys.argv[1])
    else:
        script_dir = Path(__file__).parent.parent.parent
        evaluation_dir = script_dir / "data" / "task1_evaluation"
    
    detailed_path = evaluation_dir / "detailed_results.json"
    fragments_dir = evaluation_dir / "fragments"
    
    if not detailed_path.exists():
        logger.error(f"detailed_results.json not found: {detailed_path}")
        sys.exit(1)
    
    logger.info("="*60)
    logger.info("Step 1: Loading detailed_results.json")
    logger.info("="*60)
    detailed_samples = load_detailed_results(detailed_path)
    logger.info(f"Loaded {len(detailed_samples)} samples from detailed_results.json")
    
    # 统计模型和领域
    model_domains = defaultdict(set)
    for sample in detailed_samples:
        model = sample.get("model", "")
        domain = sample.get("domain", "")
        if model and domain:
            model_domains[model].add(domain)
    
    logger.info(f"\nModels and domains in detailed_results.json:")
    for model, domains in sorted(model_domains.items()):
        logger.info(f"  {model}: {len(domains)} domains - {sorted(domains)}")
    
    logger.info("\n" + "="*60)
    logger.info("Step 2: Loading fragment files")
    logger.info("="*60)
    fragment_data = load_fragment_files(fragments_dir)
    logger.info(f"Loaded {len(fragment_data)} samples from fragment files")
    
    # 统计分片文件中的模型和领域
    fragment_model_domains = defaultdict(set)
    for sample in fragment_data.values():
        model = sample.get("model", "")
        domain = sample.get("domain", "")
        if model and domain:
            fragment_model_domains[model].add(domain)
    
    logger.info(f"\nModels and domains in fragment files:")
    for model, domains in sorted(fragment_model_domains.items()):
        logger.info(f"  {model}: {len(domains)} domains - {sorted(domains)}")
    
    logger.info("\n" + "="*60)
    logger.info("Step 3: Finding missing model-domain combinations")
    logger.info("="*60)
    
    # 按模型和领域分组 detailed_results.json 中的样本
    detailed_by_model_domain = defaultdict(list)
    for sample in detailed_samples:
        model = sample.get("model", "")
        domain = sample.get("domain", "")
        if model and domain:
            detailed_by_model_domain[(model, domain)].append(sample)
    
    # 方法1：通过文件名检查缺失的分片文件
    missing_by_filename = get_missing_fragments_by_filename(detailed_by_model_domain, fragments_dir)
    
    # 方法2：通过文件内容检查缺失的样本
    existing_fragments = get_existing_fragment_files(fragments_dir)
    
    # 合并两种方法的结果
    samples_by_model_domain = defaultdict(list)
    
    # 首先处理文件名不存在的模型-领域组合
    for model, domain, samples, expected_filename in missing_by_filename:
        logger.info(f"  MISSING FILE: {model} / {domain}: {len(samples)} samples (expected: {expected_filename}_results.json)")
        samples_by_model_domain[(model, domain)] = samples
    
    # 然后检查文件存在但样本缺失的情况
    for (model, domain), samples in sorted(detailed_by_model_domain.items()):
        if (model, domain) in existing_fragments:
            # 文件存在，检查是否有缺失的样本
            detailed_sample_ids = {s.get("sample_id") for s in samples}
            fragment_sample_ids = {
                s.get("sample_id") 
                for s in fragment_data.values() 
                if s.get("model") == model and s.get("domain") == domain
            }
            missing_ids = detailed_sample_ids - fragment_sample_ids
            if missing_ids:
                missing_samples = [s for s in samples if s.get("sample_id") in missing_ids]
                logger.info(f"  MISSING SAMPLES: {model} / {domain}: {len(missing_samples)} samples missing in existing fragment file")
                if (model, domain) not in samples_by_model_domain:
                    samples_by_model_domain[(model, domain)] = []
                samples_by_model_domain[(model, domain)].extend(missing_samples)
    
    if not samples_by_model_domain:
        logger.info("No missing model-domain combinations or samples. All data is synced!")
        return
    
    logger.info(f"\nTotal missing model-domain combinations: {len(samples_by_model_domain)}")
    total_missing_samples = sum(len(samples) for samples in samples_by_model_domain.values())
    logger.info(f"Total missing samples: {total_missing_samples}")
    
    logger.info("\n" + "="*60)
    logger.info("Step 4: Syncing missing samples to fragment files")
    logger.info("="*60)
    
    total_synced = 0
    for (model, domain), samples in sorted(samples_by_model_domain.items()):
        # 规范化指标数据
        normalized_samples = []
        for sample in samples:
            normalized_sample = sample.copy()
            normalized_sample["metrics"] = normalize_metrics(sample.get("metrics", {}))
            normalized_samples.append(normalized_sample)
        
        # 保存到分片文件
        save_fragment_file(fragments_dir, model, domain, normalized_samples)
        total_synced += len(normalized_samples)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Sync completed: {total_synced} samples synced to fragment files")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()

