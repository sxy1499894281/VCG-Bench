#!/usr/bin/env python3
"""
检查task2 evaluation数据是否错乱
检查逻辑：instruction的domain字段应该与metrics中实际评估的路径一致
"""

import json
from pathlib import Path
from collections import defaultdict

def extract_domain_from_path(path: str) -> str:
    """从路径中提取domain"""
    if not path or 'domain_' not in path:
        return None
    parts = path.split('/')
    for part in parts:
        if part.startswith('domain_'):
            return part
    return None

def check_instruction_corruption(instruction: dict) -> dict:
    """
    检查单个instruction是否错乱
    返回: {'corrupted': bool, 'reason': str, 'details': dict}
    """
    sample_id = instruction.get('sample_id', '')
    instruction_id = instruction.get('instruction_id', '')
    instruction_domain = instruction.get('domain', '')
    model = instruction.get('model', '')
    metrics = instruction.get('metrics', {})

    # 检查各个metrics中的路径
    corruption_details = []

    # 1. 检查 style_consistency_score_task2
    scs = metrics.get('style_consistency_score_task2', {})
    if scs.get('details'):
        modified_path = scs['details'].get('modified_rendered_path', '')

        if modified_path:
            path_domain = extract_domain_from_path(modified_path)
            if path_domain and path_domain != instruction_domain:
                corruption_details.append({
                    'metric': 'style_consistency_score_task2',
                    'field': 'modified_rendered_path',
                    'expected_domain': instruction_domain,
                    'actual_domain': path_domain,
                    'path': modified_path
                })

    is_corrupted = len(corruption_details) > 0

    return {
        'corrupted': is_corrupted,
        'sample_id': sample_id,
        'instruction_id': instruction_id,
        'domain': instruction_domain,
        'model': model,
        'details': corruption_details
    }

def main():
    fragments_dir = Path('data/task2_evaluation/fragments')

    # 统计结果
    model_stats = defaultdict(lambda: {
        'total_instructions': 0,
        'corrupted_instructions': 0,
        'clean_instructions': 0,
        'no_metrics_instructions': 0,
        'by_domain': defaultdict(lambda: {'total': 0, 'corrupted': 0})
    })

    all_corrupted_instructions = []

    # 遍历所有fragment文件
    fragment_files = list(fragments_dir.glob('*_results.json'))
    print(f"Scanning {len(fragment_files)} fragment files...\n")

    for fragment_file in fragment_files:
        try:
            with open(fragment_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            instructions = data.get('instructions', [])
            if not instructions:
                continue

            for instruction in instructions:
                model = instruction.get('model', '')
                domain = instruction.get('domain', '')

                if not model:
                    continue

                metrics = instruction.get('metrics', {})

                # 检查是否有style_consistency_score_task2（用于检测错乱的主要指标）
                has_scs = 'style_consistency_score_task2' in metrics and metrics['style_consistency_score_task2'].get('details')

                if not has_scs:
                    # 没有可检查的metrics
                    model_stats[model]['no_metrics_instructions'] += 1
                    model_stats[model]['total_instructions'] += 1
                    model_stats[model]['by_domain'][domain]['total'] += 1
                    continue

                # 检查instruction
                result = check_instruction_corruption(instruction)

                model_stats[model]['total_instructions'] += 1
                model_stats[model]['by_domain'][domain]['total'] += 1

                if result['corrupted']:
                    model_stats[model]['corrupted_instructions'] += 1
                    model_stats[model]['by_domain'][domain]['corrupted'] += 1
                    all_corrupted_instructions.append(result)
                else:
                    model_stats[model]['clean_instructions'] += 1

        except Exception as e:
            print(f"Error processing {fragment_file}: {e}")
            continue

    # 打印统计结果
    print("="*90)
    print("TASK2 DATA CORRUPTION ANALYSIS")
    print("="*90)
    print()

    # 按模型统计
    total_all_instructions = 0
    total_all_corrupted = 0

    for model in sorted(model_stats.keys()):
        stats = model_stats[model]
        total = stats['total_instructions']
        corrupted = stats['corrupted_instructions']
        clean = stats['clean_instructions']
        no_metrics = stats['no_metrics_instructions']

        if total == 0:
            continue

        corruption_rate = (corrupted / total * 100) if total > 0 else 0

        total_all_instructions += total
        total_all_corrupted += corrupted

        status = "❌" if corrupted > 0 else "✅"

        print(f"{status} {model}")
        print(f"   Total instructions:     {total:4d}")
        print(f"   Corrupted:              {corrupted:4d} ({corruption_rate:5.1f}%)")
        print(f"   Clean:                  {clean:4d}")
        print(f"   No SCS metrics:         {no_metrics:4d}")

        # 显示corrupted instructions的domain分布
        if corrupted > 0:
            print(f"   Corrupted by domain:")
            corrupted_domains = [(d, s['corrupted']) for d, s in stats['by_domain'].items() if s['corrupted'] > 0]
            corrupted_domains.sort(key=lambda x: x[1], reverse=True)
            for domain, count in corrupted_domains[:3]:
                domain_short = domain.replace('domain_', '').replace('_domain_', '/')
                print(f"      - {domain_short:40s}: {count:3d} instructions")
            if len(corrupted_domains) > 3:
                print(f"      ... and {len(corrupted_domains)-3} more domains")
        print()

    # 总结
    print("="*90)
    print("SUMMARY")
    print("="*90)
    overall_rate = (total_all_corrupted / total_all_instructions * 100) if total_all_instructions > 0 else 0
    print(f"Total instructions checked:   {total_all_instructions:5d}")
    print(f"Total corrupted:              {total_all_corrupted:5d} ({overall_rate:5.1f}%)")
    print(f"Total clean:                  {total_all_instructions - total_all_corrupted:5d}")
    print()

    if total_all_corrupted > 0:
        print("⚠️  RECOMMENDATION: Data corruption detected!")
        print("   Task2 evaluator has been fixed. Run evaluation to auto-fix corrupted data.")
        print()

        # 显示一些错乱样本的例子
        if all_corrupted_instructions:
            print("Examples of corrupted instructions:")
            for i, inst in enumerate(all_corrupted_instructions[:2], 1):
                print(f"\n{i}. {inst['model']}/{inst['domain']}/{inst['sample_id']}/{inst['instruction_id']}")
                for detail in inst['details']:
                    print(f"   Expected: {detail['expected_domain']}")
                    print(f"   Actual:   {detail['actual_domain']}")
                    print(f"   Path:     {detail['path']}")
    else:
        print("✅ No data corruption detected in task2!")

    print("="*90)

if __name__ == '__main__':
    main()
