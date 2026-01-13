import module_a
from utils import farewell

class BClass:
    def __init__(self, value: int) -> None:
        self.value: int = value

    def compute(self) -> int:
        print(f"BClass: computing with {self.value}")
        result: int = module_a.func_a(self.value)
        print(f"BClass: result from func_a = {result}")
        farewell("BClass user")
        return result + 10

def func_b(y: int) -> int:
    print(f"func_b: received {y}")
    return y + 5