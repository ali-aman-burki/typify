from src.inferencing import Inferencer
from src.preprocessing.preprocessor import Preprocessor
from src.preprocessing.module_meta import ModuleMeta
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
		self.preprocessor.export(self.export_path)
		# self.inference_processor.export(self.export_path)