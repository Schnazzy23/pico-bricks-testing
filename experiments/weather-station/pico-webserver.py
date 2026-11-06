"""Compatibility launcher. The server implementation is now pico_server.py."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('pico_server.py')), run_name='__main__')
