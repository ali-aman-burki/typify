import os
from src.library_builder import LibraryBuilder
from src.symbol_table import *

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

def is_valid_directory(path):
	if os.path.exists(path) and os.path.isdir(path):
		return path

def scan_and_export(project_path, export_path):
    library = LibraryBuilder(project_path, export_path)
    library.build()

    print("\rExporting...", end="", flush=True)
    print(f"\rAnalysis complete and data exported successfully. {library.errors} file errors found. Press (r) to rescan or (x) to exit:", end=" ")

	