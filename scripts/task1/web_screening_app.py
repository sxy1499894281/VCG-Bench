#!/usr/bin/env python3
"""
Web Screening Application for Task 1
网页筛选应用，用于筛选Gemini生成的结果
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, render_template, send_file

# Setup logging
logger = logging.getLogger(__name__)

# Flask app
app = Flask(
    __name__,
    template_folder=Path(__file__).parent / 'templates',
    static_folder=Path(__file__).parent / 'templates' / 'static'
)

# Global variable for source directory
SOURCE_DIR = None

# Global cache for evaluation scores
EVALUATION_SCORES_CACHE = {}
EVALUATION_DIR = None


def find_model_dir(sample_dir: Path, model_name: str = None) -> Path:
    """
    查找模型目录
    
    Args:
        sample_dir: 样本目录
        model_name: 模型名称（例如 "gemini-3-pro-preview"），如果为None则查找默认模型
        
    Returns:
        模型目录Path对象，如果不存在返回None
    """
    if model_name:
        model_dir = sample_dir / f"model_{model_name}"
        if model_dir.exists():
            return model_dir
        return None
    
    # 如果没有指定模型，优先查找 gemini-3-pro-preview
    desc_model_name = "gemini-3-pro-preview"
    candidate_dir = sample_dir / f"model_{desc_model_name}"
    if candidate_dir.exists():
        return candidate_dir
    
    # 如果没找到，查找其他包含"gemini"的模型目录
    for model_dir in sample_dir.glob('model_*'):
        if 'gemini' in model_dir.name.lower():
            return model_dir
    
    return None


def load_evaluation_scores(model_name: str, domain: str, evaluation_dir: Path) -> dict:
    """
    加载评估结果中的分数
    
    Args:
        model_name: 模型名称（例如 "GLM-4.6V" 或 "gemini-3-pro-preview"）
        domain: 领域名称（例如 "domain_academic_domain_architecture"）
        evaluation_dir: 评估结果目录
        
    Returns:
        字典，key为sample_id，value为分数字典 {scs, codevqa, siglip}
    """
    # 检查缓存
    cache_key = f"{model_name}_{domain}"
    if cache_key in EVALUATION_SCORES_CACHE:
        return EVALUATION_SCORES_CACHE[cache_key]
    
    scores = {}
    
    # 构建文件路径
    # 注意：模型名称在文件名中可能有不同的格式
    # 例如：目录名可能是 "model_GLM-4.6V"，但文件名可能是 "zai-org_GLM-4.6V_..."
    # 或者：目录名可能是 "model_Qwen3-VL-8B-Instruct"，但文件名可能是 "Qwen_Qwen3-VL-8B-Instruct_..."
    file_name = f"{model_name}_{domain}_results.json"
    file_path = evaluation_dir / "fragments" / file_name
    
    if not file_path.exists():
        # 尝试其他可能的文件名格式（处理模型名称中的特殊字符）
        # 首先尝试直接匹配
        fragments_dir = evaluation_dir / "fragments"
        if not fragments_dir.exists():
            EVALUATION_SCORES_CACHE[cache_key] = scores
            return scores
        
        # 尝试模糊匹配：查找所有包含domain的文件
        best_match = None
        model_name_normalized = model_name.replace('-', '_').replace(' ', '_').lower()
        
        # 构建domain的匹配模式（domain可能包含下划线，如 "academic_domain_architecture"）
        # 文件名格式：{model_name}_{domain}_results.json
        # 需要匹配以domain结尾的文件
        domain_pattern = f"*_{domain}_results.json"
        
        for f in fragments_dir.glob(domain_pattern):
            file_stem = f.stem
            # 文件名格式可能是：{model_name}_{domain}_results
            # 需要提取模型名称部分（在domain之前的所有部分）
            # 例如：zai-org_GLM-4.6V_domain_academic_domain_architecture_results
            # domain是 "domain_academic_domain_architecture"
            # 需要找到domain的起始位置
            
            # 方法1：直接通过字符串查找domain的位置
            domain_suffix = f"_{domain}_results"
            if file_stem.endswith(domain_suffix):
                # 提取domain之前的部分作为模型名称
                file_model_name = file_stem[:-len(domain_suffix)]
                file_model_normalized = file_model_name.replace('-', '_').replace(' ', '_').lower()
                
                # 检查是否匹配（完全匹配或部分匹配）
                # 完全匹配：glm_4_6v == glm_4_6v
                # 部分匹配：glm_4_6v 在 zai_org_glm_4_6v 中，或 zai_org_glm_4_6v 包含 glm_4_6v
                if model_name_normalized == file_model_normalized:
                    best_match = f
                    break
                elif model_name_normalized in file_model_normalized:
                    # 部分匹配：模型名在文件名中（例如：GLM-4.6V 在 zai-org_GLM-4.6V 中）
                    # 优先选择模型名在文件名末尾的匹配（更精确）
                    if best_match is None:
                        best_match = f
                    elif file_model_normalized.endswith(model_name_normalized):
                        best_match = f
                elif file_model_normalized.endswith(model_name_normalized):
                    # 文件名以模型名结尾（最精确的匹配）
                    best_match = f
                    break
        
        if best_match:
            file_path = best_match
        else:
            # 如果还是找不到，返回空字典
            EVALUATION_SCORES_CACHE[cache_key] = scores
            return scores
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        samples = data.get('samples', [])
        for sample in samples:
            sample_id = sample.get('sample_id')
            if not sample_id:
                continue
            
            metrics = sample.get('metrics', {})
            
            # 提取分数
            scs = None
            codevqa = None
            siglip = None
            
            # SCS分数
            scs_metric = metrics.get('style_consistency_score')
            if scs_metric and scs_metric.get('success', False):
                scs = scs_metric.get('score')
            
            # CodeVQA分数
            codevqa_metric = metrics.get('codevqa')
            if codevqa_metric and codevqa_metric.get('success', False):
                codevqa = codevqa_metric.get('score')
            
            # SigLIP分数
            siglip_metric = metrics.get('siglip_score')
            if siglip_metric and siglip_metric.get('success', False):
                siglip = siglip_metric.get('score')
            
            if scs is not None or codevqa is not None or siglip is not None:
                scores[sample_id] = {
                    'scs': scs,
                    'codevqa': codevqa,
                    'siglip': siglip
                }
    except Exception as e:
        logger.warning(f"Failed to load evaluation scores from {file_path}: {e}")
    
    # 缓存结果
    EVALUATION_SCORES_CACHE[cache_key] = scores
    return scores


def get_sample_scores(model_name: str, domain: str, sample_id: str, evaluation_dir: Path) -> dict:
    """
    获取单个样本的评估分数
    
    Args:
        model_name: 模型名称
        domain: 领域名称
        sample_id: 样本ID
        evaluation_dir: 评估结果目录
        
    Returns:
        分数字典 {scs, codevqa, siglip}，如果不存在则返回None值
    """
    scores = load_evaluation_scores(model_name, domain, evaluation_dir)
    return scores.get(sample_id, {'scs': None, 'codevqa': None, 'siglip': None})


def get_available_models(source_dir: Path) -> list:
    """
    获取所有可用的模型列表
    
    Args:
        source_dir: task1_benchmark目录
        
    Returns:
        模型名称列表（去除 "model_" 前缀）
    """
    models = set()
    
    for domain_dir in source_dir.glob('domain_*'):
        if not domain_dir.is_dir():
            continue
        
        for sample_dir in domain_dir.glob('sample_*'):
            if not sample_dir.is_dir():
                continue
            
            # 查找所有模型目录
            for model_dir in sample_dir.glob('model_*'):
                if model_dir.is_dir():
                    # 去除 "model_" 前缀
                    model_name = model_dir.name.replace('model_', '', 1)
                    models.add(model_name)
    
    return sorted(list(models))


def load_all_samples(source_dir: Path, model_name: str = None, model_names: list = None, filter_unmarked: bool = False, filter_status: str = None) -> list:
    """
    加载所有样本
    
    Args:
        source_dir: task1_benchmark目录
        model_name: 模型名称，如果为None则使用默认模型（gemini-3-pro-preview）
        model_names: 模型名称列表，如果指定则只返回所有模型都存在的样本（多模型筛选）
        filter_unmarked: 是否只返回未打标的样本
        filter_status: 状态筛选（approved/rejected/pending）
        
    Returns:
        样本列表
    """
    samples = []
    
    # 如果指定了多模型筛选，先找出所有包含这些模型的样本
    if model_names and len(model_names) > 0:
        # 收集所有包含所有指定模型的样本
        valid_samples = set()
        
        for domain_dir in source_dir.glob('domain_*'):
            if not domain_dir.is_dir():
                continue
            
            for sample_dir in domain_dir.glob('sample_*'):
                if not sample_dir.is_dir():
                    continue
                
                # 检查该样本是否包含所有指定的模型，并且都成功渲染了
                has_all_models = True
                for m_name in model_names:
                    model_dir = sample_dir / f"model_{m_name}"
                    rendered_path = model_dir / "rendered.png"
                    # 不仅要检查模型目录存在，还要检查rendered.png存在（表示成功渲染）
                    if not model_dir.exists() or not rendered_path.exists():
                        has_all_models = False
                        break
                
                if has_all_models:
                    valid_samples.add((domain_dir.name, sample_dir.name))
        
        # 只处理这些样本
        sample_dirs_to_process = valid_samples
    else:
        # 单模型模式，处理所有样本
        sample_dirs_to_process = None
    
    for domain_dir in source_dir.glob('domain_*'):
        if not domain_dir.is_dir():
            continue
        
        for sample_dir in domain_dir.glob('sample_*'):
            if not sample_dir.is_dir():
                continue
            
            # 如果是多模型筛选模式，检查该样本是否在有效列表中
            if sample_dirs_to_process is not None:
                if (domain_dir.name, sample_dir.name) not in sample_dirs_to_process:
                    continue
            
            # 对于多模型筛选，使用第一个模型来显示（或者可以显示所有模型）
            # 这里我们使用第一个模型作为显示模型
            display_model_name = None
            if model_names and len(model_names) > 0:
                display_model_name = model_names[0]
            else:
                display_model_name = model_name
            
            model_dir = find_model_dir(sample_dir, display_model_name)
            if model_dir is None:
                continue
            
            # 读取状态文件
            status_path = model_dir / "screening_status.json"
            status = {"status": "pending"}
            if status_path.exists():
                try:
                    with open(status_path, 'r', encoding='utf-8') as f:
                        status = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read status for {sample_dir.name}: {e}")
            
            # 筛选逻辑
            current_status = status.get('status', 'pending')
            
            # 如果筛选未打标，跳过已有状态的
            if filter_unmarked and current_status != 'pending':
                continue
            
            # 如果指定了状态筛选，只返回匹配的状态
            if filter_status and current_status != filter_status:
                continue
            
            # 检查文件是否存在
            original_path = sample_dir / "original.png"
            rendered_path = model_dir / "rendered.png"
            
            if not original_path.exists() or not rendered_path.exists():
                logger.debug(f"Skipping {sample_dir.name}: missing images")
                continue
            
            # 计算相对路径（相对于source_dir）
            try:
                original_rel_path = original_path.relative_to(source_dir)
                rendered_rel_path = rendered_path.relative_to(source_dir)
            except ValueError:
                # 如果路径不在source_dir下，使用绝对路径
                logger.warning(f"Path not relative to source_dir: {sample_dir}")
                continue
            
            # 获取模型名称（去除 "model_" 前缀）
            actual_model_name = model_dir.name.replace('model_', '', 1)
            
            # 对于多模型筛选，添加所有可用模型信息、渲染图路径和分数
            available_models_in_sample = []
            all_models_scores = {}  # 存储所有模型的分数 {model_name: {scs, codevqa, siglip}}
            all_models_rendered_paths = {}  # 存储所有模型的渲染图路径 {model_name: rendered_path}
            
            if model_names and len(model_names) > 0:
                for m_name in model_names:
                    m_dir = sample_dir / f"model_{m_name}"
                    m_rendered_path = m_dir / "rendered.png"
                    # 检查模型目录和渲染图都存在
                    if m_dir.exists() and m_rendered_path.exists():
                        available_models_in_sample.append(m_name)
                        # 计算渲染图的相对路径
                        try:
                            m_rendered_rel_path = m_rendered_path.relative_to(source_dir)
                            all_models_rendered_paths[m_name] = str(m_rendered_rel_path).replace('\\', '/')
                        except ValueError:
                            logger.warning(f"Path not relative to source_dir: {m_rendered_path}")
                            continue
                        
                        # 加载该模型的评估分数
                        if EVALUATION_DIR and EVALUATION_DIR.exists():
                            model_scores = get_sample_scores(m_name, domain_dir.name, sample_dir.name, EVALUATION_DIR)
                            all_models_scores[m_name] = model_scores
                        else:
                            all_models_scores[m_name] = {'scs': None, 'codevqa': None, 'siglip': None}
            
            # 加载显示模型的评估分数（单模型模式或作为默认）
            scores = {'scs': None, 'codevqa': None, 'siglip': None}
            if EVALUATION_DIR and EVALUATION_DIR.exists():
                scores = get_sample_scores(actual_model_name, domain_dir.name, sample_dir.name, EVALUATION_DIR)
            
            sample_data = {
                "sample_id": sample_dir.name,
                "domain": domain_dir.name,
                "model_name": actual_model_name,
                "original_path": str(original_rel_path).replace('\\', '/'),  # 统一使用正斜杠
                "rendered_path": str(rendered_rel_path).replace('\\', '/'),
                "status": status.get('status', 'pending'),
                "screened_date": status.get('screened_date'),
                "notes": status.get('screener_notes'),
                "scores": scores,  # 单模型模式的分数（向后兼容）
                "available_models": available_models_in_sample if available_models_in_sample else [actual_model_name],  # 添加可用模型列表
                "all_models_scores": all_models_scores if all_models_scores else {actual_model_name: scores},  # 所有模型的分数
                "all_models_rendered_paths": all_models_rendered_paths if all_models_rendered_paths else {actual_model_name: str(rendered_rel_path).replace('\\', '/')}  # 所有模型的渲染图路径
            }
            samples.append(sample_data)
    
    # 按domain和sample_id排序
    return sorted(samples, key=lambda x: (x['domain'], x['sample_id']))


@app.route('/')
def index():
    """返回主页面"""
    return render_template('screening.html')


@app.route('/api/models')
def get_models():
    """获取可用模型列表"""
    try:
        models = get_available_models(SOURCE_DIR)
        return jsonify({
            "models": models,
            "default": "gemini-3-pro-preview" if "gemini-3-pro-preview" in models else (models[0] if models else None)
        })
    except Exception as e:
        logger.error(f"Error loading models: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/samples')
def get_samples():
    """获取样本列表"""
    try:
        # 支持单模型和多模型筛选
        model_name = request.args.get('model', None)  # 单个模型名称（向后兼容）
        models_param = request.args.get('models', None)  # 多个模型名称，逗号分隔
        
        # 解析多模型参数
        model_names = None
        if models_param:
            model_names = [m.strip() for m in models_param.split(',') if m.strip()]
            # 如果指定了多模型，忽略单模型参数
            model_name = None
        
        filter_unmarked = request.args.get('unmarked', 'false').lower() == 'true'
        filter_status = request.args.get('status', None)  # approved, rejected, pending
        if filter_status and filter_status not in ['approved', 'rejected', 'pending']:
            filter_status = None
        
        samples = load_all_samples(SOURCE_DIR, model_name=model_name, model_names=model_names, filter_unmarked=filter_unmarked, filter_status=filter_status)
        return jsonify({
            "samples": samples,
            "total": len(samples)
        })
    except Exception as e:
        logger.error(f"Error loading samples: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/sample/<domain>/<sample_id>')
def get_sample(domain: str, sample_id: str):
    """获取单个样本详情"""
    try:
        model_name = request.args.get('model', None)  # 模型名称
        
        sample_dir = SOURCE_DIR / domain / sample_id
        if not sample_dir.exists():
            return jsonify({"error": "Sample not found"}), 404
        
        model_dir = find_model_dir(sample_dir, model_name)
        if model_dir is None:
            return jsonify({"error": "Model directory not found"}), 404
        
        # 读取状态
        status_path = model_dir / "screening_status.json"
        status = {"status": "pending"}
        if status_path.exists():
            with open(status_path, 'r', encoding='utf-8') as f:
                status = json.load(f)
        
        original_path = sample_dir / "original.png"
        rendered_path = model_dir / "rendered.png"
        
        original_rel_path = original_path.relative_to(SOURCE_DIR)
        rendered_rel_path = rendered_path.relative_to(SOURCE_DIR)
        
        # 获取模型名称（去除 "model_" 前缀）
        actual_model_name = model_dir.name.replace('model_', '', 1)
        
        return jsonify({
            "sample_id": sample_id,
            "domain": domain,
            "model_name": actual_model_name,
            "original_path": str(original_rel_path).replace('\\', '/'),
            "rendered_path": str(rendered_rel_path).replace('\\', '/'),
            "status": status.get('status', 'pending'),
            "screened_date": status.get('screened_date'),
            "notes": status.get('screener_notes')
        })
    except Exception as e:
        logger.error(f"Error loading sample: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/image/original/<path:image_path>')
def serve_original_image(image_path: str):
    """提供原图"""
    try:
        # 处理URL编码的路径
        image_path = image_path.replace('%2F', '/').replace('%5C', '/')
        full_path = SOURCE_DIR / image_path
        
        # 安全检查：确保路径在SOURCE_DIR下
        try:
            full_path.resolve().relative_to(SOURCE_DIR.resolve())
        except ValueError:
            return jsonify({"error": "Invalid path"}), 403
        
        if not full_path.exists():
            return jsonify({"error": "Image not found"}), 404
        
        return send_file(full_path, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error serving original image: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/image/rendered/<path:image_path>')
def serve_rendered_image(image_path: str):
    """提供渲染图"""
    try:
        # 处理URL编码的路径
        image_path = image_path.replace('%2F', '/').replace('%5C', '/')
        full_path = SOURCE_DIR / image_path
        
        # 安全检查：确保路径在SOURCE_DIR下
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


@app.route('/api/status', methods=['POST'])
def update_status():
    """更新样本状态"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        sample_id = data.get('sample_id')
        domain = data.get('domain')
        model_name = data.get('model_name')  # 模型名称
        status = data.get('status')
        notes = data.get('notes')
        
        if not sample_id or not domain or not status:
            return jsonify({"error": "Missing required fields"}), 400
        
        if status not in ['approved', 'rejected', 'pending']:
            return jsonify({"error": "Invalid status"}), 400
        
        sample_dir = SOURCE_DIR / domain / sample_id
        if not sample_dir.exists():
            return jsonify({"error": "Sample not found"}), 404
        
        model_dir = find_model_dir(sample_dir, model_name)
        if model_dir is None:
            return jsonify({"error": "Model directory not found"}), 404
        
        status_path = model_dir / "screening_status.json"
        
        status_data = {
            "status": status,
            "screened_date": datetime.now().isoformat(),
            "screener_notes": notes
        }
        
        # 保存状态文件
        with open(status_path, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2, ensure_ascii=False)
        
        # 记录详细信息
        logger.info(f"Updated status for {domain}/{sample_id} (model: {model_name}): {status}")
        logger.info(f"Status file saved to: {status_path.resolve()}")
        logger.debug(f"Status data: {status_data}")
        
        return jsonify({
            "success": True,
            "status_path": str(status_path.relative_to(SOURCE_DIR)),
            "status": status
        })
    except Exception as e:
        logger.error(f"Error updating status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/statistics')
def get_statistics():
    """获取统计信息"""
    try:
        model_name = request.args.get('model', None)  # 模型名称
        samples = load_all_samples(SOURCE_DIR, model_name=model_name, filter_unmarked=False)
        stats = {
            "total": len(samples),
            "approved": sum(1 for s in samples if s['status'] == 'approved'),
            "rejected": sum(1 for s in samples if s['status'] == 'rejected'),
            "pending": sum(1 for s in samples if s['status'] == 'pending')
        }
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error loading statistics: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def run_server(source_dir: str, host: str = '127.0.0.1', port: int = 5000, evaluation_dir: str = None):
    """
    启动服务器
    
    Args:
        source_dir: task1_benchmark目录路径
        host: 主机地址
        port: 端口号
        evaluation_dir: task1_evaluation目录路径（可选）
    """
    global SOURCE_DIR, EVALUATION_DIR
    SOURCE_DIR = Path(source_dir).resolve()
    
    if not SOURCE_DIR.exists():
        raise ValueError(f"Source directory does not exist: {SOURCE_DIR}")
    
    # 设置评估结果目录
    if evaluation_dir:
        EVALUATION_DIR = Path(evaluation_dir).resolve()
    else:
        # 默认尝试在source_dir的父目录下查找task1_evaluation
        default_eval_dir = SOURCE_DIR.parent / "task1_evaluation"
        if default_eval_dir.exists():
            EVALUATION_DIR = default_eval_dir
        else:
            EVALUATION_DIR = None
            logger.info("Evaluation directory not found, scores will not be displayed")
    
    import webbrowser
    url = f'http://{host}:{port}'
    logger.info(f"Starting web server at {url}")
    logger.info(f"Source directory: {SOURCE_DIR}")
    logger.info("Press Ctrl+C to stop the server")
    
    # 延迟打开浏览器，给服务器启动时间
    import threading
    def open_browser():
        import time
        time.sleep(1.5)  # 等待1.5秒让服务器启动
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
        print("Usage: python web_screening_app.py <source_dir> [host] [port]")
        sys.exit(1)
    
    source_dir = sys.argv[1]
    host = sys.argv[2] if len(sys.argv) > 2 else '127.0.0.1'
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
    
    run_server(source_dir, host, port)

