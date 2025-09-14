import sys
import inspect

print(f"Python executable: {sys.executable}")

try:
    # 我们来检查最可能的两个模块
    import gnpy.core.network
    import gnpy.core.science_utils

    print("=" * 50)
    print(f"Inspecting module: gnpy.core.network")
    print(f"File location: {gnpy.core.network.__file__}")
    print("-" * 50)

    # 列出 gnpy.core.network 中所有可用的成员
    members = [name for name, obj in inspect.getmembers(gnpy.core.network) if not name.startswith('_')]
    print("Available members in gnpy.core.network:")
    print(sorted(members))
    print("")

    print("=" * 50)
    print(f"Inspecting module: gnpy.core.science_utils")
    print(f"File location: {gnpy.core.science_utils.__file__}")
    print("-" * 50)

    # 列出 gnpy.core.science_utils 中所有可用的成员
    members = [name for name, obj in inspect.getmembers(gnpy.core.science_utils) if not name.startswith('_')]
    print("Available members in gnpy.core.science_utils:")
    print(sorted(members))
    print("")

except ImportError as e:
    print(f"Error: Could not import a GNPy module. {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")

