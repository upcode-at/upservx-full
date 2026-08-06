"""Dedicated HTTPS listener for authenticated inter-node traffic."""

import os

import uvicorn

from lib.cluster_security import CLUSTER_TLS_PORT, ensure_node_tls


def main() -> None:
    # The TLS transport process must not start a second HA loop or other
    # singleton background managers when it imports the shared FastAPI app.
    os.environ["UPCODE_HARBOR_PASSIVE_PROCESS"] = "1"
    material = ensure_node_tls()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=CLUSTER_TLS_PORT,
        workers=1,
        ssl_certfile=material.cert_file,
        ssl_keyfile=material.key_file,
    )


if __name__ == "__main__":
    main()
