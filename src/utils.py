import os

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