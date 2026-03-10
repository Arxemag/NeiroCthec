import logging
import os

import uvicorn
from api.app import app

try:
    import debugpy  # type: ignore
except ImportError:  # pragma: no cover
    debugpy = None

# Порт отладки (слушаем в контейнере или подключаемся к IDE на хосте)
_DEBUGPY_PORT = 5678


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(name)s: %(message)s",
    )

    # Debugpy может блокировать запуск сервера, если ждать клиента.
    # Включаем явно через DEBUGPY_ENABLE=1.
    if debugpy is not None and os.environ.get("DEBUGPY_ENABLE") == "1":
        # Режим для PyCharm: контейнер подключается к IDE на хосте (IDE слушает порт).
        # В docker-compose для core задайте: DEBUGPY_CONNECT=1
        # В PyCharm: Run → Edit Configurations → + → Python Remote Debug, Port 5678 → Debug.
        if os.environ.get("DEBUGPY_CONNECT") == "1":
            _host = os.environ.get("DEBUGPY_HOST", "host.docker.internal")
            logging.info("debugpy: connecting to %s:%s (start Python Remote Debug in PyCharm first)", _host, _DEBUGPY_PORT)
            debugpy.connect((_host, _DEBUGPY_PORT))
        else:
            # Режим Attach (Cursor/VS Code): контейнер слушает, IDE подключается.
            debugpy.listen(("0.0.0.0", _DEBUGPY_PORT))
            if os.environ.get("DEBUGPY_WAIT") == "1":
                debugpy.wait_for_client()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )
