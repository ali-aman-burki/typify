import json

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
from typify.progbar import (
	ProgressBar,
	IndeterminateProgressBar
)

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
		def last_n_parts(path: Path, n: int) -> str:
			parts = path.parts
			n = max(1, min(n, len(parts)))

			if len(parts) <= n:
				return str(path)
			else:
				truncated_path = Path("...") / Path(*parts[-n:])
				return str(truncated_path)
		
		working_is_package = (self.src / "__init__.py").is_file() or (self.src / "__init__.pyi").is_file()
		progress_bar = IndeterminateProgressBar(
			prefix=f"Searching modules in {last_n_parts(self.src, 2)}", 
			suffix="Discovered: 0 modules", 
		)
		progress_bar.start()

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
					progress_bar.set_suffix(f"Discovered: {len(self.meta_map)} modules")
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
			progress_bar.set_suffix(f"Discovered: {len(self.meta_map)} modules")
		
		progress_bar.done()

	def export_symbols(self, output: Path):
		progress = ProgressBar(
			len(self.meta_map) + 1, 
			prefix="Exporting Symbols",
			progress_format="percent"
		)
		progress.display()
		data = {}
		for i, meta in enumerate(self.meta_map.values(), 1):
			data[str(meta.src.resolve().as_posix())] = meta.table.to_dict()
			progress.update(i)
		
		with output.open("w", encoding="utf-8") as f:
			json.dump(data, f, indent='\t', ensure_ascii=False)
		
		progress.update(len(self.meta_map) + 1)

	def export_types(self, output: Path):
		progress = ProgressBar(
			len(self.meta_map) + 1, 
			prefix="Exporting Types",
			progress_format="percent"
		)
		progress.display()
		data = {}
		for i, meta in enumerate(self.meta_map.values(), 1):
			data[str(meta.src.resolve().as_posix())] = meta.typeslots()
			progress.update(i)
		
		with output.open("w", encoding="utf-8") as f:
			json.dump(data, f, indent='\t', ensure_ascii=False)
		
		progress.update(len(self.meta_map) + 1)