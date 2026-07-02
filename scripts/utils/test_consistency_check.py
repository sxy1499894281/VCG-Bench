#!/usr/bin/env python3
"""
测试数据一致性检查逻辑
模拟evaluator中的检测逻辑，验证能否正确识别错乱数据
"""

import json
from pathlib import Path

def extract_domain_from_path(path: str) -> str:
    """从路径中提取domain"""
    if not path or 'domain_' not in path:
        return None
    path_parts = path.split('/')
    for part in path_parts:
        if part.startswith('domain_'):
            return part
    return None

def check_consistency(sample: dict, expected_domain: str) -> dict:
    """
    检查样本的domain一致性
    返回: {'consistent': bool, 'reason': str}
    """
    sample_domain = sample.get('domain', '')
    metrics = sample.get('metrics', {})

    # 检查style_consistency_score
    scs = metrics.get('style_consistency_score', {})
    if scs.get('details'):
        original_img = scs['details'].get('original_image', '')
        if original_img and 'domain_' in original_img:
            path_domain = extract_domain_from_path(original_img)

            if path_domain != expected_domain:
                return {
                    'consistent': False,
                    'reason': f"Domain mismatch: expected={expected_domain}, path_domain={path_domain}",
                    'path': original_img
                }

    return {'consistent': True, 'reason': 'OK'}

# 测试一些已知错乱的样本
fragments_dir = Path('data/task1_evaluation/fragments')

print("Testing data consistency check logic...")
print("="*80)

# 测试gemini-3-pro-preview的dataviz domain（已知有错乱）
test_cases = [
    ('gemini-3-pro-preview', 'domain_academic_domain_dataviz'),
    ('gemini-3-pro-preview', 'domain_academic_domain_architecture'),
    ('Qwen_Qwen3-VL-32B-Instruct', 'domain_academic_domain_dataviz'),
]

for model, domain in test_cases:
    safe_model = model.replace('/', '_')
    frag_file = fragments_dir / f'{safe_model}_{domain}_results.json'

    if not frag_file.exists():
        print(f"\n❌ {model}/{domain}: Fragment not found")
        continue

    with open(frag_file) as f:
        data = json.load(f)

    samples = data.get('samples', [])
    if not samples:
        print(f"\n⚠️  {model}/{domain}: No samples")
        continue

    print(f"\n{'='*80}")
    print(f"Model: {model}")
    print(f"Domain: {domain}")
    print(f"Total samples: {len(samples)}")
    print(f"{'='*80}")

    # 检查前5个样本
    corrupted_count = 0
    for i, sample in enumerate(samples[:5], 1):
        result = check_consistency(sample, domain)
        status = "✅" if result['consistent'] else "❌"

        print(f"{status} Sample {i} ({sample.get('sample_id')}): {result['reason']}")

        if not result['consistent']:
            corrupted_count += 1
            print(f"   Path: {result.get('path', 'N/A')}")

    # 统计所有样本
    total_corrupted = sum(1 for s in samples if not check_consistency(s, domain)['consistent'])

    print(f"\nSummary: {total_corrupted}/{len(samples)} samples are corrupted")

    if total_corrupted > 0:
        print(f"✅ Consistency check will detect and trigger re-evaluation for these {total_corrupted} samples")
    else:
        print(f"✅ All samples are consistent, will be skipped correctly")

print("\n" + "="*80)
print("Test completed!")
print("="*80)
