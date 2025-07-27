from pathlib import Path
from collections import defaultdict

from typify.preprocessing.symbol_table import (
    Symbol,
	Library,
    Package,
    Module,
)
from typify.preprocessing.instance_utils import Instance
from typify.preprocessing.module_meta import ModuleMeta
from typify.preprocessing.precollector import PreCollector
from typify.progbar import ProgressBar

class LibraryMeta:
	def __init__(self, src: Path):
		self.src = Path(src).resolve()
		self.library_table = Library(self.src.name)
		self.sysmodules: dict[str, Instance] = {}
		self.meta_map: dict[Module, ModuleMeta] = {}
		self.dependency_graph: dict[ModuleMeta, set[ModuleMeta]] = {}
		self.fqn_map: dict[str, list[Symbol]] = {}

		self._build()

	def _build(self):
		working_is_package = (self.src / "__init__.py").is_file() or (self.src / "__init__.pyi").is_file()

		if working_is_package:
			root_package_table = Package(self.src.name)
			root_package_table.trust_annotations = False
			self.library_table.set_package(root_package_table, self.fqn_map)
			package_map = {self.src: root_package_table}
		else:
			self.library_table.trust_annotations = False
			package_map = {self.src: self.library_table}

		def has_valid_package_chain(path: Path, src: Path) -> bool:
			while path != src:
				if not ((path / "__init__.py").is_file() or (path / "__init__.pyi").is_file()):
					return False
				path = path.parent
			return True

		# First pass: register packages and detect py.typed
		for path in self.src.rglob("*"):
			if path.is_dir():
				if "__pycache__" in path.parts:
					continue

				has_init = (path / "__init__.py").is_file() or (path / "__init__.pyi").is_file()
				if has_init and has_valid_package_chain(path, self.src):
					parent_table = package_map.get(path.parent, self.library_table)
					package_table = Package(path.name)
					package_table.trust_annotations = parent_table.trust_annotations
					package_map[path] = package_table
					parent_table.set_package(package_table, self.fqn_map)

			elif path.name == "py.typed":
				parent = path.parent
				table = package_map.get(parent)
				if table:
					table.trust_annotations = True

		# Add __init__ modules to package tables
		for dir_path, package_table in package_map.items():
			for ext in [".pyi", ".py"]:
				init_path = dir_path / f"__init__{ext}"
				if init_path.is_file():
					meta = ModuleMeta(init_path, package_table.trust_annotations)
					package_table.set_module(meta.table, self.fqn_map)
					self.meta_map[meta.table] = meta
					break  # Prefer .pyi over .py

		# Second pass: collect .py and .pyi candidates (excluding __init__)
		module_candidates = defaultdict(dict)
		for path in self.src.rglob("*"):
			if path.suffix in {".py", ".pyi"} and not path.name.startswith("__init__.py"):
				parent = path.parent
				if parent in package_map:
					stem = path.stem
					module_candidates[(parent, stem)][path.suffix] = path

		# Final pass: resolve conflicts and create ModuleMetas
		for (parent, stem), variants in module_candidates.items():
			chosen_path = variants.get(".pyi") or variants.get(".py")
			if not chosen_path:
				continue

			table = package_map[parent]
			meta = ModuleMeta(chosen_path, True if chosen_path.suffix == ".pyi" else table.trust_annotations)
			table.set_module(meta.table, self.fqn_map)
			self.meta_map[meta.table] = meta
		
		meta_values = list(self.meta_map.values())
		progress = ProgressBar(
			len(meta_values), 
			prefix=f"Searching modules in {self.library_table.id}:", 
		)
		progress.display()

		for i, meta in enumerate(meta_values, 1):
			PreCollector(meta).visit(meta.tree)
			progress.update(i)

	def export(self, path: Path, symbols=True, typeslots=True) -> None:
		print()
		if symbols:
			progress = ProgressBar(
				len(self.meta_map), 
				prefix=f"Exporting symbols for {self.library_table.id}:"
			)
			progress.display()
			for i, meta in enumerate(self.meta_map.values(), 1):
				meta.export_symbols(self.src, path)
				progress.update(i)

		if typeslots:
			progress = ProgressBar(
				len(self.meta_map), 
				prefix=f"Exporting types for {self.library_table.id}:"
			)
			progress.display()
			for i, meta in enumerate(self.meta_map.values(), 1):
				meta.export_typeslots(self.src, path)
				progress.update(i)
