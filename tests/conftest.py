import os
import sys

# Ensure the cloud package and shared ground-station modules are on sys.path
# before any test module imports cloud code.
_CLOUD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE_ROOT = os.path.dirname(_CLOUD_DIR)
_MASTER_BASE_DIR = os.path.join(_WORKSPACE_ROOT, "logicgate_master_base")
for _path in (_MASTER_BASE_DIR, _WORKSPACE_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)
