# Automated Variable Type Inference Tool for Python Codebases

## Developers:
- Ali Aman
- Hassan Aman
- Andre Racicot

## Overview
This project is attempting to develop a tool that automatically infers variable types in Python codebases. Python's dynamic typing makes static type analysis challenging, and this tool aims to provide inferred types to improve code readability and debugging.

## Features
- Resolving method types that are present in superclasses. Follows Method Resolution Order (MRO).
- Infers primitive types like `int`, `str`, `float`, `bool` as well as class types.
- Supports type propagation for functions and class methods and instantiation (eg: `x = a.b.c()` or `x = a().b().c()` etc).
- Works with external files that are referenced using `import x` or `import x as y`. 
- Resolving relative imports and imports that are in the form `from x import y` or `from x import y as z`.
- Inferring types for variables that are redefined in current scope but originally defined in external scope (eg: `a.b.c = x`).
- Performing second pass to make sure that dependencies unresolved in first pass are resolved.
- Inferring types for class instance variables (eg: `self.x = self.y` or `self.x = y`). 

## Current Limitations
- Only works for symbols local to the project to analyze. Cannot yet determine types for some builtin classes and functions.
- Complex types like `List`, `Dict`, `Set`.
- Higher order functions (eg: `x = some_function_name`).
- Resolving Dynamic Imports
- Resolving variables that rely on operator overloading
- Integration into IDEs.
- External python codebases.

## How to Run
- Ensure Python 3.7+ is installed.
- Navigate to the root directory and run the following command:
	```python main.py```
