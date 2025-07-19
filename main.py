import argparse
import os
import json

from typing import Union
from pathlib import Path

from typify.utils import Utils
from typify.preprocessing.preloader import Preloader
from typify.inferencing.inferencer import Inferencer
from typify.logging import logger, LogLevel

config_path = "typifyconfig.json"

parser = argparse.ArgumentParser(description="Build and export type bindings for a Python project.")
parser.add_argument("project_dir", help="Path to the Python project directory.")
parser.add_argument("-o", "--output-dir", help="Path to the export directory (defaults to project path).")
parser.add_argument("-l", "--log", choices=["off", "info", "debug", "trace"], default="info", help="Set the logging level.")

args = parser.parse_args()

log_levels = {
    "off": LogLevel.OFF,
    "info": LogLevel.INFO,
    "debug": LogLevel.DEBUG,
    "trace": LogLevel.TRACE,
}
logger.set_level(log_levels[args.log])

project_dir = args.project_dir
output_dir = args.output_dir or (project_dir + "/.typify")

if not Utils.is_valid_directory(project_dir):
    logger.info("❌ Invalid project path given.")
    exit(1)

if not Utils.is_valid_directory(output_dir):
    os.makedirs(output_dir, exist_ok=True)

with open(config_path, "r") as f:
    config: dict[str, Union[str, dict[str, str]]] = json.load(f)

logger.info(Utils.title, header=False)

bundle = Preloader.load(config, Path(project_dir))

logger.debug("📦 Libraries loaded:", 1)
for libmeta in bundle.libs:
    logger.debug(f"{str(libmeta.src)}")

logger.debug("🧩 Original Graph:", 1)
for meta, deps in bundle.dependency_graph.items():
    joined = ", ".join(f"<{dep}>" if isinstance(dep, str) else repr(dep) for dep in deps)
    logger.debug(f"  {repr(meta)} -> [{joined}]")

logger.debug("🧹 Cleaned Graph:", 1)
for meta, deps in bundle.cleaned_graph.items():
    joined = ", ".join(f"<{dep}>" if isinstance(dep, str) else repr(dep) for dep in deps)
    logger.debug(f"  {repr(meta)} -> [{joined}]")

Inferencer.infer(bundle)

logger.info("💾 Exporting...", 1)

bundle.libs[0].export(
    path=Path(output_dir), 
    symbols=True, 
    typeslots=True
)

# bundle.libs["builtinlib"].export(
#     path=Path(output_dir) / "builtinlib", 
#     symbols=True, 
#     typeslots=False
# )
# bundle.libs["stdlib"].export(
#     path=Path(output_dir) / "stdlib",
#     symbols=True,
#     typeslots=False)

logger.info("✅ Done.")

logger.close()