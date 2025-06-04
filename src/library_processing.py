from src.preprocessing.preprocessor import Preprocessor
from src.inference_processor import InferenceProcessor
from pathlib import Path

class LibraryProcessor:

	def __init__(self, project_path: Path, export_path: Path):
		self.preprocessor = Preprocessor(project_path)
		self.inference_processor = InferenceProcessor(self.preprocessor)
		self.export_path = Path(export_path).resolve()
		self.working_directory = self.preprocessor.working_directory
	
	def build(self):
		self.preprocessor.build()

	def infer(self):
		self.inference_processor.infer()

	def export(self):
		meta_map = self.preprocessor.meta_map
		for meta in meta_map.values():
			meta.export_symbols(self.working_directory, self.export_path)
			meta.export_typeslots(self.working_directory, self.export_path)