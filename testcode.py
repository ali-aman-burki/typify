import ast
from typify.inferencing.typeutils import TypeUtils

def test_has_complete_return():
    # Case 1: Flat unconditional return
    src = "def f():\n    return 42"
    body = ast.parse(src).body[0].body
    assert TypeUtils.has_complete_return(body) == True, "Case 1 failed"

    # Case 2: If-else both return
    src = """
def f():
    if cond:
        return 1
    else:
        return 2
"""
    body = ast.parse(src).body[0].body
    assert TypeUtils.has_complete_return(body) == True, "Case 2 failed"

    # Case 3: If without else
    src = """
def f():
    if cond:
        return 1
"""
    body = ast.parse(src).body[0].body
    assert TypeUtils.has_complete_return(body) == False, "Case 3 failed"

    # Case 4: Nested if-else all branches return
    src = """
def f():
    if x:
        if y:
            return 1
        else:
            return 2
    else:
        return 3
"""
    body = ast.parse(src).body[0].body
    assert TypeUtils.has_complete_return(body) == True, "Case 4 failed"

    # Case 5: Match with all arms returning
    src = """
def f():
    match something:
        case 1:
            return "one"
        case 2:
            return "two"
        case _:
            return "fallback"
"""
    body = ast.parse(src).body[0].body
    assert TypeUtils.has_complete_return(body) == True, "Case 5 failed"

    # Case 6: Match with a missing return
    src = """
def f():
    match something:
        case 1:
            return "one"
        case _:
            x = 123
"""
    body = ast.parse(src).body[0].body
    assert TypeUtils.has_complete_return(body) == False, "Case 6 failed"

    # Case 7: Try-finally with all paths returning
    src = """
def f():
    try:
        return 1
    except:
        return 2
    else:
        return 3
    finally:
        return 4
"""
    body = ast.parse(src).body[0].body
    assert TypeUtils.has_complete_return(body) == True, "Case 7 failed"

    # Case 8: While loop with return (not guaranteed to run)
    src = """
def f():
    while x:
        return True
"""
    body = ast.parse(src).body[0].body
    assert TypeUtils.has_complete_return(body) == False, "Case 8 failed"

    # Case 9: Deep nesting with missing else
    src = """
def f():
    if a:
        if b:
            return 1
        # missing else here
    else:
        return 2
"""
    body = ast.parse(src).body[0].body
    assert TypeUtils.has_complete_return(body) == False, "Case 9 failed"

    # Case 10: Top-level if else, but nested one missing
    src = """
def f():
    if a:
        if b:
            return 1
        else:
            x = 2
    else:
        return 3
"""
    body = ast.parse(src).body[0].body
    assert TypeUtils.has_complete_return(body) == False, "Case 10 failed"

    # Case 11: All branches and sub-branches return
    src = """
def f():
    if x:
        if y:
            return 1
        else:
            return 2
    elif z:
        return 3
    else:
        if w:
            return 4
        else:
            return 5
"""
    body = ast.parse(src).body[0].body
    assert TypeUtils.has_complete_return(body) == True, "Case 11 failed"

    print("✅ All tests passed for has_complete_return")

# Run the test suite
test_has_complete_return()
