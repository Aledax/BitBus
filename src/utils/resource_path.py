import sys
import os

def resource_path(relative_path):
    """Get absolute path for PyInstaller-packaged files."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(relative_path)