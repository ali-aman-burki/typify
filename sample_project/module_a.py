from utils import greet
import module_b

class AClass:
    def __init__(self, name: str) -> None:
        self.name: str = name

    def show(self) -> None:
        print(f"AClass: My name is {self.name}")
        greet(self.name)

def func_a(x: int) -> int:
    print(f"func_a: received {x}")
    y: int = module_b.func_b(x + 1)
    print(f"func_a: func_b returned {y}")
    return y * 2
