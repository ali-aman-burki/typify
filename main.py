import argparse
import json
import shutil

from pathlib import Path
from typing import Union

from typify.utils import Utils
from typify.preprocessing.preloader import Preloader
from typify.preprocessing.core import GlobalContext
from typify.inferencing.inferencer import Inferencer
from typify.caching import GlobalCache
from typify.logging import (
	logger,
	LogLevel
)

def parse_args():
	parser = argparse.ArgumentParser(
		description="Build and export type bindings for a Python project."
	)

	parser.add_argument("project_dir", help="Path to the Python project directory.")

	parser.add_argument(
		"--output-dir",
		help="Directory where outputs (types + log) will be written. Defaults to <project_dir>/.typify",
	)

	parser.add_argument(
		"--relative-to",
		help="Path to compute relative source paths against when naming export files. "
			 "Defaults to project_dir.",
	)

	parser.add_argument(
		"--log-level",
		choices=["off", "info", "debug", "trace", "error", "warning"],
		default="off",
		help="Set the logging level.",
	)

	parser.add_argument("--clear-cache", action="store_true", help="Clear the typify cache before running.")
	parser.add_argument("--prune-cache", action="store_true", help="Prune stale entries from cache after setup.")
	parser.add_argument("--dont-cache", action="store_true", help="Prevent saving results to cache.")
	parser.add_argument("--clear-output", action="store_true", help="Clear the output directory before running.")
	parser.add_argument("--heur", action="store_true", help="Run hueristics-driven type prediction.")
	parser.add_argument("--usage", action="store_true", help="Run usage-driven type prediction.")

	return parser.parse_args()

def get_next_logfile(log_file: Path) -> Path:
    base_name = log_file.stem
    ext = log_file.suffix

    existing_logs = list(log_file.parent.glob(f"{base_name}*{ext}"))

    if not existing_logs:
        return log_file

    indices = []
    for lf in existing_logs:
        stem = lf.stem
        if stem == base_name:
            indices.append(None)
        elif "_" in stem:
            try:
                indices.append(int(stem.split("_")[-1]))
            except ValueError:
                pass

    if None in indices and all(isinstance(i, int) and i == 0 for i in indices if i is not None):
        old_log = log_file
        if old_log.exists():
            old_log.replace(log_file.parent / f"{base_name}_0{ext}")
        return log_file.parent / f"{base_name}_1{ext}"

    numeric_indices = [i for i in indices if isinstance(i, int)]
    next_index = (max(numeric_indices) if numeric_indices else 0) + 1
    return log_file.parent / f"{base_name}_{next_index}{ext}"

def main():
	config_path = "typifyconfig.json"
	args = parse_args()

	project_dir = Path(args.project_dir).resolve()
	default_outdir = project_dir / ".typify"
	outdir = Path(args.output_dir).resolve() if args.output_dir else default_outdir

	relative_to = Path(args.relative_to).resolve() if args.relative_to else project_dir

	if not Utils.is_valid_directory(project_dir):
		print("Invalid project path given.")
		exit(1)

	with open(config_path, "r") as f:
		config: dict[str, Union[str, dict[str, str]]] = json.load(f)

	cache_path = config["cache_dir"] if config["cache_dir"] != "{auto}" else GlobalCache.get_system_cache()
	cache_path = Path(cache_path).resolve()

	if args.clear_output and outdir.exists():
		shutil.rmtree(outdir)

	outdir.mkdir(parents=True, exist_ok=True)

	log_file = get_next_logfile(outdir / "typify.log")

	log_levels = {
		"off": LogLevel.OFF,
		"info": LogLevel.INFO,
		"debug": LogLevel.DEBUG,
		"trace": LogLevel.TRACE,
		"error": LogLevel.ERROR,
		"warning": LogLevel.WARNING,
	}
	logger.set_level(log_levels[args.log_level])
	if logger.level != LogLevel.OFF:
		logger.add_output(open(log_file, "w", encoding="utf-8"))

	Preloader.load(
		cache_path=cache_path,
		clear_cache=args.clear_cache,
		dont_cache=args.dont_cache,
		config=config,
		project_dir=project_dir,
	)

	if args.prune_cache:
		GlobalCache.prune()

	logger.info(f"{logger.emoji_map['summary']} Libraries loaded:", 1)
	for libpath in GlobalContext.libs:
		logger.info(f"   {libpath.as_posix()}")

	logger.info(f"{logger.emoji_map['graph']} Dependency Graph:", 1)
	for meta, deps in GlobalContext.dependency_graph.items():
		joined = ", ".join(repr(dep) for dep in deps)
		logger.info(f"   {repr(meta)} ➜ [{joined}]")

	Inferencer.infer(
		outdir=outdir, 
		relative_to=relative_to, 
		normalize=True,
		usage_driven=args.usage,
		heur_driven=args.heur
	)

	if GlobalCache.staged_contexts:
		len_staged_ctxs = len(GlobalCache.staged_contexts)
		GlobalCache.flush_inference_contexts(cache_path)
		logger.debug(f"{logger.emoji_map['ok']} [Cache] Flushed {len_staged_ctxs} staged context(s) to disk.", trail=1)

	logger.close()

if __name__ == "__main__":
	main()