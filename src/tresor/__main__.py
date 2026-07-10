"""Entry point: enables `python -m tresor` and serves as the PyInstaller entry.

Uses an absolute import so that app.py's relative imports resolve cleanly.
"""

from tresor.app import main

if __name__ == "__main__":
    main()
