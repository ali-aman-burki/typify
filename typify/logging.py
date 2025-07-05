class LogLevel:
    OFF = 0
    INFO = 1
    DEBUG = 2
    TRACE = 3

class AnsiColor:
    RESET = "\033[0m"
    INFO = "\033[38;5;250m"   # Grayish white
    DEBUG = "\033[38;5;108m"  # Soft green
    TRACE = "\033[38;5;179m"  # Muted yellow

class Logger:
    def __init__(self, level=LogLevel.OFF):
        self.level = level

    def set_level(self, level: LogLevel):
        self.level = level

    def info(self, msg: str, trail: int = 0, header: bool = True):
        if self.level >= LogLevel.INFO:
            print("\n" * trail, end="")
            print(f"{AnsiColor.INFO}{msg if not header else f'[INFO] {msg}'}{AnsiColor.RESET}")

    def debug(self, msg: str, trail: int = 0, header: bool = True):
        if self.level >= LogLevel.DEBUG:
            print("\n" * trail, end="")
            print(f"{AnsiColor.DEBUG}{msg if not header else f'[DEBUG] {msg}'}{AnsiColor.RESET}")

    def trace(self, msg: str, trail: int = 0, header: bool = True):
        if self.level >= LogLevel.TRACE:
            print("\n" * trail, end="")
            print(f"{AnsiColor.TRACE}{msg if not header else f'[TRACE] {msg}'}{AnsiColor.RESET}")

    def newline(self, count: int = 1):
        print("\n" * count, end="")

# Shared instance
logger = Logger()
