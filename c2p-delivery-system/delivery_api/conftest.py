import os
import sys

# Make the api modules importable when pytest runs from anywhere.
sys.path.insert(0, os.path.dirname(__file__))
