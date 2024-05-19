import sys
import os
# Insert the absolute path of the directory containing this file at the start of sys.path
# This ensures that modules in this directory can be imported at the top level in tests
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

