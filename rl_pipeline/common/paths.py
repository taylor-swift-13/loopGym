"""Path bootstrap so reward/inference components can import reused modules from src/."""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(REPO_ROOT, "src")


def ensure_src_on_path() -> str:
    """Add <repo>/src to sys.path (idempotent). Returns the src dir."""
    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)
    return SRC_DIR
