# UpservX deployment contract

The installed process and privilege model is intentionally fixed:

- `upservx-web` runs only the Next.js frontend.
- `upservx` runs the API and persistent job worker.
- Docker, LXD, libvirt/KVM, and log-reading groups are granted only for the
  selected installer profiles.
- Host mutations use `/usr/local/libexec/upservx-privileged`. The sudoers file
  grants no other root command, and the helper validates every operation and
  argument. Helper command shims are visible only in backend units.
- Application releases are immutable, root-owned directories below
  `/opt/upservx/releases`; `/opt/upservx/current` is switched atomically.
- Mutable data lives below `/var/lib/upservx`; secrets live below
  `/etc/upservx`; logs live below `/var/log/upservx`.
- Existing Linux users authenticate through the dedicated `/etc/pam.d/upservx`
  policy; UpservX does not create or store application login accounts.
- The installer binds the API and frontend to loopback and exposes them through
  an HTTPS-only nginx proxy. A local certificate is generated for the first
  boot; replace `/etc/upservx/tls/server.crt` and `server.key` with a trusted
  certificate for production clients.

## Signed updates

For version `VERSION`, stage these root-owned files in
`/var/lib/upservx/updates/VERSION/`:

- `upservx-VERSION.tar.gz`
- `upservx-VERSION.sha256`
- `upservx-VERSION.sig`

The signature is an OpenSSL SHA-256 signature of the artifact and must verify
with `/usr/share/upservx/update-public.pem`. For example, the release system signs
with:

```sh
openssl dgst -sha256 -sign release-private.pem \
  -out upservx-VERSION.sig upservx-VERSION.tar.gz
sha256sum upservx-VERSION.tar.gz > upservx-VERSION.sha256
```

The repository helper performs the reproducible archive, checksum, and signing
steps together:

```sh
deploy/build-release-artifact VERSION release-private.pem ./dist/VERSION
```

Write `VERSION` to `/var/lib/upservx/updates/latest` (root-owned, mode `0640`)
to make it the update selected by the web UI. The API asks the independent
`upservx-update@VERSION.service` unit to apply it. That unit verifies the
checksum and signature, backs up `/etc/upservx`, builds a new immutable
release, atomically switches `current`, and rolls back when readiness checks
fail. A non-zero updater result is stored as a failed persistent job.
