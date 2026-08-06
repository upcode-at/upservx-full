# UpservX Frontend

The UpservX web interface is a Next.js 16 application using React 19,
TypeScript, Tailwind CSS 4, Radix UI, and xterm.js.

## Requirements

- Node.js 20 or newer
- The locked dependencies from `package-lock.json`
- An UpservX API reachable through the same-origin `/api` proxy

## Development

From this directory:

```bash
npm ci
npm run dev
```

The development server listens on port 9200. Authentication uses the secure
UpservX session cookie; configure HTTPS through the repository's nginx setup
when testing the production login flow.

## Quality Gates

```bash
npm run lint
npm run build
```

The repository-level `make test` command additionally runs backend, CLI,
contract, App Store, and shell checks before executing these frontend gates.

## Production Deployment

Do not deploy this directory independently with a generic Next.js hosting
provider. The supported installer builds it into an immutable UpservX release,
runs it as the unprivileged `upservx-web` service on loopback port 9200, and
exposes it through the managed HTTPS nginx endpoint.

See [the installation guide](../docs/installation.md) and
[the architecture documentation](../docs/architecture.md) for the complete
deployment and authentication contract.
