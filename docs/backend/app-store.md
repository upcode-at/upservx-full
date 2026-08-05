# App Store backend

The runtime is implemented in
`upservx-service/handlers/app_store.py`, exposed under
`/containers/app-store`, and validated by
`upservx-service/lib/app_store_validation.py`.

Available routes are:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/containers/app-store/apps` | Valid templates and installation status |
| `GET` | `/containers/app-store/categories` | Template categories |
| `GET` | `/containers/app-store/apps/{id}` | Manifest, Compose, and README details |
| `GET` | `/containers/app-store/apps/{id}/icon` | Local template icon |
| `POST` | `/containers/app-store/apps/{id}/install` | Transactional validated installation |
| `POST` | `/containers/app-store/apps/{project}/update` | Pinned transactional update |
| `DELETE` | `/containers/app-store/apps/{project}/uninstall` | Remove stack, volumes, metadata, and managed data |

The canonical manifest contract, secret handling, filesystem layout,
transaction and rollback behavior, and application update procedure are
documented in [the App Store template guide](../app-store/README.md).
