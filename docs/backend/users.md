# User Management

**File:** `upservx-service/users.py`
**API sub-module:** `upservx-service/api/users.py`

**Required permission:** Admin (`sudo`/`wheel`)

---

## Overview

UpservX manages **Linux system users** on the host. There is no separate user database — all users are actual Linux users, managed via standard Linux tools:

- `useradd` / `usermod` / `userdel`
- `passwd` / `chpasswd`
- `groupadd` / `groupdel` / `gpasswd`
- `getent passwd` / `getent group`

---

## Data Model: `SystemUser`

```python
class SystemUser(BaseModel):
    username: str
    uid: int
    gid: int
    home: str
    shell: str
    groups: List[str]
    is_system_user: bool     # UID < 1000
    has_password: bool
    last_login: str
```

---

## User Listing

System users are filtered:To exclude service accounts, only users with UID >= 1000 are shown by default (or optionally include all users with `?include_system=true`).

```python
def get_users(include_system: bool = False) -> List[SystemUser]:
    users = [u for u in pwd.getpwall() if include_system or u.pw_uid >= 1000]
```

---

## Creating Users

```python
def create_user(username, password, groups, shell, home):
    subprocess.run(["useradd", "-m", "-s", shell, "-d", home, username])
    subprocess.run(["chpasswd"], input=f"{username}:{password}")
    for group in groups:
        subprocess.run(["gpasswd", "-a", username, group])
```

---

## Modifying Users

| Action | Command |
|---|---|
| Change password | `echo "user:pass" \| chpasswd` |
| Change shell | `usermod -s /bin/bash username` |
| Add to group | `gpasswd -a username groupname` |
| Remove from group | `gpasswd -d username groupname` |
| Lock account | `usermod -L username` |
| Unlock account | `usermod -U username` |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/users` | All users |
| `POST` | `/users` | Create new user |
| `GET` | `/users/{name}` | User details |
| `PUT` | `/users/{name}` | Edit user |
| `DELETE` | `/users/{name}` | Delete user |
| `POST` | `/users/{name}/password` | Change password |
| `POST` | `/users/{name}/lock` | Lock account |
| `POST` | `/users/{name}/unlock` | Unlock account |
| `GET` | `/groups` | All Linux groups |
| `POST` | `/groups` | Create group |
| `DELETE` | `/groups/{name}` | Delete group |
| `POST` | `/groups/{name}/members` | Add user to group |
| `DELETE` | `/groups/{name}/members/{user}` | Remove user from group |

---

## SSH Key Management

**File:** `upservx-service/ssh_keys.py`

SSH public keys are stored in `upservx-service/ssh_keys/` and written to `~/.ssh/authorized_keys`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/users/{name}/ssh-keys` | SSH keys of a user |
| `POST` | `/users/{name}/ssh-keys` | Add SSH key |
| `DELETE` | `/users/{name}/ssh-keys/{key_id}` | Delete SSH key |
