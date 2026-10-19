"""Optional Lua runtime worker when a standalone Lua interpreter is unavailable."""
import sys
from lupa import LuaRuntime

if __name__ == '__main__':
    LuaRuntime(unpack_returned_tuples=True).execute(sys.stdin.read())
