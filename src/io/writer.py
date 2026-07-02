"""
Dataset writer - save processing results to disk
"""

import json
import logging
import shutil
from pathlib import Path
from typing import List, Optional

from ..core.models import ProcessingResult, PaperMetadata

logger = logging.getLogger(__name__)


class DatasetWriter:
    """
    Write processing results to organized directory structure
    """

    def __init__(self, output_root: Path):
        """
        Args:
            output_root: Root directory for output
        """
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

    def write_result(
        self,
        result: ProcessingResult,
        result_dir: Path,
        copy_original: bool = True
    ):
        """
        Write a single processing result

        Creates structure:
        result_dir/
          ├── image.png             (original image)
          ├── meta.json             (image metadata)
          ├── llm_description.json  (if available)
          ├── diagram.xml           (if available)
          └── diagram_drawio.png    (if available)

        Args:
            result: Processing result
            result_dir: Output directory for this result
            copy_original: Whether to copy original image
        """
        result_dir = Path(result_dir)
        result_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Writing result to {result_dir}")

        # Copy original image
        if copy_original and result.image_info.path.exists():
            dest_image = result_dir / "image.png"
            if not dest_image.exists():
                shutil.copy2(result.image_info.path, dest_image)
                logger.debug(f"Copied image to {dest_image}")

        # Write image metadata
        meta_path = result_dir / "meta.json"
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(result.image_info.to_dict(), f, indent=2, ensure_ascii=False)

        # Write description
        if result.description:
            desc_path = result_dir / "llm_description.json"
            with open(desc_path, 'w', encoding='utf-8') as f:
                json.dump(result.description.to_dict(), f, indent=2, ensure_ascii=False)
            logger.debug(f"Wrote description to {desc_path}")

        # Write diagram XML
        if result.diagram:
            xml_path = result_dir / "diagram.xml"
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(result.diagram.xml_content)
            logger.debug(f"Wrote diagram XML to {xml_path}")

            # Write diagram metadata
            diagram_meta_path = result_dir / "diagram_meta.json"
            with open(diagram_meta_path, 'w', encoding='utf-8') as f:
                json.dump(result.diagram.to_dict(), f, indent=2, ensure_ascii=False)

        # Copy rendered diagram if available
        if result.rendered_path and result.rendered_path.exists():
            dest_render = result_dir / "diagram_drawio.png"
            if not dest_render.exists():
                shutil.copy2(result.rendered_path, dest_render)
                logger.debug(f"Copied render to {dest_render}")

        # Write complete result
        result_path = result_dir / "result.json"
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

    def write_batch(
        self,
        results: List[ProcessingResult],
        batch_name: str = "batch",
        paper_metadata: Optional[PaperMetadata] = None
    ) -> Path:
        """
        Write a batch of results

        Creates structure:
        output_root/<batch_name>/
          ├── metadata.json           (batch/paper metadata)
          ├── summary.json            (batch summary)
          ├── image_001/              (per-image directories)
          │   ├── image.png
          │   ├── meta.json
          │   └── ...
          ├── image_002/
          └── ...

        Args:
            results: List of processing results
            batch_name: Name for this batch
            paper_metadata: Optional paper metadata

        Returns:
            Path to batch directory
        """
        batch_dir = self.output_root / batch_name
        batch_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Writing batch of {len(results)} results to {batch_dir}")

        # Write individual results
        for i, result in enumerate(results):
            result_dir = batch_dir / f"image_{i+1:03d}"
            self.write_result(result, result_dir)

        # Write batch summary
        summary = {
            "total_images": len(results),
            "successful_descriptions": sum(1 for r in results if r.description_success),
            "successful_diagrams": sum(1 for r in results if r.diagram_success),
            "successful_renders": sum(1 for r in results if r.rendering_success),
            "candidates": sum(1 for r in results if r.is_candidate),
        }

        summary_path = batch_dir / "summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logger.info(f"Wrote summary: {summary}")

        # Write paper metadata if provided
        if paper_metadata:
            metadata_path = batch_dir / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(paper_metadata.to_dict(), f, indent=2, ensure_ascii=False)

        return batch_dir

    def write_screening_review(
        self,
        results: List[dict],
        output_path: Path
    ):
        """
        Write screening results for human review

        Format:
        [
          {
            "image_path": str,
            "filename": str,
            "is_candidate": bool,
            "score": float,
            "reason": str,
            "approved": bool,  # For human override
            "notes": str       # For human notes
          },
          ...
        ]

        Args:
            results: List of screening results with image_info
            output_path: Path to review JSON file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        review_data = []
        for item in results:
            image_info = item['image_info']
            screening = item['screening']

            review_data.append({
                "image_path": str(image_info.path),
                "filename": image_info.filename,
                "is_candidate": screening.get('is_candidate', False),
                "score": screening.get('score', 0.0),
                "reason": screening.get('reason', ''),
                "diagram_type": screening.get('diagram_type'),
                "approved": screening.get('is_candidate', False),  # Default to LLM decision
                "notes": ""
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(review_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Wrote screening review to {output_path}")

    def create_gallery(
        self,
        results: List[dict],
        gallery_dir: Path,
        include_rejected: bool = False,
        mode: str = 'symlink'
    ):
        """
        Create an image gallery for quick visual review

        Args:
            results: List of screening results with image_info
            gallery_dir: Output gallery directory
            include_rejected: Whether to include rejected images
            mode: 'symlink' or 'copy'
        """
        gallery_dir = Path(gallery_dir)
        gallery_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        keep_dir = gallery_dir / "candidates"
        reject_dir = gallery_dir / "rejected"
        keep_dir.mkdir(exist_ok=True)

        if include_rejected:
            reject_dir.mkdir(exist_ok=True)

        logger.info(f"Creating gallery at {gallery_dir} (mode={mode})")

        for item in results:
            image_info = item['image_info']
            screening = item['screening']
            is_candidate = screening.get('is_candidate', False)

            # Determine destination
            if is_candidate:
                dest_dir = keep_dir
            elif include_rejected:
                dest_dir = reject_dir
            else:
                continue

            # Copy or symlink
            dest_path = dest_dir / image_info.filename

            if mode == 'symlink':
                if not dest_path.exists():
                    dest_path.symlink_to(image_info.path.resolve())
            else:  # copy
                if not dest_path.exists():
                    shutil.copy2(image_info.path, dest_path)

        kept_count = len(list(keep_dir.iterdir()))
        rejected_count = len(list(reject_dir.iterdir())) if include_rejected else 0

        logger.info(f"Gallery created: {kept_count} candidates, {rejected_count} rejected")
