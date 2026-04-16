"""
Conftest for pipeline unit tests.

Adds execution/pipeline to sys.path so we can import pipeline_common
without installing it as a package.
"""

import sys
from pathlib import Path

# Resolve the execution/pipeline directory relative to this conftest
_pipeline_dir = Path(__file__).resolve().parents[2] / "execution" / "pipeline"
if str(_pipeline_dir) not in sys.path:
    sys.path.insert(0, str(_pipeline_dir))
