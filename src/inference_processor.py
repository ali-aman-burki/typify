from src.preprocessing.preprocessor import Preprocessor
from src.preprocessing.module_meta import ModuleMeta
from src.inferencing import Inferencer
from src.preloading.commons import preloaded_libs

import sys
import traceback

class InferenceProcessor:
	def __init__(self, preprocessor: Preprocessor):
		self.preprocessor = preprocessor
		self.symbols = preprocessor.symbols
		self.meta_map = self.preprocessor.meta_map
		self.sequence: list[ModuleMeta] = []
		self.sequence_length = 0
		self.errors = 0
		self.ignore_errors = False
		self.progress: list[ModuleMeta] = []
		self.working_directory = self.preprocessor.working_directory
		self.module_object_map = preprocessor.library_table.module_object_map

	def infer(self): 
		self.module_object_map.update(preloaded_libs.builtin_lib.module_object_map)
		self.module_object_map.update(preloaded_libs.pystd_lib.module_object_map)

		for site_lib in preloaded_libs.site_libs.values(): self.module_object_map.update(site_lib.module_object_map)
		for user_site_lib in preloaded_libs.user_site_libs.values(): self.module_object_map.update(user_site_lib.module_object_map)

		self.sequence = self.preprocessor.generate_resolving_sequence()
		self.sequence_length = len(self.sequence)
		
		module_precedence = [meta.table for meta in self.sequence]
		for t in self.symbols: t.order_definitions(module_precedence)
		for module_meta in self.sequence: self.infer_meta(module_meta, module_precedence)

	def infer_meta(self, module_meta: ModuleMeta, module_precedence):
		inferencer = Inferencer(module_meta, module_precedence)

		try:
			inferencer.visit(module_meta.tree)
			self.progress.append(module_meta)
			print(f"\rInferred [{len(self.progress)}/{self.sequence_length}].", end="", flush=True)
		except Exception as e:
			self.errors += 1
			if not self.ignore_errors:
				print()
				print(f"An error occurred when inferring: {module_meta}.")
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