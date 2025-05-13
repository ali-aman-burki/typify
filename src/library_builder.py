from src.symbol_table import *
from src.inferencing import Analyzer
import ast
import sys
from pathlib import Path
import traceback
import os

class LibraryBuilder:

    def __init__(self, working_directory, export_path):
        self.export_path = Path(export_path).resolve()
        self.working_directory = Path(working_directory).resolve()
        self.total_modules = len(list(self.working_directory.rglob("*.py")))
        self.processed_modules = 0
        self.errors = 0
        self.ignore_errors = False

    def build(self):
        self.library_table = LibraryTable(self.working_directory.name)
        package_map = {self.working_directory: self.library_table}

        for path in self.working_directory.rglob("*"):
            if path.is_dir():
                if "__pycache__" in path.parts:
                    continue

                if path != self.working_directory:
                    has_python_files = any((p.suffix == ".py") for p in path.rglob("*"))
                    if has_python_files:
                        package_table = PackageTable(path.name)
                        package_map[path] = package_table
                        parent_table = package_map.get(path.parent, self.library_table)
                        parent_table.add_package(package_table)

            elif path.suffix == ".py":
                package_table = package_map.get(path.parent, self.library_table)
                self.build_module(path, package_table)
        print()

    def build_module(self, file_path, package_table):
        module_name = file_path.stem
        module_table = ModuleTable(module_name)
        package_table.add_module(module_table)

        analyzer = Analyzer(self.library_table, module_table)

        try:
            code = file_path.read_text()
            tree = ast.parse(code)
            analyzer.visit(tree)
            
            self.export_module_json(file_path, module_table)
            
            self.processed_modules += 1
            print(f"\rProcessed [{self.processed_modules}/{self.total_modules}] modules.", end="", flush=True)
        except Exception as e:
            self.errors += 1
            if not self.ignore_errors:
                print()
                print(f"An error occurred when analyzing: {file_path}.")
                print(f"Error: {str(e)}")

                print("Options:")
                print("  (x) Exit")
                print("  (i) Ignore error and continue")
                print("  (s) Show error and continue")
                print("  (e) Show error and exit")
                print("  (a) Always ignore errors")

                choice = input("Enter your choice: ").strip().lower()

                if choice == "s":
                    traceback.print_exc()
                elif choice == "e":
                    traceback.print_exc()
                    sys.exit(1)
                elif choice == "x":
                    sys.exit(0)
                elif choice == "a":
                    self.ignore_errors = True
                else:
                    pass

    def export_module_json(self, file_path, module_table):
        rel_path = file_path.relative_to(self.working_directory)
        output_path = self.export_path / rel_path.parent
        output_path.parent.mkdir(parents=True, exist_ok=True)
        module_table.export_to_json(output_path, module_table.key)