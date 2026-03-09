# Frontend Components

**Directory:** `upservx/components/`

---

## Overview

All UI sections of the dashboard are implemented as React components. The main shell (`dashboard.tsx`) renders the active section based on navigation state.

---

## Core Components

### `dashboard.tsx`
The main SPA container. Manages the `activeSection` state, renders the sidebar, header, and selected section component.

```typescript
// Section routing
const sectionComponents: Record<string, React.ComponentType> = {
    "overview":      OverviewDashboard,
    "containers":    ContainersSection,
    "vms":           VMsSection,
    "storage":       StorageSection,
    "network":       NetworkSection,
    "firewall":      FirewallSection,
    "users":         UsersSection,
    "services":      ServicesSection,
    "backup":        BackupSection,
    "logs":          LogsSection,
    "settings":      SettingsSection,
    "notifications": NotificationsSection,
    "proxy":         ProxySection,
    "cluster":       ClusterSection,
    "app-store":     AppStoreSection,
};

const [activeSection, setActiveSection] = useState("overview");
const SectionComponent = sectionComponents[activeSection];
return <SectionComponent />;
```

### `auth-provider.tsx`
React Context for auth state. Contains:
- `user` – current username
- `token` – auth token
- `permissions` – `UserPermissions` object
- `login(username, password)` – auth function
- `logout()` – clears state and token

```typescript
interface UserPermissions {
    is_admin: boolean;
    has_container_access: boolean;
    has_vm_access: boolean;
    has_storage_access: boolean;
    has_shell_access: boolean;
    has_log_access: boolean;
    groups: string[];
}
```

### `sidebar.tsx`
Navigation sidebar. Menu items are shown or hidden based on `permissions`:

```typescript
const menuItems = [
    { key: "overview",    label: "Overview",   icon: LayoutDashboard, always: true },
    { key: "containers",  label: "Containers", icon: Box,             show: permissions.has_container_access },
    { key: "vms",         label: "VMs",        icon: Server,          show: permissions.has_vm_access },
    { key: "storage",     label: "Storage",    icon: HardDrive,       show: permissions.has_storage_access },
    { key: "network",     label: "Network",    icon: Network,         show: permissions.is_admin },
    { key: "firewall",    label: "Firewall",   icon: Shield,          show: permissions.is_admin },
    { key: "users",       label: "Users",      icon: Users,           show: permissions.is_admin },
    { key: "services",    label: "Services",   icon: Activity,        show: permissions.is_admin },
    { key: "backup",      label: "Backup",     icon: Archive,         show: permissions.is_admin },
    { key: "logs",        label: "Logs",       icon: FileText,        show: permissions.has_log_access },
    { key: "app-store",   label: "App Store",  icon: Store,           show: permissions.has_container_access },
    { key: "settings",    label: "Settings",   icon: Settings,        show: permissions.is_admin },
];
```

### `login.tsx`
Login form. Sends credentials to `POST /auth/login` and stores the returned token.

### `header.tsx`
Top bar. Shows the instance name, connected user, and logout button.

---

## Feature Components

### Container Components (`components/containers/`)
| Component | Description |
|---|---|
| `containers-list.tsx` | Table with all containers |
| `container-detail.tsx` | Container detail view |
| `container-logs.tsx` | Log viewer with auto-scroll |
| `container-terminal.tsx` | xterm.js terminal via WebSocket |
| `container-create.tsx` | Create container form |
| `compose-manager.tsx` | Docker Compose projects |
| `app-store.tsx` | App store integration |

### VM Components (`components/vms/`)
| Component | Description |
|---|---|
| `vms-list.tsx` | VM overview table |
| `vm-detail.tsx` | VM detail panel |
| `vm-create.tsx` | Create VM form |
| `vnc-viewer.tsx` | noVNC/xterm VNC window |

### Storage Components (`components/storage/`)
| Component | Description |
|---|---|
| `drives-list.tsx` | Physical drives overview |
| `drive-detail.tsx` | Drive with partitions and SMART |
| `zfs-manager.tsx` | ZFS pool management |

### Other Feature Components
| Section | Components Description |
|---|---|
| `network/` | Interface list, Docker networks, DNS config |
| `firewall/` | Rules table, rule editor, policy overview |
| `users/` | User list, user form, group management, SSH keys |
| `backup/` | Job list, job editor, result history |
| `services/` | Systemd services with log viewer |
| `logs/` | Activity log viewer, system log viewer |
| `settings/` | Settings form, API key management |
| `notifications/` | Notification channel configuration |
| `proxy/` | Reverse proxy route management |
| `cluster/` | Cluster topology, node management |

---

## Shared UI Components (`components/ui/`)

Based on **shadcn/ui** (Radix UI + Tailwind):

| Component | Description |
|---|---|
| `button.tsx` | Default button variants |
| `input.tsx` | Text input |
| `select.tsx` | Dropdown select |
| `dialog.tsx` | Modal dialogs |
| `table.tsx` | Data tables |
| `tabs.tsx` | Tab panels |
| `badge.tsx` | Status badges |
| `card.tsx` | Card container |
| `toast.tsx` | Notification toasts |
| `tooltip.tsx` | Hover tooltips |
| `progress.tsx` | Progress bar |
| `switch.tsx` | Toggle switch |
| `dropdown-menu.tsx` | Context menus |
| `scroll-area.tsx` | Scrollable containers |

---

## Terminal Integration (xterm.js)

```typescript
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";

// 1. Create WS ticket
const ticket = await apiRequest<{ticket: string}>("/system/ws-ticket", {method: "POST"});

// 2. Open WebSocket
const ws = new WebSocket(`${WS_URL}/containers/${name}/terminal?ticket=${ticket.ticket}`);

// 3. Initialize xterm
const term = new Terminal({ cursorBlink: true, theme: { background: "#0f0f0f" }});
const fitAddon = new FitAddon();
term.loadAddon(fitAddon);
term.open(containerRef.current);
fitAddon.fit();

// 4. Bind WebSocket ↔ Terminal
ws.onmessage = (e) => term.write(e.data);
term.onData((data) => ws.send(data));
```
