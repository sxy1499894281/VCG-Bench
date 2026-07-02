#!/usr/bin/env python3
"""
模拟数据错乱检测和修复逻辑的测试（修正版）
"""

def simulate_corruption_detection(existing_metrics, current_domain):
    """
    模拟检测到数据错乱时的处理逻辑
    """
    print(f"Current domain: {current_domain}")
    print(f"Existing metrics: {list(existing_metrics.keys())}")
    print()

    # 检查style_consistency_score
    if 'style_consistency_score' in existing_metrics:
        scs = existing_metrics['style_consistency_score']
        if scs.get('details'):
            original_img = scs['details'].get('original_image', '')
            if original_img and 'domain_' in original_img:
                path_parts = original_img.split('/')
                path_domain = None
                for part in path_parts:
                    if part.startswith('domain_'):
                        path_domain = part
                        break

                if path_domain and path_domain != current_domain:
                    print(f"❌ Data corruption detected!")
                    print(f"   Expected domain: {current_domain}")
                    print(f"   Found in path:   {path_domain}")
                    print(f"   Image path:      {original_img}")
                    print()
                    print(f"⚠️  Analysis: All metrics are from wrong sample!")
                    print(f"   - execution_success_rate: evaluated wrong sample's XML ❌")
                    print(f"   - xml_token_count: counted wrong sample's XML tokens ❌")
                    print(f"   - style_consistency_score: evaluated wrong sample's image ❌")
                    print(f"   - codevqa: evaluated wrong sample's image ❌")
                    print()

                    # 清空所有metrics
                    corrupted_metrics = list(existing_metrics.keys())
                    existing_metrics.clear()

                    print(f"✅ Cleared ALL corrupted metrics: {corrupted_metrics}")
                    print(f"✅ Remaining metrics: {list(existing_metrics.keys())} (empty)")
                    print()
                    print(f"Result: Will re-evaluate ALL {len(corrupted_metrics)} metrics from scratch")
                    return True

    print("✅ No corruption detected, all metrics are consistent")
    return False

# Test case 1: 错乱的样本
print("="*80)
print("TEST CASE 1: Corrupted Sample - All Metrics from Wrong Sample")
print("="*80)
existing_metrics_1 = {
    'execution_success_rate': {'score': 1.0, 'success': True},
    'xml_token_count': {'score': 1500, 'success': True},
    'style_consistency_score': {
        'score': 0.85,
        'success': True,
        'details': {
            'original_image': 'task1_benchmark/domain_academic_domain_architecture/sample_0001/original.png'
        }
    },
    'codevqa': {'score': 0.66, 'success': True}
}
simulate_corruption_detection(existing_metrics_1.copy(), 'domain_academic_domain_dataviz')

# Test case 2: 正确的样本
print("\n" + "="*80)
print("TEST CASE 2: Correct Sample - All Metrics Match")
print("="*80)
existing_metrics_2 = {
    'execution_success_rate': {'score': 1.0, 'success': True},
    'xml_token_count': {'score': 1500, 'success': True},
    'style_consistency_score': {
        'score': 0.85,
        'success': True,
        'details': {
            'original_image': 'task1_benchmark/domain_academic_domain_dataviz/sample_0001/original.png'
        }
    },
    'codevqa': {'score': 0.66, 'success': True}
}
simulate_corruption_detection(existing_metrics_2.copy(), 'domain_academic_domain_dataviz')

# Test case 3: 只有部分metrics的错乱样本
print("\n" + "="*80)
print("TEST CASE 3: Partially Evaluated Corrupted Sample")
print("="*80)
existing_metrics_3 = {
    'execution_success_rate': {'score': 1.0, 'success': True},
    'xml_token_count': {'score': 1500, 'success': True},
    'style_consistency_score': {
        'score': 0.85,
        'success': True,
        'details': {
            'original_image': 'task1_benchmark/domain_business_domain_strategy/sample_0050/original.png'
        }
    }
    # 注意：没有codevqa
}
result = simulate_corruption_detection(existing_metrics_3.copy(), 'domain_academic_domain_architecture')
if result:
    print("\n📊 Final state: All existing metrics cleared")
    print("   → Will evaluate: ALL 4 enabled metrics from scratch")
    print("   → execution_success_rate: re-evaluate with correct XML")
    print("   → xml_token_count: re-count with correct XML")
    print("   → style_consistency_score: re-evaluate with correct image")
    print("   → codevqa: evaluate with correct image (was missing)")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("✅ ALL metrics will be re-evaluated (not just vision-dependent)")
print("✅ Ensures complete correctness for corrupted samples")
print("⚠️  Cost: Need to re-evaluate all metrics (4 per sample)")
print("📊 Estimated corrupted samples: 260 out of 4736 (5.5%)")
print("📊 Total re-evaluations needed: 260 samples × 4 metrics = 1040 metric evaluations")
