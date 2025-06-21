import argparse
import os
import json

from typing import Union
from pathlib import Path

from typify.utils import Utils
from typify.preprocessing.preloader import Preloader
from typify.inferencing.inferencer import Inferencer

config_path = "typifyconfig.json"

parser = argparse.ArgumentParser(description="Build and export type bindings for a Python project.")
parser.add_argument("project_dir", help="Path to the Python project directory.")
parser.add_argument("-o", "--output-dir", help="Path to the export directory (defaults to project path).")

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

config["project_dir"] = project_dir

print(Utils.title)

bundle = Preloader.load(config)

print("")
for lib, meta in bundle.libs.items():
     print(f"{lib} -> {str(meta.src)}")

print("\nOriginal Graph: ")
for meta, deps in bundle.dependency_graph.items():
    joined = ", ".join(
        f"<{dep}>" if isinstance(dep, str) else repr(dep)
        for dep in deps
    )
    print(f"{repr(meta)} -> [{joined}]")
print("\nCleaned Graph: ")
for meta, deps in bundle.cleaned_graph.items():
    joined = ", ".join(
        f"<{dep}>" if isinstance(dep, str) else repr(dep)
        for dep in deps
    )
    print(f"{repr(meta)} -> [{joined}]")

print("\nResolving Sequence: ")
joined = " -> ".join(repr(meta) for meta in bundle.resolving_sequence)
print(joined + "\n")

Inferencer.infer(bundle)

next(iter(bundle.libs.values())).export_to(Path(output_dir))

