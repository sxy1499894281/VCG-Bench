# Data

The full benchmark data is released separately from the code repository.

## Task 1 Parquet Release

The Task 1 parquet release contains 1,449 diagram image samples. QA pairs, generated model outputs, and evaluation outputs are not included in this parquet file.

Actual columns:

| Column | Type | Description |
|---|---|---|
| `image_id` | string | Globally unique image identifier, e.g. `academic_architecture_sample_0001`. |
| `domain_l1` | string | Coarse domain label: `academic`, `business`, `general`, `management`, `software`, or `uiux`. |
| `domain_l2` | string | Sub-domain label, e.g. `architecture`, `strategy`, `uml`. |
| `image` | struct | Hugging Face image-compatible `{bytes, path}` struct. |
| `image_description` | string | Structured visual description used during data construction. |
| `restored_xml` | string | Restored Draw.io `mxGraph` XML. Empty for samples where XML is unavailable. |
| `xml_token_count` | int | Approximate token count of `restored_xml`. |

Dataset size:

- Samples: 1,449
- Coarse domains: 6
- Sub-domains: 15
- Rows with non-empty `restored_xml`: 1,444
- Rows without `restored_xml`: 5

Domain distribution:

| Coarse domain | Samples |
|---|---:|
| `academic` | 367 |
| `business` | 545 |
| `general` | 54 |
| `management` | 153 |
| `software` | 221 |
| `uiux` | 109 |

Load locally:

```python
from datasets import load_dataset

ds = load_dataset("parquet", data_files="data/train.parquet", split="train")
sample = ds[0]

print(sample["image_id"])
print(sample["domain_l1"], sample["domain_l2"])
print(sample["image"])
print(sample["restored_xml"][:200])
```

Keep downloaded datasets under `data/`; this directory is ignored by Git.

## Local Task 1 Directory Layout

The code evaluation pipeline expects generated outputs in this format:

```text
data/task1_benchmark/
└── domain_.../
    └── sample_0001/
        ├── original.png
        ├── metadata.json
        ├── qa_pairs.json
        └── model_<model-name>/
            ├── diagram.xml
            ├── llm_description.txt
            ├── performance.json
            └── rendered.png
```

`rendered.png` is required for image-based metrics such as execution success via existing render output and SCS. Use `--metrics execution_success_rate xml_token_count` for a lightweight no-API smoke test.

## Task 2 Data

Task 2 data is prepared locally from high-quality Task 1 XML outputs and editing instructions. The public release status of Task 2 data should be documented in the dataset card when it is uploaded.

Expected local layout:

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

`modified.png` is required by execution-success and image-based Task 2 metrics. Use `scripts/render/batch_render.py task2` to render `modified.xml` files after model editing outputs are generated. `question_set.json` is required for XDRFR; lightweight local tests can use only `modified_xml_execution_success_rate`, `modified_xml_token_count`, `modification_json_token_count`, and `xml_edit_distance`.
