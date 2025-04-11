import sys

def is_debug_mode():
    return "--debug" in sys.argv or "-d" in sys.argv