OpenVPN is a full-featured, open-source SSL/TLS VPN solution. It enables secure encrypted connections for remote clients and site-to-site tunnels, with support for a wide range of platforms.

## Features

- 🔒 Strong TLS/SSL encryption
- 👥 Multiple simultaneous client connections
- 🌐 Works through most firewalls and proxies (UDP/TCP)
- 📱 Client support for Windows, macOS, Linux, iOS, Android
- 🔑 Certificate-based authentication (PKI via Easy-RSA)
- 📊 Client status and connection logging
- 🔀 Split-tunnel and full-tunnel routing

## Initial Setup

The container requires a one-time initialization before starting. Run the following commands **on the host**:

**1. Initialize the PKI and generate server config:**
```bash
docker run --rm -v /opt/upcode-harbor/data/openvpn:/etc/openvpn kylemanna/openvpn ovpn_genconfig -u udp://<YOUR_SERVER_IP>
docker run --rm -it -v /opt/upcode-harbor/data/openvpn:/etc/openvpn kylemanna/openvpn ovpn_initpki
```

**2. Start the container:**
```bash
docker compose up -d
```

## Adding a Client

```bash
# Generate a client certificate (with passphrase)
docker run --rm -it -v /opt/upcode-harbor/data/openvpn:/etc/openvpn kylemanna/openvpn easyrsa build-client-full <CLIENTNAME>

# Export the client .ovpn profile
docker run --rm -v /opt/upcode-harbor/data/openvpn:/etc/openvpn kylemanna/openvpn ovpn_getclient <CLIENTNAME> > <CLIENTNAME>.ovpn
```

## Revoking a Client

```bash
docker run --rm -it -v /opt/upcode-harbor/data/openvpn:/etc/openvpn kylemanna/openvpn ovpn_revokeclient <CLIENTNAME>
```

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upcode-harbor/data/openvpn` | PKI, server config, CRL, client certificates |

## Default Port

| Port | Protocol | Description |
|---|---|---|
| `1194` | UDP | VPN tunnel traffic |

## Official Documentation

https://github.com/kylemanna/docker-openvpn
