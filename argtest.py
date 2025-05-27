import ast
import json

from src.call_utils import CallerContext, ParameterSpec

def ast_node_to_str(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return ast.dump(node)


def convert_param_spec_to_jsonable(param_spec: dict[str, ParameterSpec]) -> dict:
    def convert(value):
        if isinstance(value, list):
            return [ast_node_to_str(v) for v in value]
        elif isinstance(value, dict):
            return {k: ast_node_to_str(v.node) for k, v in value.items()}
        else:
            return ast_node_to_str(value)
    return {k: convert(spec.node) for k, spec in param_spec.items()}


def pretty_print_param_spec(param_spec: dict[str, ParameterSpec]):
    jsonable = convert_param_spec_to_jsonable(param_spec)
    print(json.dumps(jsonable, indent=2))

src = '''
def f(x, z, /, y=2, w=4, *args, k1, k2=20, **extras): pass
f(10, 42, 99, 88, k1='A', extra1=1, extra2=2)
'''
tree = ast.parse(src)
func_def = tree.body[0]
call = tree.body[1].value

cc = CallerContext(None)

map = cc.build_parameter_map(func_def)
applied = cc.map_args_to_params(map, call)
pretty_print_param_spec(applied)

