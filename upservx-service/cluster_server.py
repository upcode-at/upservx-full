"""Dedicated HTTPS listener for authenticated inter-node traffic."""

import uvicorn

from lib.cluster_security import CLUSTER_TLS_PORT, ensure_node_tls


def main() -> None:
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
