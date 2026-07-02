## Root Bash Script Archive

This directory stores bash scripts that were previously placed at the project root.

- No script content is modified.
- Files are only reorganized to keep the root directory clean.
- You can create root-level `task1` and `task2` orchestration scripts later to call these scripts in sequence.

If needed, run scripts from project root with paths like:

```bash
bash scripts/root_entrypoints/run_task1_data_generation.sh
bash scripts/root_entrypoints/run_task2_data_generation.sh
```
