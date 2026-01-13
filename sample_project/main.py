from module_a import AClass, func_a
from module_b import BClass
from utils import greet, farewell

def main() -> None:
    greet("User")
    a: AClass = AClass("Alice")
    a.show()
    result_a: int = func_a(10)
    print(f"Result from func_a: {result_a}")
    b: BClass = BClass(20)
    result_b: int = b.compute()
    print(f"Result from BClass.compute(): {result_b}")
    farewell("User")

if __name__ == "__main__":
    main()

