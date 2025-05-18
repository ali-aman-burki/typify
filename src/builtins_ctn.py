from src.symbol_table import ModuleTable, ClassTable

builtins = ModuleTable("builtins")
object_table = builtins.add_class(ClassTable("object"))

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