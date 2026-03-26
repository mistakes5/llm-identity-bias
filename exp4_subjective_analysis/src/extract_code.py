"""Extract Python code blocks from LLM markdown responses."""

import ast
import re
import argparse
from pathlib import Path

from .utils import save_json, load_json, setup_logging, ensure_dirs


def extract_code_blocks(response_text: str) -> list[str]:
    """
    Extract all code blocks from markdown response.
    Strategy:
    1. Try ```python ... ``` blocks first
    2. Fall back to untagged ``` ... ``` blocks
    3. Last resort: indented blocks (4+ spaces after blank line)
    Filter out blocks that are clearly not Python (contain HTML, shell commands, etc.)
    """
    # Primary: tagged python blocks
    blocks = re.findall(r'```python\s*\n(.*?)```', response_text, re.DOTALL)
    if blocks:
        return [b.strip() for b in blocks if b.strip()]

    # Fallback: untagged code blocks
    blocks = re.findall(r'```\s*\n(.*?)```', response_text, re.DOTALL)
    if blocks:
        # Filter to likely-Python blocks (contain def, class, import, or = )
        py_blocks = [b.strip() for b in blocks
                     if b.strip() and any(kw in b for kw in ['def ', 'class ', 'import ', ' = ', 'print('])]
        if py_blocks:
            return py_blocks
        return [b.strip() for b in blocks if b.strip()]

    # Last resort: indented blocks
    lines = response_text.split('\n')
    current_block = []
    blocks = []
    for line in lines:
        if line.startswith('    ') or line.startswith('\t'):
            current_block.append(line)
        elif current_block:
            block = '\n'.join(current_block).strip()
            if block and len(block) > 20:
                blocks.append(block)
            current_block = []
    if current_block:
        block = '\n'.join(current_block).strip()
        if block and len(block) > 20:
            blocks.append(block)
    return blocks


def merge_code_blocks(blocks: list[str]) -> str:
    """
    Merge multiple code blocks into one, deduplicating imports.
    For Task 5 (refactor), take the largest block as the main solution.
    """
    if len(blocks) == 1:
        return blocks[0]

    # Strategy: concatenate all blocks, dedup import lines
    seen_imports = set()
    merged_lines = []

    for block in blocks:
        for line in block.split('\n'):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')):
                if stripped not in seen_imports:
                    seen_imports.add(stripped)
                    merged_lines.append(line)
            else:
                merged_lines.append(line)
        merged_lines.append('')  # separator

    return '\n'.join(merged_lines).strip()


def validate_syntax(code: str) -> tuple[bool, str | None]:
    """Try ast.parse(). Returns (True, None) on success, (False, error_msg) on failure."""
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"


def extract_all(raw_dir: str, extracted_dir: str, logger=None) -> dict:
    """
    Process all raw response JSONs, extract code, save as .py files.
    Returns summary dict.
    """
    ensure_dirs(extracted_dir)
    raw_path = Path(raw_dir)
    ext_path = Path(extracted_dir)
    summary = {}

    for f in sorted(raw_path.glob("*.json")):
        stem = f.stem  # e.g. sonnet_A_task1_run1
        data = load_json(str(f))
        response_text = data["response_text"]

        blocks = extract_code_blocks(response_text)

        if not blocks:
            if logger:
                logger.warning(f"No code blocks found in {f.name}")
            # Save empty file with warning
            code = "# NO CODE BLOCKS EXTRACTED"
            valid = False
            error = "No code blocks found"
        else:
            code = merge_code_blocks(blocks)
            valid, error = validate_syntax(code)

        # Save extracted code
        suffix = ".py" if valid else ".py"  # save as .py either way for metrics
        out_file = ext_path / f"{stem}.py"
        out_file.write_text(code)

        # Save metadata
        meta = {
            "source": f.name,
            "n_blocks": len(blocks),
            "syntax_valid": valid,
            "syntax_error": error,
            "code_lines": len(code.split('\n')),
            "code_chars": len(code),
        }
        save_json(meta, str(ext_path / f"{stem}_meta.json"))

        summary[stem] = meta

        if logger:
            status = "OK" if valid else f"SYNTAX ERROR: {error}"
            logger.info(f"{f.name}: {len(blocks)} blocks, {meta['code_lines']} lines, {status}")

    if logger:
        total = len(summary)
        valid_count = sum(1 for m in summary.values() if m["syntax_valid"])
        logger.info(f"Extraction complete: {valid_count}/{total} valid syntax ({valid_count/max(1,total)*100:.0f}%)")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Extract code from experiment responses")
    parser.add_argument("--raw-dir", default="results/raw")
    parser.add_argument("--output-dir", default="results/extracted")
    args = parser.parse_args()

    logger = setup_logging("results", "extract_code")
    extract_all(args.raw_dir, args.output_dir, logger=logger)


if __name__ == "__main__":
    main()
