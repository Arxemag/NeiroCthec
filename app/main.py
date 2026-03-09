import logging
import uvicorn
from api.app import app

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(name)s: %(message)s",
    )
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )
