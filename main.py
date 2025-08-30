import argparse
import os
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
	parser.add_argument("--output-dir", help="Path to the export directory (defaults to project path).")

	parser.add_argument(
		"--log-level",
		choices=["off", "info", "debug", "trace", "error", "warning"],
		default="off",
		help="Set the logging level."
	)

	parser.add_argument("--log-file", help="Name of the log file (without extension). Defaults to config value.")
	parser.add_argument("--types-file", help="Name of the types JSON file (without extension). Defaults to config value.")
	parser.add_argument("--clear-cache", action="store_true", help="Clear the typify cache before running.")
	parser.add_argument("--prune-cache", action="store_true", help="Prune stale entries from the typify cache after setup.")

	return parser.parse_args()

def main():
	config_path = "typifyconfig.json"
	args = parse_args()

	project_dir = args.project_dir
	output_dir = args.output_dir or (project_dir + "/.typify")

	if not Utils.is_valid_directory(project_dir):
		print("Invalid project path given.")
		exit(1)

	if not Utils.is_valid_directory(output_dir):
		os.makedirs(output_dir, exist_ok=True)

	with open(config_path, "r") as f:
		config: dict[str, Union[str, dict[str, str]]] = json.load(f)

	project_dir = Path(project_dir).resolve()
	output_dir = Path(output_dir).resolve()
	cache_path = config["cache_dir"] if config["cache_dir"] != "{auto}" else GlobalCache.get_system_cache()
	cache_path = Path(cache_path).resolve()
	types_file_name = "types"
	log_file_name = "typify"

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
		logger.add_output(
			open(Path(output_dir) / f"{log_file_name}.log", "w", encoding="utf-8")
		)

	Preloader.load(
		cache_path,
		args.clear_cache,
		config,
		project_dir
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

	next(iter(GlobalContext.libs.values())).export_types(
		Path(output_dir) / f"{types_file_name}.json"
	)
	export_path_show = Path(Path(output_dir) / f"{types_file_name}.json").as_posix()
	logger.info(f"{logger.emoji_map['ok']} Exported types to: {export_path_show}")

	if GlobalCache.staged_contexts:
		len_staged_ctxs = len(GlobalCache.staged_contexts)
		GlobalCache.flush_inference_contexts(cache_path)
		logger.debug(f"{logger.emoji_map['ok']} [Cache] Flushed {len_staged_ctxs} staged context(s) to disk.", trail=1)

	logger.close()

if __name__ == "__main__":
	main()
