# LogicGate Cloud
# Multi-tenant SaaS backend and customer portal for the LogicGate fleet platform.

import os
import sys

# Add the cloud directory, workspace root, and logicgate_master_base to sys.path
# so cloud modules can import each other and shared infrastructure (cache, logging,
# exceptions, settings) from the ground station repository. This is a temporary
# coupling until the shared infrastructure is extracted into a common package.
_CLOUD_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(_CLOUD_DIR)
_MASTER_BASE_DIR = os.path.join(_WORKSPACE_ROOT, "logicgate_master_base")
for _path in (_MASTER_BASE_DIR, _WORKSPACE_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)
