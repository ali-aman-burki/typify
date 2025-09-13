import argparse
import json

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
		"--log-level",
		choices=["off", "info", "debug", "trace", "error", "warning"],
		default="off",
		help="Set the logging level."
	)

	parser.add_argument(
		"--log-file",
		help="Path (without extension) to the log file. Defaults to <project_dir>/.typify/typify(.json)."
	)
	parser.add_argument(
		"--types-file",
		help="Path (without extension) to the types JSON file. Defaults to <project_dir>/.typify/types(.log)."
	)
	parser.add_argument("--clear-cache", action="store_true", help="Clear the typify cache before running.")
	parser.add_argument("--prune-cache", action="store_true", help="Prune stale entries from the typify cache after setup.")
	parser.add_argument("--dont-cache", action="store_true", help="Prevent saving inference results to cache.")

	return parser.parse_args()

def main():
	config_path = "typifyconfig.json"
	args = parse_args()

	project_dir = Path(args.project_dir).resolve()
	default_outdir = project_dir / ".typify"

	if not Utils.is_valid_directory(project_dir):
		print("Invalid project path given.")
		exit(1)

	with open(config_path, "r") as f:
		config: dict[str, Union[str, dict[str, str]]] = json.load(f)

	cache_path = config["cache_dir"] if config["cache_dir"] != "{auto}" else GlobalCache.get_system_cache()
	cache_path = Path(cache_path).resolve()

	log_file = Path(args.log_file) if args.log_file else (default_outdir / "typify")
	types_file = Path(args.types_file) if args.types_file else (default_outdir / "types")

	log_file.parent.mkdir(parents=True, exist_ok=True)
	types_file.parent.mkdir(parents=True, exist_ok=True)

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
		logger.add_output(open(log_file.with_suffix(".log"), "w", encoding="utf-8"))

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

	Inferencer.infer()

	types_file.parent.mkdir(parents=True, exist_ok=True)
	next(iter(GlobalContext.libs.values())).export_types(
		types_file.with_suffix(".json")
	)
	
	logger.info(f"{logger.emoji_map['ok']} Exported types to: {types_file.with_suffix('.json').as_posix()}")

	if GlobalCache.staged_contexts:
		len_staged_ctxs = len(GlobalCache.staged_contexts)
		GlobalCache.flush_inference_contexts(cache_path)
		logger.debug(f"{logger.emoji_map['ok']} [Cache] Flushed {len_staged_ctxs} staged context(s) to disk.", trail=1)

	logger.close()

if __name__ == "__main__":
	main()
