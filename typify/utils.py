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
	
	@staticmethod
	def pretty_list_arrow(data: list, columns: int):
		result = ""
		max_width = max(len(str(item)) for item in data)
		for i in range(0, len(data), columns):
			row = data[i:i + columns]
			formatted_row = " ".join(f"-> {str(item):<{max_width}}" for item in row)
			result += formatted_row + "\n"
		
		return result