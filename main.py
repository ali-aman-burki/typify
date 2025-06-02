import argparse
from src.utils import Utils
from src.preprocessing.preprocessor import Preprocessor
import os

parser = argparse.ArgumentParser(description="Build and export type bindings for a Python project.")
parser.add_argument("project_path", help="Path to the Python project directory.")
parser.add_argument("-o", "--export-path", 
                    help="Path to the export directory (default: './export').",
                    default="./.typify")
args = parser.parse_args()

if not Utils.is_valid_directory(args.project_path):
    print("Invalid project path given.")
    exit(1)

if not Utils.is_valid_directory(args.export_path):
    os.makedirs(args.export_path, exist_ok=True)

project_path = args.project_path
export_path = args.export_path

print(Utils.title)

pp = Preprocessor(project_path)

for m, dependencies in pp.dependency_graph.items():
	print(f"{m} -> {[str(d) for d in dependencies]}")