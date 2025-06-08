from src.symbol_table import ModuleTable, ClassTable

builtins = ModuleTable("builtins")
object_table = builtins.add_class(ClassTable("object"))
type_table = builtins.add_class(ClassTable("type"))
function_table = builtins.add_class(ClassTable("function"))
module_table = builtins.add_class(ClassTable("module"))

list_table = builtins.add_class(ClassTable("list"))
list_table.bases.append(object_table)

set_table = builtins.add_class(ClassTable("set"))
set_table.bases.append(object_table)

dict_table = builtins.add_class(ClassTable("dict"))
dict_table.bases.append(object_table)

tuple_table = builtins.add_class(ClassTable("tuple"))
tuple_table.bases.append(object_table)

str_table = builtins.add_class(ClassTable("str"))
str_table.bases.append(object_table)

int_table = builtins.add_class(ClassTable("int"))
int_table.bases.append(object_table)

float_table = builtins.add_class(ClassTable("float"))
float_table.bases.append(object_table)

bool_table = builtins.add_class(ClassTable("bool"))
bool_table.bases.append(object_table)

none_table = builtins.add_class(ClassTable("NoneType"))
none_table.bases.append(object_table)

bytes_table = builtins.add_class(ClassTable("bytes"))
bytes_table.bases.append(object_table)

complex_table = builtins.add_class(ClassTable("complex"))
complex_table.bases.append(object_table)