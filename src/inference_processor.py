from src.preprocessing.preprocessor import Preprocessor
from src.preprocessing.module_meta import ModuleMeta
from src.inferencing import Inferencer
from pathlib import Path
import sys
import traceback

class InferenceProcessor:
	def __init__(self, preprocessor: Preprocessor):
		self.preprocessor = preprocessor
		self.symbols = preprocessor.symbols
		self.meta_map = self.preprocessor.meta_map
		self.sequence = []
		self.sequence_length = 0
		self.errors = 0
		self.ignore_errors = False
		self.progress: list[ModuleMeta] = []
		self.working_directory = self.preprocessor.working_directory

	def infer(self):
		self.sequence = self.preprocessor.generate_resolving_sequence()
		self.sequence_length = len(self.sequence)
		
		module_precedence = [meta.table for meta in self.sequence]
		for t in self.symbols:
			t.definitions = t.order_definitions(module_precedence)
			pass

		for module_meta in self.sequence: self.infer_meta(module_meta)

	def infer_meta(self, module_meta: ModuleMeta):
		inferencer = Inferencer(module_meta)

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