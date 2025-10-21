"""
ModuleGUI - A graphical user interface module for dependency management.
"""

__title__ = "ModuleGUI"
__version__ = "0.0.1"

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

del logging
