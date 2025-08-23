import argparse
import os
import json

from typing import Union
from pathlib import Path

from typify.utils import Utils
from typify.preprocessing.preloader import Preloader
from typify.preprocessing.core import GlobalContext
from typify.inferencing.inferencer import Inferencer
from typify.logging import (
    logger, 
    LogLevel
)

config_path = "typifyconfig.json"

parser = argparse.ArgumentParser(description="Build and export type bindings for a Python project.")
parser.add_argument(
    "project_dir", 
    help="Path to the Python project directory."
)
parser.add_argument(
    "-o", 
    "--output-dir", 
    help="Path to the export directory (defaults to project path)."
)
parser.add_argument(
    "-l", 
    "--log", 
    choices=["off", "info", "debug", "trace", "error", "warning"], 
    default="off", 
    help="Set the logging level."
)
parser.add_argument(
    "--types-file", 
    help="Name of the types JSON file (without extension). Defaults to config value."
)
parser.add_argument(
    "--log-file", 
    help="Name of the log file (without extension). Defaults to config value."
)

args = parser.parse_args()

project_dir = args.project_dir
output_dir = args.output_dir or (project_dir + "/.typify")

if not Utils.is_valid_directory(project_dir):
    print("Invalid project path given.")
    exit(1)

if not Utils.is_valid_directory(output_dir):
    os.makedirs(output_dir, exist_ok=True)

with open(config_path, "r") as f:
    config: dict[str, Union[str, dict[str, str]]] = json.load(f)

types_file_name = args.types_file or config["outputs"]["types"]
log_file_name = args.log_file or config["outputs"]["log"]
cache_dir = config["cache"]

log_levels = {
    "off": LogLevel.OFF,
    "info": LogLevel.INFO,
    "debug": LogLevel.DEBUG,
    "trace": LogLevel.TRACE,
    "error": LogLevel.ERROR,
    "warning": LogLevel.WARNING,
}
logger.set_level(log_levels[args.log])
if logger.level != LogLevel.OFF:
    logger.add_output(
        open(Path(output_dir) / f"{log_file_name}.log", "w", encoding="utf-8")
    )

print(Utils.title)

Preloader.load(
    config, 
    Path(project_dir),
    Path(cache_dir)
)

logger.info("📦 Libraries loaded:", 1)
for libmeta in GlobalContext.libs:
    logger.info(f"{str(libmeta.src)}")

logger.info("🧩 Dependency Graph:", 1)
for meta, deps in GlobalContext.dependency_graph.items():
    joined = ", ".join(repr(dep) for dep in deps)
    logger.info(f"  {repr(meta)} -> [{joined}]")

Inferencer.infer()

GlobalContext.libs[0].export_types(
    Path(output_dir) / f"{types_file_name}.json"
)

logger.close()