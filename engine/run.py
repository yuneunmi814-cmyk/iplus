"""PyInstaller entry point. Imports the app package absolutely so relative imports
survive. (Using app/main.py directly as the entry runs it as __main__ and breaks
relative imports.)"""
from app.main import main

if __name__ == "__main__":
    main()
