import os
from src.library_processing import LibraryProcessor
from src.preprocessing.preprocessor import Preprocessor

class Utils:
	
	title = r"""
  _______             _  ___        
 |__   __|           (_)|  _|       
    | | _   _  _ __   _ | |_  _   _ 
    | || | | || '_ \ | ||  _|| | | |
    | || |_| || |_) || || |  | |_| |
    |_| \__, || .__/ |_||_|   \__, |
         __/ || |              __/ |
        |___/ |_|             |___/ 
"""

	@staticmethod
	def is_valid_directory(path):
		if os.path.exists(path) and os.path.isdir(path):
			return path

	@staticmethod
	def scan_and_export(project_path, export_path):
		library = LibraryProcessor(project_path, export_path)
		library.build()
		# library.infer()
		library.export()
		print(f"\rAnalysis complete and data exported successfully. Press (r) to rescan or (x) to exit:", end=" ")