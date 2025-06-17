from src.symbol_table import Table, VariableTable, ClassTable
from src.typeutils import TypeUtils

orphan_class = ClassTable("$")

class ModuleUtils:
	
	@staticmethod
	def add(add_to: Table, class_table: ClassTable, type_class: Table | None = None):
		ct = add_to.add_class(class_table)
		cv = VariableTable(ct.key)
		
		if type_class: ins = TypeUtils.create_instance(type_class, [])
		else: ins = TypeUtils.create_instance(orphan_class, [])
		
		ins.origin = ct
		cv.points_to.add(ins)
		add_to.add_variable(cv)
		return ct