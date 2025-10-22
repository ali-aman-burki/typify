from __future__ import annotations
import ast
import json
from pathlib import Path
from typing import Dict, List, Any
from tqdm import tqdm
from typify.preprocessing.typeexpr import parse_typeexpr


def extract_context(source: str, node: ast.AST, window: int = 2) -> str:
    """Extract a short snippet of source code around the given node."""
    lines = source.splitlines()
    lineno = getattr(node, "lineno", None)
    if lineno is None or lineno > len(lines):
        return ""
    start = max(0, lineno - window)
    end = min(len(lines), lineno + window)
    context = " ".join(lines[start:end])
    tokens = [t for t in context.split() if len(t) < 50]
    return " ".join(tokens[:40])


def build_index(train_list_file: str, output_json: str):
    """
    Build a JSON index mapping canonicalized types to lists of
    small code contexts where they appear.

    Args:
        train_list_file: Path to a text file listing Python source paths.
        output_json: Path to save the resulting JSON index.
    """
    train_list_path = Path(train_list_file)
    if not train_list_path.exists():
        raise FileNotFoundError(f"Training list file not found: {train_list_path}")

    # Read all file paths
    with open(train_list_path, "r", encoding="utf8") as f:
        files = [Path("/media/ali/T7/datasets/mt4py/repos/"+line.strip()) for line in f if line.strip()]

    if not files:
        print("⚠️ No valid files listed in training file.")
        return

    type_index: Dict[str, List[Dict[str, Any]]] = {}

    print(f"📦 Building type index from {len(files)} files...")
    for path in tqdm(files, desc="Indexing"):
        if not path.exists() or not path.suffix == ".py":
            continue
        try:
            source = path.read_text(encoding="utf8")
            tree = ast.parse(source, filename=str(path))
        except Exception as e:
            print(f"⚠️ Skipping {path}: {e}")
            continue

        for node in ast.walk(tree):
            # --- Variable annotations ---
            if isinstance(node, ast.AnnAssign) and isinstance(node.annotation, ast.expr):
                try:
                    ann_src = ast.unparse(node.annotation)
                    typ = str(parse_typeexpr(ann_src).canonical())
                    ctx = extract_context(source, node)
                    type_index.setdefault(typ, []).append({
                        "context": ctx,
                        "file": str(path)
                    })
                except Exception:
                    pass

            # --- Function definitions (params + return types) ---
            elif isinstance(node, ast.FunctionDef):
                # parameters
                for arg in node.args.args:
                    if arg.annotation:
                        try:
                            ann_src = ast.unparse(arg.annotation)
                            typ = str(parse_typeexpr(ann_src).canonical())
                            ctx = extract_context(source, node)
                            type_index.setdefault(typ, []).append({
                                "context": f"def {node.name}(..., {arg.arg}: {ann_src}, ...)",
                                "file": str(path)
                            })
                        except Exception:
                            pass
                # return type
                if node.returns:
                    try:
                        ann_src = ast.unparse(node.returns)
                        typ = str(parse_typeexpr(ann_src).canonical())
                        ctx = extract_context(source, node)
                        type_index.setdefault(typ, []).append({
                            "context": f"def {node.name}() -> {ann_src}",
                            "file": str(path)
                        })
                    except Exception:
                        pass

    with open(output_json, "w", encoding="utf-8") as out:
        json.dump(type_index, out, indent=2, ensure_ascii=False)

    print(f"✅ Type index written to: {output_json} ({len(type_index)} unique types)")
