from src.preprocessing.module_meta import ModuleMeta

import ast

class SlotsCollector(ast.NodeVisitor):
	def __init__(self, module_meta: ModuleMeta):
		self.module_meta = module_meta