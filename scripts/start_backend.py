"""Helper to start the NEXUS backend with correct sys.path"""
import sys
import os

# Ensure NEXUS root is in sys.path
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root not in sys.path:
    sys.path.insert(0, root)

os.environ.setdefault("PYTHONPATH", root)

# Now import and run uvicorn
import uvicorn
uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True, reload_dirs=[os.path.join(root, "backend")])
