#!/usr/bin/env python3
"""
Task 1: Generate QA Pairs for CodeVQA Evaluation
根据原图生成 QA 对，用于后续 CodeVQA 评估
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
vcgbench_root = Path(__file__).parent.parent.parent
env_path = vcgbench_root / '.env'
if env_path.exists():
    load_dotenv(env_path, override=True)

from src.llm.client import LLMClient

# Setup logging
log_dir = vcgbench_root / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'task1_qa_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def generate_qa_pairs_for_image(
    image_path: Path,
    num_questions: int = 3,  # 固定为 3，包含三种不同类型
    generation_model: str = "gemini-3-pro-preview",
    llm_client: LLMClient = None
) -> List[Dict[str, str]]:
    """
    根据原图生成 QA 对
    
    参数:
        image_path: 原图路径
        num_questions: 生成的问题数量（固定为 3，包含三种不同类型）
        generation_model: 生成模型
        llm_client: LLM 客户端
    
    返回:
        List[Dict]: QA 对列表，必须包含 3 个不同类型的 QA 对
    """
    
    if llm_client is None:
        llm_client = LLMClient()
    
    prompt = f"""Please analyze the provided diagram image and generate 3 question-answer pairs for testing semantic information retention.
Must include the following three types, one of each:
1. Counting: Count the number of elements in the diagram
2. Identification: Identify attributes or labels of specific elements
3. Relationship: Identify relationships or connections between elements

Image: [Image: {image_path}]

**Requirements (Enhanced Version):**

**1. Depth Requirements (Improve Discrimination)**
- **Counting questions**: Should not only ask "how many nodes" which is too simple. Should include counting of specific attributes, for example:
  - "How many blue circular nodes are in the diagram?"
  - "How many dashed connections are there?"
  - "How many nodes have labels starting with the letter 'A'?"
- **Identification questions**: Should test specific visual details, for example:
  - "What is the fill color of the node with id 'node_5'?"
  - "What is the label of the node located at the top-left corner of the diagram?"
  - "What color is the line connecting node A and node B?"
- **Relationship questions**: Should test multi-level connections or complex relationships, for example:
  - "Through which intermediate nodes can node A reach node D?"
  - "Which nodes are connected to both node B and node C?"
  - "How many nodes are in the longest path from the root node to a leaf node?"

**2. Semantic Uniqueness**
- Ensure each question's answer is unique and unambiguous in the diagram
- Avoid questions that can be answered through common sense or context
- Questions should require the model to carefully observe the image to answer

**3. Visual Anchors**
- Guide questions to focus on key details and specific locations in the diagram
- Use specific identifiers (such as node IDs, position descriptions) to anchor questions
- Prevent models from answering through general reasoning rather than visual observation

**4. Verifiability**
- Answers should be specific and verifiable (numbers, color values, label text, etc.)
- Avoid subjective judgment questions

**Output Format (JSON):**
{{
    "qa_pairs": [
        {{
            "question": "How many blue circular nodes are in the diagram?",
            "answer": "3",
            "question_type": "counting",
            "visual_anchor": "blue circular nodes"
        }},
        {{
            "question": "What is the fill color (in hexadecimal) of the node with id 'anchor'?",
            "answer": "#FF5733",
            "question_type": "identification",
            "visual_anchor": "node ID 'anchor'"
        }},
        {{
            "question": "Through which intermediate nodes can node A reach node D? Please list in order.",
            "answer": "Node B and Node C",
            "question_type": "relationship",
            "visual_anchor": "path from node A to node D"
        }}
    ]
}}

**Examples (Few-shot):**

**Good Question Examples:**
- Counting: "How many rectangular nodes with fill color #FF0000 are in the diagram?" (Answer: 2)
- Identification: "What is the label of the node located at the center of the diagram with the largest area?" (Answer: Root)
- Relationship: "How many nodes are in the shortest path from node 'start' to node 'end'?" (Answer: 4)

**Bad Question Examples (Avoid):**
- "How many nodes are in the diagram?" (Too simple, lacks discrimination)
- "What type of diagram is this?" (Can be answered through common sense)
- "What is the relationship between nodes?" (Too broad, answer is not unique)"""
    
    try:
        # Call vision model to generate QA pairs
        response_text, token_usage = llm_client._call_vision_api(
            prompt=prompt,
            image_input=image_path,
            provider='custom',
            model=generation_model,
            temperature=0.3,  # Lower temperature for consistency
            response_format={"type": "json_object"}
        )
        
        # Parse JSON response
        qa_data = json.loads(response_text)
        qa_pairs = qa_data.get("qa_pairs", [])
        
        # Validate that all 3 different types of QA pairs are included
        required_types = {"counting", "identification", "relationship"}
        actual_types = {qa.get("question_type") for qa in qa_pairs}
        
        if not required_types.issubset(actual_types):
            logger.warning(f"QA pairs missing required types. Required: {required_types}, Got: {actual_types}")
            # Try to fix: if missing a type, generate default question
            if "counting" not in actual_types:
                qa_pairs.append({
                    "question": "How many nodes are in the diagram?",
                    "answer": "Unknown",
                    "question_type": "counting"
                })
            if "identification" not in actual_types:
                qa_pairs.append({
                    "question": "What is the label of the center node?",
                    "answer": "Unknown",
                    "question_type": "identification"
                })
            if "relationship" not in actual_types:
                qa_pairs.append({
                    "question": "Which nodes are connected to each other?",
                    "answer": "Unknown",
                    "question_type": "relationship"
                })
        
        logger.info(f"Generated {len(qa_pairs)} QA pairs for {image_path.name}")
        
        return qa_pairs[:num_questions]  # 确保只返回 3 个
        
    except Exception as e:
        logger.error(f"Failed to generate QA pairs for {image_path.name}: {e}", exc_info=True)
        return []


def process_all_samples(
    source_dir: Path,
    num_questions: int = 3,  # 固定为 3，包含三种不同类型
    generation_model: str = "gemini-3-pro-preview",
    resume: bool = True
):
    """
    处理所有样本，生成 QA 对
    
    参数:
        source_dir: task1_benchmark 目录
        num_questions: 每个样本生成的问题数量
        generation_model: 生成模型
        resume: 是否断点续传
    """
    
    logger.info("=" * 80)
    logger.info("Task 1: Generate QA Pairs for CodeVQA")
    logger.info("=" * 80)
    logger.info(f"Source directory: {source_dir}")
    logger.info(f"Questions per sample: {num_questions}")
    logger.info(f"Generation model: {generation_model}")
    logger.info(f"Resume: {resume}")
    
    # 初始化 LLM 客户端
    llm_client = LLMClient()
    
    # 扫描所有领域
    domain_dirs = sorted([d for d in source_dir.glob('domain_*') if d.is_dir()])
    logger.info(f"\nFound {len(domain_dirs)} domains: {[d.name for d in domain_dirs]}")
    
    total_processed = 0
    total_qa_pairs = 0
    
    for domain_dir in domain_dirs:
        domain = domain_dir.name
        logger.info("\n" + "=" * 80)
        logger.info(f"Processing domain: {domain}")
        logger.info("=" * 80)
        
        # 扫描所有样本
        sample_dirs = sorted([d for d in domain_dir.glob('sample_*') if d.is_dir()])
        logger.info(f"Found {len(sample_dirs)} samples")
        
        domain_processed = 0
        domain_qa_pairs = 0
        
        for sample_dir in sample_dirs:
            sample_id = sample_dir.name
            
            # 检查是否已处理（断点续传）
            qa_pairs_path = sample_dir / "qa_pairs.json"
            if resume and qa_pairs_path.exists():
                try:
                    with open(qa_pairs_path, 'r', encoding='utf-8') as f:
                        existing_qa = json.load(f)
                    if existing_qa.get("qa_pairs") and len(existing_qa["qa_pairs"]) >= num_questions:
                        logger.info(f"Sample {sample_id} already has QA pairs, skipping")
                        domain_qa_pairs += len(existing_qa["qa_pairs"])
                        domain_processed += 1
                        continue
                except Exception as e:
                    logger.warning(f"Failed to read existing QA pairs: {e}")
            
            # 获取原图路径
            original_image_path = sample_dir / "original.png"
            if not original_image_path.exists():
                logger.warning(f"Original image not found for {sample_id}, skipping")
                continue
            
            logger.info(f"\n--- Processing {sample_id} ---")
            
            try:
                # 生成 QA 对
                qa_pairs = generate_qa_pairs_for_image(
                    image_path=original_image_path,
                    num_questions=num_questions,
                    generation_model=generation_model,
                    llm_client=llm_client
                )
                
                if qa_pairs:
                    # 保存 QA 对到文件
                    qa_data = {
                        "sample_id": sample_id,
                        "domain": domain,
                        "num_questions": len(qa_pairs),
                        "qa_pairs": qa_pairs,
                        "generated_at": datetime.now().isoformat(),
                        "generation_model": generation_model
                    }
                    
                    with open(qa_pairs_path, 'w', encoding='utf-8') as f:
                        json.dump(qa_data, f, indent=2, ensure_ascii=False)
                    
                    domain_qa_pairs += len(qa_pairs)
                    domain_processed += 1
                    logger.info(f"✓ Generated {len(qa_pairs)} QA pairs for {sample_id}")
                else:
                    logger.warning(f"Failed to generate QA pairs for {sample_id}")
                    
            except Exception as e:
                logger.error(f"Error processing {sample_id}: {e}", exc_info=True)
        
        total_processed += domain_processed
        total_qa_pairs += domain_qa_pairs
        
        logger.info(f"\nDomain {domain} summary: {domain_processed} samples, {domain_qa_pairs} QA pairs")
    
    # 最终统计
    logger.info("\n" + "=" * 80)
    logger.info("Final Summary")
    logger.info("=" * 80)
    logger.info(f"Total samples processed: {total_processed}")
    logger.info(f"Total QA pairs generated: {total_qa_pairs}")
    logger.info(f"Average QA pairs per sample: {total_qa_pairs/total_processed:.1f}" if total_processed > 0 else "N/A")
    
    logger.info("\nNote: QA pairs saved to individual qa_pairs.json files.")
    logger.info("Run generate_dataset_json to update dataset.json with QA pairs.")


def main():
    parser = argparse.ArgumentParser(
        description="Task 1: Generate QA pairs for CodeVQA evaluation"
    )
    
    parser.add_argument('command', choices=['generate-all'],
                        help='Command to execute')
    parser.add_argument('--source', type=Path, required=True,
                        help='Source directory (task1_benchmark)')
    parser.add_argument('--num-questions', type=int, default=3,
                        help='Number of questions per sample (default: 3, must include counting, identification, relationship)')
    parser.add_argument('--model', type=str, default='gemini-3-pro-preview',
                        help='QA generation model (default: gemini-3-pro-preview)')
    parser.add_argument('--resume', action='store_true', default=True,
                        help='Resume from last checkpoint (default: True)')
    parser.add_argument('--no-resume', dest='resume', action='store_false',
                        help='Do not resume, reprocess all')
    
    args = parser.parse_args()
    
    # Validate
    if not args.source.exists():
        logger.error(f"Source directory not found: {args.source}")
        return 1
    
    if args.command == 'generate-all':
        try:
            process_all_samples(
                source_dir=args.source,
                num_questions=args.num_questions,
                generation_model=args.model,
                resume=args.resume
            )
            return 0
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
