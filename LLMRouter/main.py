"""Project entry point.
Run the service with:  uv run python main.py
This is a thin wrapper around app.main.run() so users don't need to
remember the uvicorn flags or module path.
"""

from app.main import run

if __name__ == "__main__":
    run()
