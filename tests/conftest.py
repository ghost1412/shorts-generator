import os
import sys

# Make `engine` importable when pytest runs from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
