"""
Dataset loader - load and iterate over processed datasets
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Iterator, Dict, Any

from ..core.models import ProcessingResult, PaperMetadata, ImageInfo

logger = logging.getLogger(__name__)


class DatasetLoader:
    """
    Load and iterate over processed datasets
    Useful for Jupyter notebooks and post-processing
    """

    def __init__(self, dataset_root: Path):
        """
        Args:
            dataset_root: Root directory of processed dataset
        """
        self.dataset_root = Path(dataset_root)
        if not self.dataset_root.exists():
            raise FileNotFoundError(f"Dataset root not found: {dataset_root}")

    def list_batches(self) -> List[str]:
        """List all batch/paper names in dataset"""
        batches = [d.name for d in self.dataset_root.iterdir() if d.is_dir()]
        logger.info(f"Found {len(batches)} batches in {self.dataset_root}")
        return batches

    def load_batch(self, batch_name: str) -> List[ProcessingResult]:
        """
        Load all results from a batch

        Args:
            batch_name: Name of batch directory

        Returns:
            List of ProcessingResult objects
        """
        batch_dir = self.dataset_root / batch_name
        if not batch_dir.exists():
            raise FileNotFoundError(f"Batch not found: {batch_dir}")

        logger.info(f"Loading batch: {batch_name}")

        results = []
        for result_dir in sorted(batch_dir.iterdir()):
            if not result_dir.is_dir() or not result_dir.name.startswith("image_"):
                continue

            try:
                result = self.load_result(result_dir)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to load result from {result_dir}: {e}")

        logger.info(f"Loaded {len(results)} results from {batch_name}")
        return results

    def load_result(self, result_dir: Path) -> ProcessingResult:
        """
        Load a single processing result

        Args:
            result_dir: Directory containing result files

        Returns:
            ProcessingResult object
        """
        result_dir = Path(result_dir)

        # Try to load complete result.json first
        result_json = result_dir / "result.json"
        if result_json.exists():
            with open(result_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return ProcessingResult.from_dict(data)

        # Otherwise, reconstruct from individual files
        logger.debug(f"Reconstructing result from {result_dir}")

        # Load image metadata
        meta_path = result_dir / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"meta.json not found in {result_dir}")

        with open(meta_path, 'r', encoding='utf-8') as f:
            image_data = json.load(f)
        image_info = ImageInfo.from_dict(image_data)

        # Load description if available
        from ..core.models import StructuredDescription
        description = None
        desc_path = result_dir / "llm_description.json"
        if desc_path.exists():
            with open(desc_path, 'r', encoding='utf-8') as f:
                desc_data = json.load(f)
            description = StructuredDescription.from_dict(desc_data)

        # Load diagram if available
        from ..core.models import DiagramXML
        diagram = None
        xml_path = result_dir / "diagram.xml"
        diagram_meta_path = result_dir / "diagram_meta.json"

        if xml_path.exists():
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()

            if diagram_meta_path.exists():
                with open(diagram_meta_path, 'r', encoding='utf-8') as f:
                    diagram_data = json.load(f)
                diagram_data['xml_content'] = xml_content
                diagram = DiagramXML.from_dict(diagram_data)
            else:
                # Minimal diagram object
                diagram = DiagramXML(xml_content=xml_content, diagram_type='unknown')

        # Check for rendered image
        rendered_path = result_dir / "diagram_drawio.png"
        if not rendered_path.exists():
            rendered_path = None

        # Reconstruct result
        result = ProcessingResult(
            image_info=image_info,
            description=description,
            description_success=description is not None,
            diagram=diagram,
            diagram_success=diagram is not None,
            rendered_path=rendered_path,
            rendering_success=rendered_path is not None
        )

        return result

    def load_metadata(self, batch_name: str) -> Optional[PaperMetadata]:
        """
        Load paper/batch metadata

        Args:
            batch_name: Name of batch directory

        Returns:
            PaperMetadata object or None
        """
        batch_dir = self.dataset_root / batch_name
        metadata_path = batch_dir / "metadata.json"

        if not metadata_path.exists():
            logger.debug(f"No metadata found for {batch_name}")
            return None

        with open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return PaperMetadata.from_dict(data)

    def load_summary(self, batch_name: str) -> Optional[Dict[str, Any]]:
        """
        Load batch summary

        Args:
            batch_name: Name of batch directory

        Returns:
            Summary dict or None
        """
        batch_dir = self.dataset_root / batch_name
        summary_path = batch_dir / "summary.json"

        if not summary_path.exists():
            logger.debug(f"No summary found for {batch_name}")
            return None

        with open(summary_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def iter_all_results(self) -> Iterator[ProcessingResult]:
        """
        Iterate over all results in the dataset

        Yields:
            ProcessingResult objects from all batches
        """
        for batch_name in self.list_batches():
            try:
                for result in self.load_batch(batch_name):
                    yield result
            except Exception as e:
                logger.error(f"Failed to load batch {batch_name}: {e}")

    def load_screening_review(self, review_path: Path) -> List[Dict[str, Any]]:
        """
        Load screening review JSON for human review

        Args:
            review_path: Path to review JSON file

        Returns:
            List of review items
        """
        review_path = Path(review_path)
        if not review_path.exists():
            raise FileNotFoundError(f"Review file not found: {review_path}")

        with open(review_path, 'r', encoding='utf-8') as f:
            review_data = json.load(f)

        logger.info(f"Loaded {len(review_data)} items from review file")
        return review_data

    def get_approved_images(self, review_path: Path) -> List[str]:
        """
        Get list of approved image paths from review

        Args:
            review_path: Path to review JSON file

        Returns:
            List of approved image paths
        """
        review_data = self.load_screening_review(review_path)
        approved = [item['image_path'] for item in review_data if item.get('approved', False)]

        logger.info(f"Found {len(approved)} approved images")
        return approved

    def export_to_json(self, output_path: Path, batch_names: Optional[List[str]] = None):
        """
        Export dataset to a single JSON file

        Args:
            output_path: Output JSON file path
            batch_names: Optional list of batch names to include (all if None)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if batch_names is None:
            batch_names = self.list_batches()

        logger.info(f"Exporting {len(batch_names)} batches to {output_path}")

        dataset = {
            "dataset_root": str(self.dataset_root),
            "batches": []
        }

        for batch_name in batch_names:
            try:
                results = self.load_batch(batch_name)
                metadata = self.load_metadata(batch_name)
                summary = self.load_summary(batch_name)

                batch_data = {
                    "batch_name": batch_name,
                    "metadata": metadata.to_dict() if metadata else None,
                    "summary": summary,
                    "results": [r.to_dict() for r in results]
                }

                dataset["batches"].append(batch_data)

            except Exception as e:
                logger.error(f"Failed to export batch {batch_name}: {e}")

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported dataset to {output_path}")
