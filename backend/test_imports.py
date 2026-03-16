import sys
try:
    from langchain.tools import StructuredTool
    print("SUCCESS: langchain.tools")
except ImportError as e:
    print(f"FAILED langchain.tools: {e}")

try:
    from langchain_core.tools import StructuredTool
    print("SUCCESS: langchain_core.tools")
except ImportError as e:
     print(f"FAILED langchain_core.tools: {e}")

try:
    from langchain.agents import tool
    print("SUCCESS: langchain.agents.tool")
except ImportError as e:
    print(f"FAILED langchain.agents.tool: {e}")
