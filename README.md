# VCG-Bench

VCG-Bench is a benchmark and evaluation toolkit for visual-centric diagram generation and editing with editable Draw.io `mxGraph` XML.

It covers two workflows:

- **Task 1: Vision-to-XML Generation**: reconstruct editable `mxGraph` XML from a diagram image.
- **Task 2: Instruction-based XML Editing**: modify an existing XML diagram according to a natural-language instruction.

The full Task 1 dataset is distributed separately on Hugging Face as parquet. This repository contains code, prompts, evaluation logic, and lightweight Task 1/Task 2 demo samples.

## What Is Included

```text
configs/      Prompt and runtime configuration.
eval/         Task 1 and Task 2 evaluation metrics.
examples/     Tiny sample data for smoke tests.
scripts/      Generation, rendering, data preparation, and utility scripts.
src/          Shared IO, rendering, LLM client, and processing code.
docs/         Setup and metric documentation.
```

Generated data, logs, local model caches, and full benchmark files are intentionally ignored by Git.

## Installation

Use Python 3.10+.

```bash
git clone <repo-url>
cd VCG-Bench

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

Set an OpenAI-compatible vision endpoint in `.env`:

```bash
CUSTOM_API_KEY=your_api_key_here
CUSTOM_BASE_URL=https://your-endpoint/v1
CUSTOM_VISION_MODEL=gemini-3-pro-preview
```

### Draw.io Setup

Draw.io Desktop/CLI is required when rendering XML to PNG and for execution-success metrics that need to render XML. Install it before running generation/evaluation without `--skip-render`.

macOS:

```bash
brew install --cask drawio
```

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install drawio
```

Linux without root access can use the Draw.io AppImage. See [docs/DRAWIO_LINUX_SETUP.md](docs/DRAWIO_LINUX_SETUP.md).

Verify that VCG-Bench can find Draw.io:

```bash
python - <<'PY'
from src.renderer.drawio_renderer import DrawioRenderer
r = DrawioRenderer()
print(r.drawio_path)
print("can_render=", r.can_render())
PY
```

If auto-detection fails, set `DRAWIO_PATH` in `.env`, for example:

```bash
DRAWIO_PATH=/Applications/draw.io.app/Contents/MacOS/draw.io
```

If Draw.io is unavailable, use `--skip-render` for generation and restrict evaluation to metrics that do not need rendered images.

## Smoke Tests

Run Task 1 evaluation on the bundled demo sample without any API call:

```bash
python eval/run_evaluation.py task1 \
  --benchmark examples/task1_demo \
  --output outputs/task1_demo_eval \
  --models gemini-3-pro-preview \
  --metrics execution_success_rate xml_token_count
```

Expected output files include:

```text
outputs/task1_demo_eval/detailed_results.json
outputs/task1_demo_eval/all_models_comparison.csv
outputs/task1_demo_eval/all_models_summary_statistics.csv
```

Run Task 2 evaluation on the bundled no-op editing demo without any API call:

```bash
python eval/run_evaluation.py task2 \
  --benchmark examples/task2_demo \
  --output outputs/task2_demo_eval \
  --models gemini-3-pro-preview \
  --metrics modified_xml_execution_success_rate modified_xml_token_count modification_json_token_count xml_edit_distance
```

Expected output files include:

```text
outputs/task2_demo_eval/detailed_results.json
outputs/task2_demo_eval/all_models_comparison.csv
outputs/task2_demo_eval/all_models_summary_statistics.csv
outputs/task2_demo_eval/all_models_by_instruction_difficulty.csv
```

## Single Image Generation

Generate a description and XML for one image:

```bash
python scripts/task1/process_single_image.py \
  examples/task1_demo/domain_management_domain_gantt/sample_0011/original.png \
  --provider custom \
  --model gemini-3-pro-preview \
  --output outputs/single_image_demo
```

Evaluate the generated XML with lightweight metrics:

```bash
python scripts/task1/evaluate_single_image.py \
  --output outputs/single_image_demo \
  --model gemini-3-pro-preview \
  --skip-render
```

Expected generated files:

```text
outputs/single_image_demo/original.png
outputs/single_image_demo/model_gemini-3-pro-preview/llm_description.txt
outputs/single_image_demo/model_gemini-3-pro-preview/diagram.xml
outputs/single_image_demo/model_gemini-3-pro-preview/rendered.png
outputs/single_image_demo/stats.json
outputs/single_image_demo/evaluation.json
```

`rendered.png` is produced when Draw.io is installed and generation is run without `--skip-render`.

## Batch Task 1

Prepare images under domain folders:

```text
data/raw_picture/
└── domain_example/
    └── image_001.png
```

Run generation:

```bash
./task1.sh gemini-3-pro-preview \
  --source data/raw_picture \
  --target data/task1_benchmark \
  --skip-render \
  --skip-eval
```

Run lightweight evaluation after model outputs exist:

```bash
python eval/run_evaluation.py task1 \
  --benchmark data/task1_benchmark \
  --output outputs/task1_eval \
  --models gemini-3-pro-preview \
  --metrics execution_success_rate xml_token_count
```

To run VLM-based SCS/CodeVQA, provide API credentials and omit the restricted `--metrics` list. To skip SigLIP on machines without the model/GPU:

```bash
./scripts/commands/task1_evaluate.sh gemini-3-pro-preview \
  --disable-metrics siglip_score
```

## Data

The released Task 1 parquet contains 1,449 samples across 6 coarse domains and 15 sub-domains. See [DATA.md](DATA.md) for the exact schema.

Expected Task 1 directory layout:

```text
data/task1_benchmark/
├── dataset.json
└── domain_.../
    └── sample_0001/
        ├── original.png
        ├── metadata.json
        ├── qa_pairs.json
        └── model_<model-name>/
            ├── diagram.xml
            ├── llm_description.txt
            └── rendered.png
```

Expected Task 2 directory layout:

```text
data/task2_benchmark/
└── domain_.../
    └── sample_0001/
        ├── diagram.xml
        ├── rendered.png
        ├── metadata.json
        └── instructions/
            └── inst_easy_001/
                ├── instruction.txt
                ├── instruction_metadata.json
                ├── question_set.json
                └── model_<model-name>/
                    ├── model_output.json
                    ├── modified.xml
                    └── modified.png
```

`question_set.json` is required for XDRFR, while the lightweight smoke test above does not need it.

## Task 2 Viewer

After Task 2 data exists locally:

```bash
./viewer.sh task2 review
```

Task 1 screening uses:

```bash
./viewer.sh task1 review
```

## License

Code is released under the MIT License. Dataset files are intended for release under CC BY 4.0 unless a future dataset card states otherwise.

## Citation

Please cite VCG-Bench if you use this benchmark. The formal BibTeX entry should be added after camera-ready metadata is finalized.
