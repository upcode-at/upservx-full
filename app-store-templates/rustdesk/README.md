# RustDesk

RustDesk is an open-source remote desktop software that lets you host your own relay and signaling server. It is a full self-hosted alternative to TeamViewer or AnyDesk without any cloud dependency.

## Components

| Container | Role |
|---|---|
| `rustdesk-hbbs` | ID / Rendezvous server – coordinates connections between clients |
| `rustdesk-hbbr` | Relay server – relays encrypted traffic when direct connections fail |

## Ports

| Port | Protocol | Purpose |
|---|---|---|
| 21115 | TCP | NAT type test |
| 21116 | TCP | ID server & hole punching |
| 21116 | UDP | ID server & hole punching |
| 21117 | TCP | Relay server |
| 21118 | TCP | WebSocket (web client) |
| 21119 | TCP | WebSocket (web client, encrypted) |

> **Note:** This setup uses `network_mode: host` for best NAT traversal performance. Make sure the ports above are open in your firewall.

## Setup

1. Install the app via the UpServX App Store.
2. After the containers start, retrieve the public key from the server:
   ```bash
   cat /opt/upservx/data/rustdesk/id_ed25519.pub
   ```
3. In the RustDesk client on your devices, open **Settings → Network** and enter:
   - **ID Server**: `<your-server-ip>`
   - **Relay Server**: `<your-server-ip>`
   - **Key**: the public key from step 2
4. Connections are now routed through your self-hosted server.

## Security

- `ENCRYPTED_ONLY=1` forces all connections to use the server's keypair – unencrypted connections are rejected.
- The key pair (`id_ed25519` / `id_ed25519.pub`) is auto-generated on first start and stored in `/opt/upservx/data/rustdesk`.

## More Information

- [RustDesk Website](https://rustdesk.com)
- [GitHub](https://github.com/rustdesk/rustdesk-server)
- [Documentation](https://rustdesk.com/docs/en/self-host/)
