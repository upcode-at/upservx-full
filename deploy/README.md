# Upcode Harbor deployment contract

`upcode-harbor` is the deployment identifier for system users, units, paths,
helper binaries, and signed update files. Environment variables use the
`UPCODE_HARBOR_*` prefix. Version 0.7.0 installs no aliases for the previous
technical namespace and therefore starts a new deployment contract.

The installed process and privilege model is intentionally fixed:

- `upcode-harbor-web` runs only the Next.js frontend.
- `upcode-harbor` runs the API and persistent job worker.
- Docker, LXD, libvirt/KVM, and log-reading groups are granted only for the
  selected installer profiles.
- Host mutations use `/usr/local/libexec/upcode-harbor-privileged`. The sudoers file
  grants no other root command, and the helper validates every operation and
  argument. Helper command shims are visible only in backend units.
- Application releases are immutable, root-owned directories below
  `/opt/upcode-harbor/releases`; `/opt/upcode-harbor/current` is switched atomically.
- Mutable data lives below `/var/lib/upcode-harbor`; secrets live below
  `/etc/upcode-harbor`; logs live below `/var/log/upcode-harbor`.
- Existing Linux users authenticate through the dedicated `/etc/pam.d/upcode-harbor`
  policy; Upcode Harbor does not create or store application login accounts.
- The installer binds the API and frontend to loopback and exposes them through
  an HTTPS-only nginx proxy. A local certificate is generated for the first
  boot; replace `/etc/upcode-harbor/tls/server.crt` and `server.key` with a trusted
  certificate for production clients.

## Signed updates

For version `VERSION`, stage these root-owned files in
`/var/lib/upcode-harbor/updates/VERSION/`:

- `upcode-harbor-VERSION.tar.gz`
- `upcode-harbor-VERSION.sha256`
- `upcode-harbor-VERSION.sig`

The signature is an OpenSSL SHA-256 signature of the artifact and must verify
with `/usr/share/upcode-harbor/update-public.pem`. For example, the release system signs
with:

```sh
openssl dgst -sha256 -sign release-private.pem \
  -out upcode-harbor-VERSION.sig upcode-harbor-VERSION.tar.gz
sha256sum upcode-harbor-VERSION.tar.gz > upcode-harbor-VERSION.sha256
```

The repository helper performs the reproducible archive, checksum, and signing
steps together:

```sh
deploy/build-release-artifact VERSION release-private.pem ./dist/VERSION
```

Write `VERSION` to `/var/lib/upcode-harbor/updates/latest` (root-owned, mode `0640`)
to make it the update selected by the web UI. The API asks the independent
`upcode-harbor-update@VERSION.service` unit to apply it. That unit verifies the
checksum and signature, backs up `/etc/upcode-harbor`, builds a new immutable
release, atomically switches `current`, and rolls back when readiness checks
fail. A non-zero updater result is stored as a failed persistent job.
