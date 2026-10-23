"""Find installed CPU test packages without requiring the optional GPU runtime."""
import importlib
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
_DLL_HANDLES=[]


def cpu_package(name):
    """Return an installed module, or None when that optional package is absent.

    Broken installed dependencies still raise; they must not become skipped tests.
    The documents runtime is part of Windows installation and supplies Pillow and
    NumPy even when the host interpreter has no third-party site-packages.
    """
    try:return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name!=name:raise
    folder=ROOT/'runtime/tools/documents'
    if not (folder/name).is_dir():return None
    if os.name=='nt' and hasattr(os,'add_dll_directory'):
        _DLL_HANDLES.append(os.add_dll_directory(str(folder)))
    sys.path.insert(0,str(folder))
    try:return importlib.import_module(name)
    finally:sys.path.remove(str(folder))
