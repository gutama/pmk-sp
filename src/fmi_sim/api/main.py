"""Entry point for FMI-SimEngine API server."""
import uvicorn
from pathlib import Path
from .server import create_app

CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"

app = create_app(config_dir=CONFIG_DIR)


def run(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """Run the FMI-SimEngine API server."""
    uvicorn.run(
        "fmi_sim.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    run(reload=True)
