import sys
from typing import Optional, Literal

class ProgressBar:
	def __init__(
		self,
		total: int,
		length: int = 24,
		fill: str = '━',
		empty: str = '─',
		prefix: str = '',
		suffix: str = '',
		left: str = '',
		right: str = '',
		decimals: int = 1,
		progress_format: Literal["percent", "counter", "none"] = "counter",
		prefix_width: int = 34,  # New parameter
	) -> None:
		self.total: int = total
		self.length: int = length
		self.fill: str = fill
		self.empty: str = empty
		self.prefix: str = prefix
		self.suffix: str = suffix
		self.left: str = left
		self.right: str = right
		self.decimals: int = decimals
		self.progress_format: Literal["percent", "counter", "none"] = progress_format
		self.prefix_width: Optional[int] = max(prefix_width or 0, len(prefix))  # Clamp to prefix length
		self.iteration: int = 0

	def display(self) -> None:
		self.update(0)

	def update(self, iteration: Optional[int] = None) -> None:
		if iteration is not None:
			self.iteration = iteration
		else:
			self.iteration += 1

		GREEN = "\033[32m"
		GRAY = "\033[90m"
		RESET = "\033[0m"

		filled_len: int = int(self.length * self.iteration // self.total) if self.total > 0 else 0
		bar = f"{GREEN}{self.fill * filled_len}{RESET}{GRAY}{self.empty * (self.length - filled_len)}{RESET}"

		if self.progress_format == "percent":
			progress_info = f"{100 * (self.iteration / float(self.total)):.{self.decimals}f}%"
		elif self.progress_format == "counter":
			progress_info = f"[{self.iteration}/{self.total}]"
		else:
			progress_info = ""

		components: list[str] = []

		if self.prefix:
			prefix_str = self.prefix.ljust(self.prefix_width) if self.prefix_width else self.prefix
			components.append(prefix_str)

		components.append(f'{self.left}{bar}{self.right}')

		if progress_info:
			components.append(progress_info)

		if self.suffix:
			components.append(self.suffix)

		print('\r' + ' '.join(components), end='', file=sys.stdout)

		if self.iteration >= self.total:
			print(file=sys.stdout)