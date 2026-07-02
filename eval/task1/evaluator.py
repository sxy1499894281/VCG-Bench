"""
任务一评估运行器
"""

import logging
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

# Try to import file locking (Unix/Linux/macOS only)
try:
    import fcntl  # Unix/Linux/macOS
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

from eval.base import MetricRegistry, get_registry, MetricResult
from eval.task1.metrics import (
    ExecutionSuccessRate,
    XMLTokenCount,
    StyleConsistencyScore,
    CodeVQA,
    SigLIPScore
)
from src.llm.client import LLMClient
from src.renderer.drawio_renderer import DrawioRenderer

logger = logging.getLogger(__name__)


def get_model_dir_name(model_name: str) -> str:
    """
    从模型名提取目录名
    对于带斜杠的模型名（如 zai-org/GLM-4.6V），只取最后一个斜杠后的部分
    例如: zai-org/GLM-4.6V -> GLM-4.6V
          Qwen/Qwen3-VL-8B-Instruct -> Qwen3-VL-8B-Instruct
          Pro/deepseek-ai/DeepSeek-V3.2 -> DeepSeek-V3.2
          gemini-3-flash-preview -> gemini-3-flash-preview
    """
    if '/' in model_name:
        return model_name.split('/')[-1]
    return model_name


class Task1Evaluator:
    """任务一评估器"""
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        renderer: Optional[DrawioRenderer] = None,
        enabled_metrics: Optional[List[str]] = None
    ):
        """
        Args:
            llm_client: LLM客户端
            renderer: 渲染器
            enabled_metrics: 启用的指标列表（None表示启用所有）
        """
        self.llm_client = llm_client or LLMClient()
        self.renderer = renderer or DrawioRenderer()
        self.registry = get_registry()
        
        # 检查 API 配置
        self._check_api_config()
        
        # 注册所有指标
        self._register_metrics()
        
        # 设置启用的指标
        if enabled_metrics is not None:
            self._set_enabled_metrics(enabled_metrics)
    
    def _check_api_config(self):
        """检查 API 配置，如果缺失则记录警告"""
        self.has_api_config = bool(
            os.getenv('CUSTOM_API_KEY') and os.getenv('CUSTOM_BASE_URL')
        )
        if not self.has_api_config:
            logger.warning(
                "CUSTOM_API_KEY or CUSTOM_BASE_URL not found. "
                "Metrics requiring LLM API (style_consistency_score, codevqa) will be disabled."
            )
    
    def _register_metrics(self):
        """注册所有指标"""
        self.registry.register(ExecutionSuccessRate(renderer=self.renderer))
        self.registry.register(XMLTokenCount())
        
        # 只有在 API 配置存在时才注册需要 LLM 的指标
        if self.has_api_config:
            self.registry.register(StyleConsistencyScore(llm_client=self.llm_client))
            self.registry.register(CodeVQA(llm_client=self.llm_client))
        else:
            logger.info("Skipping registration of style_consistency_score and codevqa (API config missing)")
        
        self.registry.register(SigLIPScore())
    
    def _set_enabled_metrics(self, enabled_metrics: List[str]):
        """设置启用的指标"""
        all_metrics = self.registry.list_metrics()
        for metric_name in all_metrics:
            if metric_name in enabled_metrics:
                self.registry.enable(metric_name)
            else:
                self.registry.disable(metric_name)
    
    def evaluate_sample(
        self,
        sample_dir: Path,
        model_name: str
    ) -> Dict[str, Any]:
        """
        评估单个样本
        
        Args:
            sample_dir: 样本目录（如 task1_benchmark/domain_ai/sample_0001）
            model_name: 模型名称（如 "gemini"）
        
        Returns:
            评估结果字典
        """
        results = {
            "sample_id": sample_dir.name,
            "domain": sample_dir.parent.name,
            "model": model_name,
            "metrics": {}
        }
        
        # 使用模型名的最后部分作为目录名（处理带斜杠的情况）
        model_dir_name = get_model_dir_name(model_name)
        model_dir = sample_dir / f"model_{model_dir_name}"
        original_image_path = sample_dir / "original.png"
        
        # 准备输入路径
        xml_path = model_dir / "diagram.xml"
        rendered_path = model_dir / "rendered.png"
        
        # 检查执行是否成功
        execution_success = rendered_path.exists()
        
        # 读取 QA 对（如果存在）
        qa_pairs = None
        qa_pairs_path = sample_dir / "qa_pairs.json"
        if qa_pairs_path.exists():
            try:
                with open(qa_pairs_path, 'r', encoding='utf-8') as f:
                    qa_data = json.load(f)
                    qa_pairs = qa_data.get("qa_pairs", [])
            except Exception as e:
                logger.warning(f"Failed to load QA pairs from {qa_pairs_path}: {e}")
        
        # 执行所有启用的指标
        enabled_metrics = self.registry.get_enabled()
        
        for metric_name, metric in enabled_metrics.items():
            try:
                if metric_name == "execution_success_rate":
                    result = metric(xml_path=xml_path, rendered_path=rendered_path)
                    # 更新 execution_success 状态
                    if result.success:
                        execution_success = result.details.get("execution_success", execution_success)
                elif metric_name == "xml_token_count":
                    result = metric(xml_path=xml_path)
                elif metric_name == "style_consistency_score":
                    result = metric(
                        original_image_path=original_image_path,
                        generated_image_path=rendered_path,
                        execution_success=execution_success
                    )
                elif metric_name == "codevqa":
                    if qa_pairs:
                        # Read generated XML content
                        generated_xml = ""
                        if xml_path.exists():
                            generated_xml = xml_path.read_text(encoding='utf-8')
                        else:
                            logger.warning(f"XML file not found: {xml_path}, skipping codevqa")
                            result = MetricResult(
                                metric_name=metric_name,
                                score=None,
                                details={"error": "XML file not found"},
                                success=False,
                                error_message="XML file not found"
                            )
                            results["metrics"][metric_name] = {
                                "score": result.score,
                                "success": result.success,
                                "details": result.details
                            }
                            continue
                        
                        result = metric(
                            generated_xml=generated_xml,
                            qa_pairs=qa_pairs,
                            execution_success=execution_success
                        )
                    else:
                        logger.warning(f"QA pairs not found for {sample_dir.name}, skipping codevqa")
                        result = MetricResult(
                            metric_name=metric_name,
                                score=None,
                                details={"error": "QA pairs not found"},
                                success=False,
                            error_message="QA pairs not found"
                        )
                elif metric_name == "siglip_score":
                    result = metric(
                        original_image_path=original_image_path,
                        rendered_image_path=rendered_path,
                        execution_success=execution_success
                    )
                else:
                    continue
                
                results["metrics"][metric_name] = {
                    "score": result.score,
                    "success": result.success,
                    "details": result.details
                }
            except Exception as e:
                error_str = str(e).lower()
                # 检测 524 错误，保存为 success=False，避免无限制重试和重复计费
                if '524' in error_str or 'error 524' in error_str or 'cloudflare' in error_str or 'timeout occurred' in error_str:
                    logger.error(f"HTTP 524 Cloudflare timeout error when evaluating {metric_name} for {sample_dir}: {e}")
                    logger.error("Saving result as success=False. Will retry on next run, but please check API server status first.")
                    results["metrics"][metric_name] = {
                        "score": None,
                        "success": False,
                        "details": {
                            "error": str(e),
                            "error_type": "524_timeout",
                            "message": "HTTP 524 Cloudflare timeout - server may still be processing request"
                        },
                        "error_message": f"HTTP 524 Cloudflare timeout: {e}"
                    }
                else:
                    logger.error(f"Error evaluating {metric_name} for {sample_dir}: {e}")
                    # 其他错误保存为None，后面重新运行再更新
                    results["metrics"][metric_name] = None
        
        return results
    
    def evaluate_all(
        self,
        benchmark_dir: Path,
        output_dir: Path,
        models: Optional[List[str]] = None,
        domain_filter: Optional[List[str]] = None
    ):
        """
        评估所有样本（支持增量评估）
        
        Args:
            benchmark_dir: task1_benchmark目录
            output_dir: 输出目录
            models: 要评估的模型列表（None表示评估所有模型）
            domain_filter: 要评估的领域列表（None表示评估所有领域，如 ['domain_academic_domain_architecture', 'domain_business_domain_product']）
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建分片文件目录
        fragments_dir = output_dir / "fragments"
        fragments_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载已有结果（从分片文件中加载）
        existing_results = self._load_existing_results(output_dir)
        
        all_results = []
        
        # 确定要处理的领域
        if domain_filter:
            # 只处理指定的领域
            domain_dirs = []
            for domain_name in domain_filter:
                # 支持两种格式：带 domain_ 前缀或不带
                if not domain_name.startswith("domain_"):
                    domain_name = f"domain_{domain_name}"
                domain_path = benchmark_dir / domain_name
                if domain_path.exists() and domain_path.is_dir():
                    domain_dirs.append(domain_path)
                else:
                    logger.warning(f"Domain '{domain_name}' not found, skipping")
            domain_dirs = sorted(domain_dirs)
        else:
            # 处理所有领域
            domain_dirs = sorted(benchmark_dir.glob("domain_*"))
        
        logger.info(f"Processing {len(domain_dirs)} domains: {[d.name for d in domain_dirs]}")
        
        # 统计总样本数（用于显示进度）
        total_samples = 0
        for domain_dir in domain_dirs:
            total_samples += len(list(domain_dir.glob("sample_*")))
        logger.info(f"Total samples to process: {total_samples}")
        
        current_sample_index = 0
        
        # 遍历所有domain
        for domain_index, domain_dir in enumerate(domain_dirs, 1):
            domain = domain_dir.name
            sample_dirs = sorted(domain_dir.glob("sample_*"))
            logger.info(f"[{domain_index}/{len(domain_dirs)}] Processing domain: {domain} ({len(sample_dirs)} samples)")
            
            # 遍历所有样本
            for sample_index, sample_dir in enumerate(sample_dirs, 1):
                sample_id = sample_dir.name
                current_sample_index += 1
                logger.info(f"[{domain_index}/{len(domain_dirs)}] [{sample_index}/{len(sample_dirs)}] [{current_sample_index}/{total_samples}] Processing sample: {domain}/{sample_id}")
                
                # 确定要评估的模型
                if models is None:
                    model_dirs = list(sample_dir.glob("model_*"))
                    model_names = [d.name.replace("model_", "") for d in model_dirs]
                else:
                    model_names = models
                
                # 评估每个模型
                for model_name in model_names:
                    # 使用模型名的最后部分作为目录名（处理带斜杠的情况）
                    model_dir_name = get_model_dir_name(model_name)
                    model_dir = sample_dir / f"model_{model_dir_name}"
                    if not model_dir.exists():
                        logger.warning(f"Model directory not found: {model_dir}")
                        continue
                    
                    # 检查是否已有结果（只从分片文件加载，不从 detailed_results.json 加载）
                    sample_key = f"{domain}/{sample_id}/{model_name}"
                    existing_metrics = existing_results.get(sample_key, {})

                    # ========================================
                    # 第一步：数据一致性检查（优先级最高）
                    # 检查是否存在数据错乱，如果有则清空所有metrics
                    # ========================================
                    data_corrupted = False

                    # 尝试从多个metric中检查路径（优先级从高到低）
                    # 1. execution_success_rate（总是存在，因为它只需要检查文件存在性）
                    # 2. xml_token_count（只要XML存在就会评估）
                    # 3. style_consistency_score（需要PNG渲染成功才有）
                    # 4. codevqa（需要PNG渲染成功才有）

                    check_path = None
                    check_metric_name = None

                    # 优先检查execution_success_rate
                    if 'execution_success_rate' in existing_metrics:
                        existing_esr = existing_metrics['execution_success_rate']
                        if isinstance(existing_esr, dict) and existing_esr.get('details'):
                            details = existing_esr['details']
                            check_path = details.get('xml_path') or details.get('rendered_path')
                            if check_path:
                                check_metric_name = 'execution_success_rate'

                    # 如果没有execution_success_rate，检查xml_token_count
                    if not check_path and 'xml_token_count' in existing_metrics:
                        existing_xtc = existing_metrics['xml_token_count']
                        if isinstance(existing_xtc, dict) and existing_xtc.get('details'):
                            details = existing_xtc['details']
                            check_path = details.get('xml_path')
                            if check_path:
                                check_metric_name = 'xml_token_count'

                    # 如果没有xml_token_count，检查style_consistency_score
                    if not check_path and 'style_consistency_score' in existing_metrics:
                        existing_scs = existing_metrics['style_consistency_score']
                        if isinstance(existing_scs, dict) and existing_scs.get('details'):
                            details = existing_scs['details']
                            check_path = details.get('original_image') or details.get('generated_image')
                            if check_path:
                                check_metric_name = 'style_consistency_score'

                    # 如果有路径可以检查，进行数据一致性验证
                    if check_path and 'domain_' in check_path and 'sample_' in check_path:
                        # 从路径中提取domain和sample_id
                        path_parts = check_path.split('/')
                        path_domain = None
                        path_sample_id = None
                        for part in path_parts:
                            if part.startswith('domain_'):
                                path_domain = part
                            elif part.startswith('sample_'):
                                path_sample_id = part

                        # 检查domain和sample_id是否都匹配
                        if path_domain and path_sample_id:
                            if path_domain != domain or path_sample_id != sample_id:
                                # 检测到数据错乱
                                logger.warning(
                                    f"[{domain}/{sample_id}] ⚠️  DATA CORRUPTION DETECTED! "
                                    f"Metric '{check_metric_name}' contains wrong path. "
                                    f"Expected: {domain}/{sample_id}, Found in path: {path_domain}/{path_sample_id}. "
                                    f"This means all metrics are from the wrong sample!"
                                )
                                logger.warning(
                                    f"[{domain}/{sample_id}] 🔄 AUTOMATIC FIX: Clearing all corrupted metrics and re-evaluating from scratch."
                                )
                                corrupted_metrics = list(existing_metrics.keys())
                                existing_metrics.clear()
                                logger.info(f"[{domain}/{sample_id}] Cleared {len(corrupted_metrics)} corrupted metrics: {corrupted_metrics}")
                                data_corrupted = True

                    # ========================================
                    # 第二步：检查是否所有启用的指标都已评估且成功
                    # 只有在数据一致性检查通过后才进行
                    # ========================================
                    enabled_metrics = self.registry.get_enabled()
                    all_metrics_evaluated = True
                    for metric_name in enabled_metrics.keys():
                        if metric_name not in existing_metrics or existing_metrics[metric_name] is None:
                            logger.info(f"[{domain}/{sample_id}] Metric '{metric_name}' not found or None for {sample_id}/{model_name}, will evaluate")
                            all_metrics_evaluated = False
                            break
                        # 检查结果是否有效（必须成功且有有效的分数）
                        existing_result = existing_metrics[metric_name]
                        if not (isinstance(existing_result, dict) and existing_result.get("score") is not None):
                            logger.info(f"[{domain}/{sample_id}] Metric '{metric_name}' invalid (not dict or score is None) for {sample_id}/{model_name}, will evaluate")
                            all_metrics_evaluated = False
                            break
                        # 检查是否成功（如果 success=False，需要重试）
                        # 处理 success 可能是布尔值、字符串或缺失的情况
                        success_value = existing_result.get("success")
                        if success_value is None:
                            # 如果 success 字段不存在，默认认为成功（向后兼容）
                            success_value = True
                        elif isinstance(success_value, str):
                            # 如果是字符串，转换为布尔值
                            success_value = success_value.lower() in ('true', '1', 'yes')
                        elif not isinstance(success_value, bool):
                            # 如果是其他类型，尝试转换为布尔值
                            success_value = bool(success_value)

                        if not success_value:
                            logger.warning(f"[{domain}/{sample_id}] Metric '{metric_name}' for {sample_id}/{model_name} failed previously (success={existing_result.get('success')}), will retry")
                            all_metrics_evaluated = False
                            break
                        else:
                            logger.debug(f"[{domain}/{sample_id}] Metric '{metric_name}' for {sample_id}/{model_name} is valid (success={success_value}, score={existing_result.get('score')})")

                    if all_metrics_evaluated:
                        # 所有指标都已评估，直接跳过该样本
                        logger.info(f"[{domain}/{sample_id}] Sample {sample_id}/{model_name} already fully evaluated, skipping")
                        # 从已有结果中构建结果字典（用于后续CSV生成）
                        result = {
                            "sample_id": sample_id,
                            "domain": domain,
                            "model": model_name,
                            "metrics": existing_metrics
                        }
                        all_results.append(result)
                        
                        # 检查分片文件是否存在，如果不存在则保存（即使跳过了评估）
                        # 这样可以确保从 detailed_results.json 加载的数据也会被保存到分片文件
                        safe_model_name = model_name.replace("/", "_").replace("\\", "_")
                        safe_domain = domain.replace("/", "_").replace("\\", "_")
                        fragment_file = output_dir / "fragments" / f"{safe_model_name}_{safe_domain}_results.json"
                        if not fragment_file.exists():
                            logger.info(f"[{domain}/{sample_id}] Fragment file not found, saving skipped sample to fragment file")
                            self._save_single_result(result, output_dir, model_name, domain)
                        continue
                    
                    # 增量评估：只评估缺失的指标
                    logger.info(f"[{domain}/{sample_id}] Evaluating {sample_id} - {model_name}")
                    try:
                        result = self.evaluate_sample_incremental(
                            sample_dir, 
                            model_name, 
                            existing_metrics
                        )
                        all_results.append(result)
                        
                        # 实时保存：每个样本评估完成后立即保存到分片文件（按模型-领域分组）
                        self._save_single_result(result, output_dir, model_name, domain)
                        logger.info(f"[{domain}/{sample_id}] Saved result for {sample_id}/{model_name} to fragment file")
                    except Exception as e:
                        logger.error(f"[{domain}/{sample_id}] Error evaluating {sample_id}/{model_name}: {e}", exc_info=True)
                        # 即使出错也继续处理下一个样本
                        continue
        
        # 最后批量保存CSV结果（重新生成所有CSV文件，确保包含所有结果）
        logger.info("Generating CSV files from all saved results...")
        self._regenerate_csv_results(output_dir)
        
        logger.info(f"Evaluation completed. Results saved to {output_dir}")
    
    def _load_existing_results(self, output_dir: Path, model: Optional[str] = None, domain: Optional[str] = None) -> Dict[str, Dict]:
        """
        加载已有结果（从分片文件中加载）
        
        Args:
            output_dir: 输出目录
            model: 模型名称（可选，用于过滤）
            domain: 领域名称（可选，用于过滤）
        
        Returns:
            {sample_key: {metric_name: result}} 格式的字典
        """
        fragments_dir = output_dir / "fragments"
        existing = {}
        
        # 从分片文件加载
        if fragments_dir.exists():
            # 构建文件名模式（使用 safe 版本，与保存时保持一致）
            if model and domain:
                # 加载特定的模型-领域分片
                safe_model_name = model.replace("/", "_").replace("\\", "_")
                safe_domain = domain.replace("/", "_").replace("\\", "_")
                fragment_file = fragments_dir / f"{safe_model_name}_{safe_domain}_results.json"
                fragment_files = [fragment_file] if fragment_file.exists() else []
            elif model:
                # 加载特定模型的所有领域分片
                safe_model_name = model.replace("/", "_").replace("\\", "_")
                pattern = f"{safe_model_name}_*_results.json"
                fragment_files = list(fragments_dir.glob(pattern))
            elif domain:
                # 加载特定领域的所有模型分片
                safe_domain = domain.replace("/", "_").replace("\\", "_")
                pattern = f"*_{safe_domain}_results.json"
                fragment_files = list(fragments_dir.glob(pattern))
            else:
                # 加载所有分片文件
                fragment_files = list(fragments_dir.glob("*_results.json"))
            
            for fragment_file in fragment_files:
                try:
                    with open(fragment_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 处理不同的数据格式
                    samples = []
                    if isinstance(data, dict):
                        samples = data.get("samples", [])
                    elif isinstance(data, list):
                        samples = data
                    else:
                        logger.warning(f"Unexpected data format in {fragment_file}, expected dict or list")
                        continue
                    
                    # 添加到已有结果中
                    for result in samples:
                        if not isinstance(result, dict):
                            continue
                        
                        sample_id = result.get("sample_id", "")
                        model_name = result.get("model", "")
                        domain_name = result.get("domain", "")
                        if not sample_id or not model_name:
                            continue

                        sample_key = f"{domain_name}/{sample_id}/{model_name}"
                        # 如果已有结果，合并指标（保留已有指标，更新新指标）
                        if sample_key in existing:
                            existing_metrics = existing[sample_key]
                            new_metrics = result.get("metrics", {})
                            for metric_name, metric_value in new_metrics.items():
                                existing_metrics[metric_name] = metric_value
                        else:
                            existing[sample_key] = result.get("metrics", {})
                except Exception as e:
                    logger.warning(f"Failed to load fragment file {fragment_file}: {e}")
                    continue
        
        # 只从分片文件加载，不从 detailed_results.json 加载
        # 没有分片文件就说明需要运行
        fragments_count = len([f for f in fragments_dir.glob("*_results.json")] if fragments_dir.exists() else [])
        logger.info(f"Loaded {len(existing)} existing results from {fragments_count} fragment files")
        return existing
    
    def evaluate_sample_incremental(
        self,
        sample_dir: Path,
        model_name: str,
        existing_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        增量评估单个样本，只评估缺失的指标
        
        Args:
            sample_dir: 样本目录
            model_name: 模型名称
            existing_metrics: 已有指标结果
        
        Returns:
            评估结果字典
        """
        results = {
            "sample_id": sample_dir.name,
            "domain": sample_dir.parent.name,
            "model": model_name,
            "metrics": {}
        }
        
        # 获取启用的指标
        enabled_metrics = self.registry.get_enabled()
        
        # 确定需要评估的指标
        metrics_to_evaluate = []
        for metric_name, metric in enabled_metrics.items():
            # 检查是否已有结果
            if metric_name in existing_metrics and existing_metrics[metric_name] is not None:
                # 检查结果是否有效（有 score 字段且不为 None）
                existing_result = existing_metrics[metric_name]
                if isinstance(existing_result, dict) and existing_result.get("score") is not None:
                    # 检查是否成功（如果 success=False，需要重新评估）
                    domain = sample_dir.parent.name
                    sample_id = sample_dir.name
                    if not existing_result.get("success", True):
                        logger.info(f"[{domain}/{sample_id}] Metric '{metric_name}' failed previously (success=False), will re-evaluate")
                        metrics_to_evaluate.append((metric_name, metric))
                    else:
                        logger.info(f"[{domain}/{sample_id}] Metric '{metric_name}' already evaluated, reusing result")
                        results["metrics"][metric_name] = existing_result
                    continue
            
            domain = sample_dir.parent.name
            sample_id = sample_dir.name
            logger.info(f"[{domain}/{sample_id}] Metric '{metric_name}' not found or invalid, will evaluate")
            metrics_to_evaluate.append((metric_name, metric))
        
        # 评估缺失的指标
        domain = sample_dir.parent.name
        sample_id = sample_dir.name
        if not metrics_to_evaluate:
            logger.info(f"[{domain}/{sample_id}] All metrics already evaluated for {sample_id}/{model_name}")
            return results
        
        logger.info(f"[{domain}/{sample_id}] Evaluating {len(metrics_to_evaluate)} metrics for {sample_id}/{model_name}")
        
        # 准备输入路径（与 evaluate_sample 相同）
        # 使用模型名的最后部分作为目录名（处理带斜杠的情况）
        model_dir_name = get_model_dir_name(model_name)
        model_dir = sample_dir / f"model_{model_dir_name}"
        original_image_path = sample_dir / "original.png"
        xml_path = model_dir / "diagram.xml"
        rendered_path = model_dir / "rendered.png"
        
        # 检查执行是否成功
        execution_success = rendered_path.exists()
        
        # 读取 QA 对（如果存在）
        qa_pairs = None
        qa_pairs_path = sample_dir / "qa_pairs.json"
        if qa_pairs_path.exists():
            try:
                with open(qa_pairs_path, 'r', encoding='utf-8') as f:
                    qa_data = json.load(f)
                    qa_pairs = qa_data.get("qa_pairs", [])
            except Exception as e:
                logger.warning(f"Failed to load QA pairs from {qa_pairs_path}: {e}")
        
        # 评估缺失的指标
        for metric_index, (metric_name, metric) in enumerate(metrics_to_evaluate, 1):
            logger.info(f"[{domain}/{sample_id}] [{metric_index}/{len(metrics_to_evaluate)}] Evaluating metric: {metric_name}")
            try:
                if metric_name == "execution_success_rate":
                    result = metric(xml_path=xml_path, rendered_path=rendered_path)
                    if result.success:
                        execution_success = result.details.get("execution_success", execution_success)
                elif metric_name == "xml_token_count":
                    result = metric(xml_path=xml_path)
                elif metric_name == "style_consistency_score":
                    result = metric(
                        original_image_path=original_image_path,
                        generated_image_path=rendered_path,
                        execution_success=execution_success
                    )
                elif metric_name == "codevqa":
                    if qa_pairs:
                        # Read generated XML content
                        generated_xml = ""
                        if xml_path.exists():
                            generated_xml = xml_path.read_text(encoding='utf-8')
                        else:
                            logger.warning(f"XML file not found: {xml_path}, skipping codevqa")
                            result = MetricResult(
                                metric_name=metric_name,
                                score=None,
                                details={"error": "XML file not found"},
                                success=False,
                                error_message="XML file not found"
                            )
                            results["metrics"][metric_name] = {
                                "score": result.score,
                                "success": result.success,
                                "details": result.details
                            }
                            continue
                        
                        result = metric(
                            generated_xml=generated_xml,
                            qa_pairs=qa_pairs,
                            execution_success=execution_success
                        )
                    else:
                        logger.warning(f"QA pairs not found for {sample_dir.name}, skipping codevqa")
                        result = MetricResult(
                            metric_name=metric_name,
                                score=None,
                                details={"error": "QA pairs not found"},
                                success=False,
                            error_message="QA pairs not found"
                        )
                elif metric_name == "siglip_score":
                    result = metric(
                        original_image_path=original_image_path,
                        rendered_image_path=rendered_path,
                        execution_success=execution_success
                    )
                else:
                    continue
                
                results["metrics"][metric_name] = {
                    "score": result.score,
                    "success": result.success,
                    "details": result.details
                }
            except Exception as e:
                error_str = str(e).lower()
                # 检测 524 错误，保存为 success=False，避免无限制重试和重复计费
                if '524' in error_str or 'error 524' in error_str or 'cloudflare' in error_str or 'timeout occurred' in error_str:
                    logger.error(f"HTTP 524 Cloudflare timeout error when evaluating {metric_name} for {sample_dir}: {e}")
                    logger.error("Saving result as success=False. Will retry on next run, but please check API server status first.")
                    results["metrics"][metric_name] = {
                        "score": None,
                        "success": False,
                        "details": {
                            "error": str(e),
                            "error_type": "524_timeout",
                            "message": "HTTP 524 Cloudflare timeout - server may still be processing request"
                        },
                        "error_message": f"HTTP 524 Cloudflare timeout: {e}"
                    }
                else:
                    logger.error(f"Error evaluating {metric_name} for {sample_dir}: {e}")
                    # 其他错误保存为None，后面重新运行再更新
                    results["metrics"][metric_name] = None
        
        return results
    
    def _save_single_result(
        self,
        result: Dict[str, Any],
        output_dir: Path,
        model_name: str,
        domain: str
    ):
        """
        实时保存单个样本的评估结果到分片文件（按模型-领域分组，避免并发写入竞争）
        
        Args:
            result: 单个样本的评估结果
            output_dir: 输出目录
            model_name: 模型名称
            domain: 领域名称
        """
        fragments_dir = output_dir / "fragments"
        fragments_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建分片文件名：{model}_{domain}_results.json
        # 清理模型名和领域名中的特殊字符（用于文件名）
        safe_model_name = model_name.replace("/", "_").replace("\\", "_")
        safe_domain = domain.replace("/", "_").replace("\\", "_")
        fragment_file = fragments_dir / f"{safe_model_name}_{safe_domain}_results.json"
        
        # 原子写入分片文件（不需要文件锁，因为每个进程只写自己的文件）
        temp_path = fragment_file.with_suffix('.tmp')
        max_retries = 3
        retry_delay = 0.1  # 100ms
        
        for attempt in range(max_retries):
            try:
                # 加载已有结果（该模型-领域的分片文件）
                all_results = []
                if fragment_file.exists():
                    try:
                        with open(fragment_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, dict):
                            all_results = data.get("samples", [])
                        elif isinstance(data, list):
                            all_results = data
                    except Exception as e:
                        logger.warning(f"Failed to load existing fragment file {fragment_file}: {e}, starting fresh")
                        all_results = []
                
                # 查找是否已有该样本的结果
                sample_key = f"{result.get('domain', '')}/{result['sample_id']}/{result['model']}"
                found = False
                for i, existing_result in enumerate(all_results):
                    existing_key = f"{existing_result.get('domain', '')}/{existing_result.get('sample_id')}/{existing_result.get('model')}"
                    if existing_key == sample_key:
                        # 更新已有结果：合并指标（保留已有指标，只更新/添加新指标）
                        existing_metrics = existing_result.get("metrics", {})
                        new_metrics = result.get("metrics", {})
                        # 只更新 new_metrics 中存在的指标，保留 existing_metrics 中的其他指标
                        for metric_name, metric_value in new_metrics.items():
                            existing_metrics[metric_name] = metric_value
                        all_results[i]["metrics"] = existing_metrics
                        # 保留其他字段（如 domain）
                        if "domain" in result:
                            all_results[i]["domain"] = result["domain"]
                        found = True
                        break
                
                # 如果没找到，添加新结果
                if not found:
                    all_results.append(result)
                
                # 写入临时文件
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump({"samples": all_results}, f, indent=2, ensure_ascii=False)
                
                # 原子替换
                temp_path.replace(fragment_file)
                
                logger.debug(f"Saved result to fragment file: {fragment_file}")
                break  # 成功，退出重试循环
                
            except (IOError, OSError, json.JSONEncodeError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to save result to fragment (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                    time.sleep(retry_delay * (attempt + 1))  # 指数退避
                    # 清理临时文件（如果存在）
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except:
                            pass
                else:
                    logger.error(f"Failed to save result to fragment after {max_retries} attempts: {e}", exc_info=True)
                    # 清理临时文件
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except:
                            pass
                    raise
    
    def _merge_fragment_files(self, output_dir: Path) -> List[Dict[str, Any]]:
        """
        合并所有分片文件，生成完整的结果列表
        
        Args:
            output_dir: 输出目录
        
        Returns:
            合并后的所有结果列表
        """
        fragments_dir = output_dir / "fragments"
        all_results = []
        seen_keys = set()
        
        if not fragments_dir.exists():
            logger.warning(f"Fragments directory not found: {fragments_dir}")
            return all_results
        
        # 加载所有分片文件
        fragment_files = list(fragments_dir.glob("*_results.json"))
        logger.info(f"Merging {len(fragment_files)} fragment files...")
        
        for fragment_file in fragment_files:
            try:
                with open(fragment_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                samples = []
                if isinstance(data, dict):
                    samples = data.get("samples", [])
                elif isinstance(data, list):
                    samples = data
                else:
                    logger.warning(f"Unexpected data format in {fragment_file}")
                    continue
                
                # 合并样本（避免重复）
                for result in samples:
                    if not isinstance(result, dict):
                        continue
                    
                    sample_id = result.get("sample_id", "")
                    model_name = result.get("model", "")
                    domain_name = result.get("domain", "")
                    if not sample_id or not model_name:
                        continue

                    sample_key = f"{domain_name}/{sample_id}/{model_name}"
                    if sample_key in seen_keys:
                        # 如果已存在，合并指标（保留已有指标，更新新指标）
                        for i, existing_result in enumerate(all_results):
                            existing_key = f"{existing_result.get('domain', '')}/{existing_result.get('sample_id')}/{existing_result.get('model')}"
                            if existing_key == sample_key:
                                existing_metrics = existing_result.get("metrics", {})
                                new_metrics = result.get("metrics", {})
                                for metric_name, metric_value in new_metrics.items():
                                    existing_metrics[metric_name] = metric_value
                                all_results[i]["metrics"] = existing_metrics
                                # 更新其他字段
                                if "domain" in result:
                                    all_results[i]["domain"] = result["domain"]
                                break
                    else:
                        # 新样本，直接添加
                        all_results.append(result)
                        seen_keys.add(sample_key)
            except Exception as e:
                logger.warning(f"Failed to merge fragment file {fragment_file}: {e}")
                continue
        
        logger.info(f"Merged {len(all_results)} unique results from {len(fragment_files)} fragment files")
        return all_results
    
    def _regenerate_csv_results(self, output_dir: Path):
        """
        从分片文件合并后重新生成所有CSV文件（以及可选的合并后的 detailed_results.json）
        这个方法在所有样本评估完成后调用，确保CSV文件包含所有结果
        
        Args:
            output_dir: 输出目录
        """
        # 合并所有分片文件
        all_results = self._merge_fragment_files(output_dir)
        
        if not all_results:
            logger.warning("No results found in fragment files, skipping CSV generation")
            return
        
        # 生成合并后的 detailed_results.json（从所有分片文件合并生成）
        # 包含 success 字段用于后续清理
        try:
            json_path = output_dir / "detailed_results.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({"samples": all_results}, f, indent=2, ensure_ascii=False)
            logger.info(f"Generated merged detailed_results.json with {len(all_results)} results (includes success field for cleanup)")
        except Exception as e:
            logger.warning(f"Failed to generate merged detailed_results.json: {e}")
        
        # 生成CSV
        try:
            self._save_csv_results(all_results, output_dir)
            logger.info("CSV files generated successfully")
        except Exception as e:
            logger.error(f"Failed to regenerate CSV files: {e}", exc_info=True)
    
    def _save_results(
        self, 
        results: List[Dict[str, Any]], 
        output_dir: Path,
        existing_results: Optional[Dict[str, Dict]] = None
    ):
        """保存评估结果（合并已有结果）"""
        # 合并已有结果
        if existing_results:
            # 将新结果合并到已有结果中
            for result in results:
                sample_key = f"{result.get('domain', '')}/{result['sample_id']}/{result['model']}"
                if sample_key in existing_results:
                    # 合并指标
                    existing_metrics = existing_results[sample_key]
                    new_metrics = result.get("metrics", {})
                    existing_metrics.update(new_metrics)
                    result["metrics"] = existing_metrics
        
        # 读取所有已有结果（用于CSV生成，确保包含所有模型）
        json_path = output_dir / "detailed_results.json"
        all_existing_samples = []
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    all_existing_samples = data.get("samples", [])
                elif isinstance(data, list):
                    all_existing_samples = data
            except Exception as e:
                logger.warning(f"Failed to load existing JSON for CSV generation: {e}")
        
        # 构建包含所有模型的结果列表（用于JSON和CSV）
        # 创建新结果的映射
        new_results_map = {f"{r.get('domain', '')}/{r['sample_id']}/{r['model']}": r for r in results}
        # 合并已有结果（排除已被新结果覆盖的）
        all_results = []
        for existing_sample in all_existing_samples:
            sample_key = f"{existing_sample.get('domain', '')}/{existing_sample.get('sample_id')}/{existing_sample.get('model')}"
            if sample_key not in new_results_map:
                all_results.append(existing_sample)
        # 添加新结果
        all_results.extend(results)
        
        # 保存JSON格式的详细结果（原子写入）- 包含所有模型
        temp_path = json_path.with_suffix('.tmp')
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump({"samples": all_results}, f, indent=2, ensure_ascii=False)
        temp_path.replace(json_path)  # 原子替换
        
        # 保存CSV格式的汇总结果（包含所有已有模型）
        self._save_csv_results(all_results, output_dir)
    
    def _save_csv_results(self, results: List[Dict[str, Any]], output_dir: Path):
        """保存CSV格式的结果（包含所有已有模型）"""
        # 展开所有结果到DataFrame
        rows = []
        for result in results:
            row = {
                "sample_id": result["sample_id"],
                "domain": result["domain"],
                "model": result["model"]
            }
            
            # 添加每个指标的分数
            for metric_name, metric_result in result["metrics"].items():
                if isinstance(metric_result, dict) and "score" in metric_result:
                    row[metric_name] = metric_result["score"]
                    # 添加详细信息（如果需要）
                    if "mean_iou" in metric_result.get("details", {}):
                        row[f"{metric_name}_mean_iou"] = metric_result["details"]["mean_iou"]
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # 只保存所有模型的对比结果（不保存按模型分组的 CSV）
        all_models_path = output_dir / "all_models_comparison.csv"
        df.to_csv(all_models_path, index=False, encoding='utf-8')
        
        # 保存统计摘要（只保存汇总的统计，不保存按模型分组的）
        self._save_summary_statistics(df, output_dir)
        
        # CodeVQA 按问题类型分层统计（评估模型在不同类型问题上的表现）
        self._save_codevqa_by_question_type_statistics(results, output_dir)
        
        # SCS 按维度分层统计（评估模型在不同维度上的表现）
        self._save_scs_by_dimension_statistics(results, output_dir)
    
    def _save_summary_statistics(self, df: pd.DataFrame, output_dir: Path):
        """保存统计摘要（所有模型的汇总统计）"""
        # 计算所有模型的汇总统计
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            logger.warning("No numeric columns found for summary statistics")
            return
        
        # 按模型分组统计
        summary_rows = []
        for model in df["model"].unique():
            model_df = df[df["model"] == model]
            summary_row = {"model": model}
            for col in numeric_cols:
                summary_row[f"{col}_mean"] = model_df[col].mean()
                summary_row[f"{col}_median"] = model_df[col].median()
                summary_row[f"{col}_std"] = model_df[col].std()
                summary_row[f"{col}_min"] = model_df[col].min()
                summary_row[f"{col}_max"] = model_df[col].max()
                summary_row[f"{col}_count"] = len(model_df[model_df[col].notna()])
            summary_rows.append(summary_row)
        
        summary_df = pd.DataFrame(summary_rows)
        summary_df = summary_df.round(3)
        
        # 只保存汇总的统计文件
        summary_path = output_dir / "all_models_summary_statistics.csv"
        summary_df.to_csv(summary_path, index=False, encoding='utf-8')
    
    def _save_codevqa_by_question_type_statistics(self, results: List[Dict[str, Any]], output_dir: Path):
        """
        保存 CodeVQA 按问题类型分层的统计（评估模型在不同类型问题上的表现）
        
        Args:
            results: 所有评估结果列表
            output_dir: 输出目录
        """
        # 提取所有 CodeVQA 的问题级别结果
        codevqa_rows = []
        
        for result in results:
            model = result.get("model", "unknown")
            sample_id = result.get("sample_id", "unknown")
            domain = result.get("domain", "unknown")
            
            # 获取 codevqa 指标的结果
            codevqa_metric = result.get("metrics", {}).get("codevqa")
            if not codevqa_metric or not isinstance(codevqa_metric, dict):
                continue
            
            # 获取 per_question_results
            details = codevqa_metric.get("details", {})
            per_question_results = details.get("per_question_results", [])
            
            if not per_question_results:
                continue
            
            # 提取每个问题的结果
            for q_result in per_question_results:
                if not isinstance(q_result, dict):
                    continue
                
                question_type = q_result.get("question_type", "unknown")
                is_correct = q_result.get("is_correct", False)
                
                codevqa_rows.append({
                    "model": model,
                    "sample_id": sample_id,
                    "domain": domain,
                    "question_type": question_type,
                    "is_correct": 1 if is_correct else 0,
                    "question": q_result.get("question", ""),
                    "ground_truth": q_result.get("ground_truth", ""),
                    "generated_answer": q_result.get("generated_answer", "")
                })
        
        if not codevqa_rows:
            logger.info("No CodeVQA question-level results found, skipping CodeVQA by question type statistics")
            return
        
        # 转换为 DataFrame
        codevqa_df = pd.DataFrame(codevqa_rows)
        
        # 按模型和问题类型分组统计
        summary_rows = []
        for model in codevqa_df["model"].unique():
            model_df = codevqa_df[codevqa_df["model"] == model]
            
            for question_type in model_df["question_type"].unique():
                type_df = model_df[model_df["question_type"] == question_type]
                
                total_count = len(type_df)
                correct_count = type_df["is_correct"].sum()
                accuracy = correct_count / total_count if total_count > 0 else 0.0
                
                summary_rows.append({
                    "model": model,
                    "question_type": question_type,
                    "total_questions": total_count,
                    "correct_answers": int(correct_count),
                    "accuracy": round(accuracy, 4),
                    "accuracy_percentage": round(accuracy * 100, 2)
                })
        
        if not summary_rows:
            logger.warning("No summary rows generated for CodeVQA by question type statistics")
            return
        
        summary_df = pd.DataFrame(summary_rows)
        summary_df = summary_df.sort_values(["model", "question_type"])
        
        # 保存统计文件
        codevqa_summary_path = output_dir / "all_models_codevqa_by_question_type.csv"
        summary_df.to_csv(codevqa_summary_path, index=False, encoding='utf-8')
        logger.info(f"Saved CodeVQA by question type statistics to {codevqa_summary_path}")
    
    def _save_scs_by_dimension_statistics(self, results: List[Dict[str, Any]], output_dir: Path):
        """
        保存 SCS 按维度分层的统计（评估模型在不同维度上的表现）
        
        Args:
            results: 所有评估结果列表
            output_dir: 输出目录
        """
        # 提取所有 SCS 的维度得分
        scs_rows = []
        
        # Task1的维度名称
        dimension_names = ["visual_style_consistency", "layout_consistency", "aesthetic_quality"]
        
        for result in results:
            model = result.get("model", "unknown")
            sample_id = result.get("sample_id", "unknown")
            domain = result.get("domain", "unknown")
            
            # 获取 style_consistency_score 指标的结果
            scs_metric = result.get("metrics", {}).get("style_consistency_score")
            if not scs_metric or not isinstance(scs_metric, dict):
                continue
            
            # 获取 dimension_scores
            details = scs_metric.get("details", {})
            dimension_scores = details.get("dimension_scores", {})
            
            if not dimension_scores or not isinstance(dimension_scores, dict):
                continue
            
            # 提取每个维度的得分
            for dimension_name in dimension_names:
                dimension_score = dimension_scores.get(dimension_name)
                if dimension_score is None:
                    continue
                
                # 确保得分是数值类型
                try:
                    score = float(dimension_score)
                except (ValueError, TypeError):
                    continue
                
                scs_rows.append({
                    "model": model,
                    "sample_id": sample_id,
                    "domain": domain,
                    "dimension": dimension_name,
                    "score": score
                })
        
        if not scs_rows:
            logger.info("No SCS dimension scores found, skipping SCS by dimension statistics")
            return
        
        # 转换为 DataFrame
        scs_df = pd.DataFrame(scs_rows)
        
        # 按模型和维度分组统计
        summary_rows = []
        for model in scs_df["model"].unique():
            model_df = scs_df[scs_df["model"] == model]
            
            for dimension in model_df["dimension"].unique():
                dim_df = model_df[model_df["dimension"] == dimension]
                
                mean_score = dim_df["score"].mean()
                std_score = dim_df["score"].std()
                min_score = dim_df["score"].min()
                max_score = dim_df["score"].max()
                count = len(dim_df)
                
                summary_rows.append({
                    "model": model,
                    "dimension": dimension,
                    "mean_score": round(mean_score, 2),
                    "std_score": round(std_score, 2) if not pd.isna(std_score) else 0.0,
                    "min_score": round(min_score, 2),
                    "max_score": round(max_score, 2),
                    "count": int(count)
                })
        
        if not summary_rows:
            logger.warning("No summary rows generated for SCS by dimension statistics")
            return
        
        summary_df = pd.DataFrame(summary_rows)
        summary_df = summary_df.sort_values(["model", "dimension"])
        
        # 保存统计文件
        scs_summary_path = output_dir / "all_models_scs_by_dimension.csv"
        summary_df.to_csv(scs_summary_path, index=False, encoding='utf-8')
        logger.info(f"Saved SCS by dimension statistics to {scs_summary_path}")
