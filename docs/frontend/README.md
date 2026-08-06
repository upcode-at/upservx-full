# Frontend

**Directory:** `upservx/`
**Framework:** Next.js 16, React 19, TypeScript 5
**Styling:** Tailwind CSS v4, Radix UI
**Port:** 9200

---

## Overview

The Upcode Harbor frontend is a **Single Page Application (SPA)** built with Next.js. Despite using Next.js, the dashboard operates as a client-side SPA — all navigation happens via React state without page reloads.

---

## Directory Structure

```
upservx/
├── app/
│   ├── layout.tsx          Root layout (HTML, fonts, metadata)
│   └── page.tsx            Entry point (auth check → Login or Dashboard)
├── components/
│   ├── dashboard.tsx       Main SPA shell with section routing
│   ├── auth-provider.tsx   Authentication context
│   ├── login.tsx           Login form
│   ├── sidebar.tsx         Navigation sidebar
│   ├── header.tsx          Top bar with user info
│   ├── containers/         Container management UI
│   ├── vms/                VM management UI
│   ├── storage/            Storage UI
│   ├── network/            Network UI
│   ├── firewall/           Firewall UI
│   ├── users/              User management UI
│   ├── backup/             Backup UI
│   ├── services/           Services UI
│   ├── settings/           Settings UI
│   ├── logs/               Log viewer
│   ├── notifications/      Notification configuration
│   ├── proxy/              Reverse proxy UI
│   ├── cluster/            Cluster management UI
│   ├── app-store/          App store UI
│   └── ui/                 Shared UI components (shadcn/ui)
├── lib/
│   ├── api.ts              Central API client
│   ├── auth.ts             Auth helper functions
│   └── utils.ts            Utility functions
└── public/                 Static assets
```

---

## Technologies

| Technology | Version | Purpose |
|---|---|---|
| Next.js | 16 | React framework, routing |
| React | 19 | UI library |
| TypeScript | 5 | Type safety |
| Tailwind CSS | v4 | Styling |
| Radix UI | latest | Accessible component primitives |
| shadcn/ui | latest | Pre-built UI components |
| xterm.js | 5.5 | In-browser terminal emulator |
| Lucide React | latest | Icon library |
| Recharts | 2.x | Charts and graphs |

---

## API Communication

All backend requests go through `lib/api.ts`:

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9500";

export async function apiRequest<T>(
    path: string,
    options?: RequestInit
): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            "Authorization": getAuthHeader(),
            ...options?.headers,
        },
        credentials: "include",  // Cookie support
    });

    if (!response.ok) {
        throw new APIError(response.status, await response.json());
    }
    return response.json();
}
```

---

## Auth Flow

```
1. page.tsx loads → checks localStorage for token
2. No token → renders <Login />
3. Login success → token stored in localStorage + cookie
4. AuthProvider supplies { user, permissions, logout } to all components
5. Dashboard renders based on permissions (hides inaccessible menu items)
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:9500` | Backend URL |

Configure in `.env.local`:
```
NEXT_PUBLIC_API_URL=https://my-server.example.com:9500
```

---

## Development

```bash
cd upservx
npm install
npm run dev      # Port 9200
```

## Production Build

```bash
npm run build
npm run start    # Port 9200
```
