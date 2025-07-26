import sys

class LogLevel:
	OFF = 0
	INFO = 1
	DEBUG = 2
	TRACE = 3

class AnsiColor:
	RESET = "\033[0m"
	INFO = "\033[38;5;250m"
	DEBUG = "\033[38;5;108m"
	TRACE = "\033[38;5;179m"
	ERROR = "\033[38;5;160m"
	WARN = "\033[38;5;179m"

class Logger:
	def __init__(self, level=LogLevel.OFF):
		self.level = level
		self.outputs = []
	
	def set_level(self, level: int):
		self.level = level

	def add_output(self, stream):
		self.outputs.append(stream)

	def to_terminal(self, msg: str):
		print(msg)

	def _log(self, level_name: str, msg: str, color: str, min_level: int, trail: int, header: bool):
		if self.level >= min_level:
			prefix = f"[{level_name}] " if header else ""
			color_msg = f"{color}{prefix}{msg}{AnsiColor.RESET}"
			plain_msg = f"{prefix}{msg}"

			for out in self.outputs:
				if out == sys.stdout:
					print("\n" * trail, end="", file=out)
					print(color_msg, file=out)
				else:
					out.write("\n" * trail + plain_msg + "\n")
					out.flush()

	def info(self, msg: str, trail: int = 0, header: bool = True):
		self._log("INFO", msg, AnsiColor.INFO, LogLevel.INFO, trail, header)

	def debug(self, msg: str, trail: int = 0, header: bool = True):
		self._log("DEBUG", msg, AnsiColor.DEBUG, LogLevel.DEBUG, trail, header)

	def trace(self, msg: str, trail: int = 0, header: bool = True):
		self._log("TRACE", msg, AnsiColor.TRACE, LogLevel.TRACE, trail, header)

	def error(self, msg: str, trail: int = 0, header: bool = True):
		prefix = "[ERROR] " if header else ""
		color_msg = f"{AnsiColor.ERROR}{prefix}{msg}{AnsiColor.RESET}"
		plain_msg = f"{prefix}{msg}"

		for out in self.outputs:
			if out == sys.stdout or out == sys.stderr:
				print("\n" * trail, end="", file=out)
				print(color_msg, file=out)
			else:
				out.write("\n" * trail + plain_msg + "\n")
				out.flush()
	
	def warn(self, msg: str, trail: int = 0, header: bool = True):
		prefix = "[WARN] " if header else ""
		color_msg = f"{AnsiColor.WARN}{prefix}{msg}{AnsiColor.RESET}"
		plain_msg = f"{prefix}{msg}"

		for out in self.outputs:
			if out == sys.stdout or out == sys.stderr:
				print("\n" * trail, end="", file=out)
				print(color_msg, file=out)
			else:
				out.write("\n" * trail + plain_msg + "\n")
				out.flush()

	def close(self):
		for out in self.outputs:
			if out not in (sys.stdout, sys.stderr):
				out.close()

logger = Logger(level=LogLevel.DEBUG)
