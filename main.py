import argparse
import os
import json

from typing import Union
from pathlib import Path

from typify.utils import Utils
from typify.preprocessing.preloader import Preloader
from typify.preprocessing.core import GlobalContext
from typify.inferencing.inferencer import Inferencer
from typify.logging import logger, LogLevel

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
    choices=["off", "info", "debug", "trace"], 
    default="info", 
    help="Set the logging level."
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

log_levels = {
    "off": LogLevel.OFF,
    "info": LogLevel.INFO,
    "debug": LogLevel.DEBUG,
    "trace": LogLevel.TRACE,
}
logger.set_level(log_levels[args.log])
logger.add_output(open(Path(output_dir) / "typify.log", "w", encoding="utf-8"))

print(Utils.title)

Preloader.load(config, Path(project_dir))

logger.info("📦 Libraries loaded:", 1)
for libmeta in GlobalContext.libs:
    logger.info(f"{str(libmeta.src)}")

logger.info("🧩 Original Graph:", 1)
for meta, deps in GlobalContext.dependency_graph.items():
    joined = ", ".join(f"<{dep}>" if isinstance(dep, str) else repr(dep) for dep in deps)
    logger.info(f"  {repr(meta)} -> [{joined}]")

logger.info("🧹 Cleaned Graph:", 1)
for meta, deps in GlobalContext.cleaned_graph.items():
    joined = ", ".join(f"<{dep}>" if isinstance(dep, str) else repr(dep) for dep in deps)
    logger.info(f"  {repr(meta)} -> [{joined}]")

Inferencer.infer()

GlobalContext.libs[0].export(
    path=Path(output_dir), 
    prefix_ts="Exporting types",
    prefix_sy="Exporting symbols",
    symbols=False, 
    typeslots=True
)

logger.close()