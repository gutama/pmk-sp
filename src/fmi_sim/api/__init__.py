"""FMI SimEngine REST API and WebSocket server."""
from .server import create_app

__all__ = ["create_app"]
