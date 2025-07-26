import ast

class Desugar:
    @staticmethod
    def subscript(node: ast.Subscript, use_class_getitem: bool = False) -> ast.Call:
        if not isinstance(node, ast.Subscript):
            raise TypeError("Expected ast.Subscript node")
        method = "__class_getitem__" if use_class_getitem else "__getitem__"
        return ast.Call(
            func=ast.Attribute(
                value=node.value,
                attr=method,
                ctx=ast.Load()
            ),
            args=[node.slice],
            keywords=[]
        )