# App Store templates

Upcode Harbor ships 62 schema-versioned Docker Compose templates in
`app-store-templates/`. `app-store-templates/app.schema.json` is the canonical
manifest contract. A template is eligible for listing or installation only
when both its `app.json` and `docker-compose.yml` pass validation.

## Required files and contract

Each template directory contains `app.json`, `docker-compose.yml`, and a
`README.md`. An optional PNG/JPEG icon may be included. The directory name must
equal the manifest `id`.

The version 1 manifest uses these canonical shapes:

```json
{
  "schema_version": 1,
  "id": "example",
  "name": "Example",
  "description": "Example service",
  "version": "1.2.3",
  "category": "tools",
  "icon": "🧰",
  "author": "Example",
  "ports": [
    {"host": 8080, "container": 80, "protocol": "tcp", "description": "Web UI"}
  ],
  "volumes": [
    {"host": "./data", "container": "/data", "mode": "rw", "description": "Data"}
  ],
  "environment": [
    {
      "name": "ADMIN_PASSWORD",
      "label": "Administrator password",
      "description": "Initial administrator credential",
      "default": "",
      "required": true,
      "secret": true,
      "generate": true,
      "min_length": 24
    }
  ],
  "update": {"strategy": "compose-pull-recreate"}
}
```

Environment variables may additionally be marked `managed`; the backend sets
these and rejects client overrides. `APP_DATA_DIR` is the supported managed
per-installation data root. Generated values are created with Python's
cryptographic `secrets` module and stored only in the project's owner-readable
`.env` file.

Compose images must use intentional release tags or immutable digests. Floating
tags such as `latest`, `stable`, `main`, and `lts`, hard-coded container names,
undeclared variables, and hard-coded credentials are rejected. Secret manifest
defaults must always be empty.

## Validation

From the repository root, validate the JSON schema, security invariants, YAML,
and every rendered Compose project:

```bash
python tools/validate_app_store.py
```

This requires the locked backend Python dependencies and Docker Compose. The
repository-wide `make test` command provisions those dependencies in a
temporary virtual environment and runs this validation as a mandatory gate.

## Transactional installation

`POST /containers/app-store/apps/{template_id}/install` accepts:

```json
{
  "custom_name": "customer-example",
  "environment": {"PUBLIC_HOSTNAME": "example.internal"}
}
```

The backend validates the template and submitted fields, generates omitted
secrets, copies the template into `/var/lib/upservx/compose/{project}`, writes a
mode-0600 `.env`, renders `docker compose config`, pulls the pinned images, and
runs `docker compose up -d --wait`. Any failure triggers `down --volumes`, then
removes the incomplete project and its managed bind-data directory. Installed
project metadata stores variable names but never their values.

Custom project names are recorded in `.upservx-installation.json`; listing and
status checks use that project name rather than assuming it equals the template
ID. Uninstall removes Compose resources, project metadata, and managed bind
data. It does not delete anything when `docker compose down` fails.

## Tested update path

`POST /containers/app-store/apps/{project_name}/update` supports the manifest's
`compose-pull-recreate` strategy. It preserves existing environment values,
creates newly introduced generated secrets, validates the new Compose file,
pulls its pinned images, and waits for services to become running/healthy. If
that fails, the old manifest, Compose file, and `.env` are restored and the old
stack is recreated. Unit tests exercise successful install/update, generated
secrets, custom names, and rollback behavior.

To update an image, change its exact tag and the manifest version together,
then run `make test`. Do not use an uncontrolled floating tag as an update
mechanism.

## Adding a template

Copy an existing version 1 template, change its ID and metadata, declare every
Compose variable in `environment`, pin all images, and run the validator. CI
rejects incomplete directories and invalid schemas or Compose projects.
