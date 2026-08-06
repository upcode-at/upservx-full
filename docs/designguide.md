# Upcode Harbor Design Guide

> Reference for all design decisions, colors, typography, and UI patterns in the Upcode Harbor project.

---

## 1. Color System

The color system is based on CSS Custom Properties and supports Light and Dark mode. All colors are mapped via Tailwind CSS variables.

### 1.1 Light Mode (`:root`)

| Token | CSS Variable | Hex Value | Usage |
|---|---|---|---|
| background | `--background` | `#fafbfc` | Page background |
| foreground | `--foreground` | `#0f172a` | Primary text |
| card | `--card` | `#ffffff` | Card background |
| card-foreground | `--card-foreground` | `#1e293b` | Text on cards |
| popover | `--popover` | `#ffffff` | Popover background |
| popover-foreground | `--popover-foreground` | `#1e293b` | Text in popovers |
| **primary** | `--primary` | `#ef4444` | Brand color (Red) |
| primary-foreground | `--primary-foreground` | `#ffffff` | Text on primary |
| secondary | `--secondary` | `#f1f5f9` | Secondary surfaces |
| secondary-foreground | `--secondary-foreground` | `#334155` | Text on secondary |
| muted | `--muted` | `#f8fafc` | Muted surfaces |
| muted-foreground | `--muted-foreground` | `#64748b` | Muted text, labels |
| **accent** | `--accent` | `#6366f1` | Accent color (Indigo) |
| accent-foreground | `--accent-foreground` | `#4338ca` | Text on accent |
| destructive | `--destructive` | `#ef4444` | Delete / error actions |
| border | `--border` | `#e2e8f0` | Borders |
| input | `--input` | `#f1f5f9` | Input field background |
| ring | `--ring` | `#ef4444` | Focus ring |

**Sidebar (Light):**

| Token | CSS Variable | Hex-Wert |
|---|---|---|
| sidebar | `--sidebar` | `#ffffff` |
| sidebar-foreground | `--sidebar-foreground` | `#1e293b` |
| sidebar-primary | `--sidebar-primary` | `#ef4444` |
| sidebar-primary-foreground | `--sidebar-primary-foreground` | `#ffffff` |
| sidebar-accent | `--sidebar-accent` | `#f8fafc` |
| sidebar-accent-foreground | `--sidebar-accent-foreground` | `#4338ca` |
| sidebar-border | `--sidebar-border` | `#e2e8f0` |
| sidebar-ring | `--sidebar-ring` | `#ef4444` |

---

### 1.2 Dark Mode (`.dark`)

| Token | CSS Variable | Hex Value | Usage |
|---|---|---|---|
| background | `--background` | `#0f172a` | Slate-900 |
| foreground | `--foreground` | `#f8fafc` | Near white |
| card | `--card` | `#1e293b` | Slate-800 |
| card-foreground | `--card-foreground` | `#f1f5f9` | |
| popover | `--popover` | `#1e293b` | |
| popover-foreground | `--popover-foreground` | `#f1f5f9` | |
| **primary** | `--primary` | `#f87171` | Red-400 (lighter) |
| primary-foreground | `--primary-foreground` | `#1e1b4b` | Indigo-950 |
| secondary | `--secondary` | `#334155` | Slate-700 |
| secondary-foreground | `--secondary-foreground` | `#e2e8f0` | |
| muted | `--muted` | `#334155` | |
| muted-foreground | `--muted-foreground` | `#94a3b8` | Slate-400 |
| **accent** | `--accent` | `#818cf8` | Indigo-400 |
| accent-foreground | `--accent-foreground` | `#1e1b4b` | |
| destructive | `--destructive` | `#f87171` | |
| border | `--border` | `#334155` | |
| input | `--input` | `#475569` | Slate-600 |
| ring | `--ring` | `#f87171` | |

**Sidebar (Dark):**

| Token | CSS Variable | Hex-Wert |
|---|---|---|
| sidebar | `--sidebar` | `#1e293b` |
| sidebar-foreground | `--sidebar-foreground` | `#f1f5f9` |
| sidebar-primary | `--sidebar-primary` | `#f87171` |
| sidebar-primary-foreground | `--sidebar-primary-foreground` | `#1e1b4b` |
| sidebar-accent | `--sidebar-accent` | `#818cf8` |
| sidebar-accent-foreground | `--sidebar-accent-foreground` | `#1e1b4b` |
| sidebar-border | `--sidebar-border` | `#334155` |
| sidebar-ring | `--sidebar-ring` | `#f87171` |

---

### 1.3 Chart Colors

Used in charts and data visualizations.

| Token | Light | Dark | Meaning |
|---|---|---|---|
| chart-1 | `#3b82f6` | `#60a5fa` | Blue – primary data series |
| chart-2 | `#10b981` | `#34d399` | Green – positive / online |
| chart-3 | `#f59e0b` | `#fbbf24` | Yellow – warning / medium |
| chart-4 | `#8b5cf6` | `#a78bfa` | Purple – fourth data series |
| chart-5 | `#ef4444` | `#f87171` | Red – critical / primary |

---

### 1.4 Semantic Status Colors

Used in badges, icons, and status indicators (Tailwind classes):

| Status | Tailwind Class | Hex (Light) |
|---|---|---|
| Online / Active | `bg-green-500` | `#22c55e` |
| Warning | `bg-yellow-500` | `#eab308` |
| Error / Critical | `bg-red-500` | `#ef4444` |
| Inactive / Stopped | `bg-gray-400` | `#9ca3af` |
| Info | `bg-blue-500` | `#3b82f6` |

---

## 2. Typography

### 2.1 Fonts

| Role | Font | Integration |
|---|---|---|
| Sans-serif (UI) | Inter | `next/font/google` |
| Monospace (Code, Terminal) | Geist Mono | CSS variable `--font-geist-mono` |

**Font Feature Settings (Body):**
```css
font-feature-settings: "cv02", "cv03", "cv04", "cv11";
```

### 2.2 Type Scale (Tailwind)

| Class | Size | Usage |
|---|---|---|
| `text-xs` | 12px | Labels, badges, timestamps |
| `text-sm` | 14px | Sidebar items, table content |
| `text-base` | 16px | Default body text |
| `text-lg` | 18px | Card titles |
| `text-xl` | 20px | Page headings |
| `text-2xl` | 24px | Dashboard metrics |
| `text-3xl` | 30px | Hero numbers |

### 2.3 Font Weights

| Class | Usage |
|---|---|
| `font-normal` | Body text, table content |
| `font-medium` | Sidebar items, button labels |
| `font-semibold` | Card headings |
| `font-bold` | Page titles, category labels |
| `font-mono` | Version numbers, code, API keys |

---

## 3. Border Radius

Defined via `--radius: 0.875rem`:

| Token | Value | Tailwind Equivalent |
|---|---|---|
| `--radius-sm` | `calc(0.875rem - 4px)` = ~0.625rem | `rounded-sm` |
| `--radius-md` | `calc(0.875rem - 2px)` = ~0.75rem | `rounded-md` |
| `--radius-lg` | `0.875rem` | `rounded-lg` |
| `--radius-xl` | `calc(0.875rem + 4px)` = ~1.125rem | `rounded-xl` |

> **Note:** Sidebar buttons explicitly use `rounded-none` for a flat, edge-aligned design.

---

## 4. Custom CSS Classes

These classes are defined in `app/globals.css` under `@layer components`.

### `.upcode-harbor-gradient`
Primary red gradient for accent elements.
```css
background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
```

### `.upcode-harbor-card`
Subtle card styling with a glassmorphism approach.
```css
/* Tailwind */
bg-card border border-border/50 backdrop-blur-sm

/* Box-Shadow */
0 1px 3px 0 rgb(0 0 0 / 0.1),
0 1px 2px -1px rgb(0 0 0 / 0.1),
0 0 0 1px rgb(255 255 255 / 0.05) inset

/* Gradient */
linear-gradient(to bottom right, hsl(--card) 0%, hsl(--card / 0.8) 100%)
```

### `.upcode-harbor-glass`
Full glassmorphism effect.
```css
/* Tailwind */
bg-background/60 backdrop-blur-md border border-border/30

/* Box-Shadow */
0 8px 32px 0 rgba(31, 38, 135, 0.37),
0 0 0 1px rgba(255, 255, 255, 0.18) inset
```

### `.upcode-harbor-button-primary`
Custom primary button with hover-lift effect.
```css
background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
box-shadow:
  0 4px 14px 0 rgba(239, 68, 68, 0.35),
  0 0 0 1px rgba(255, 255, 255, 0.2) inset;
transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

/* On Hover */
transform: translateY(-1px);
box-shadow:
  0 8px 25px 0 rgba(239, 68, 68, 0.4),
  0 0 0 1px rgba(255, 255, 255, 0.3) inset;
```

### `.upcode-harbor-sidebar`
Sidebar container with backdrop blur.
```css
/* Tailwind */
bg-sidebar/95 backdrop-blur-sm border-r border-sidebar-border/50

/* Gradient */
linear-gradient(to bottom, hsl(--sidebar) 0%, hsl(--sidebar / 0.95) 100%)
```

---

## 5. Button Patterns

Standardized in `lib/button-patterns.ts`. All buttons use the Radix UI / shadcn `<Button>` component.

### 5.1 Variants

| Variant | Usage |
|---|---|
| `default` | Primary actions (create, start, save) |
| `outline` | Secondary actions (edit, cancel, export) |
| `destructive` | Dangerous actions (delete, stop) |
| `ghost` | Utility actions (search, filter, refresh) |

### 5.2 Button Pattern Overview

| Pattern | Variante | Icon | Loading-Text |
|---|---|---|---|
| `create` | default | Plus | "Creating..." |
| `add` | default | Plus | "Adding..." |
| `save` | default | Save | "Saving..." |
| `edit` | outline | Edit | – |
| `cancel` | outline | X | – |
| `delete` | destructive | Trash2 | "Deleting..." |
| `remove` | destructive | Trash2 | "Removing..." |
| `download` | outline | Download | "Downloading..." |
| `upload` | outline | Upload | "Uploading..." |
| `export` | outline | Download | – |
| `import` | outline | Upload | – |
| `start` | default | Play | "Starting..." |
| `stop` | destructive | Square | "Stopping..." |
| `pause` | outline | Pause | – |
| `restart` | outline | RotateCw | "Restarting..." |
| `power` | outline | Power | – |
| `search` | ghost | Search | – |
| `filter` | ghost | Filter | – |
| `settings` | ghost | Settings | – |
| `refresh` | ghost | RefreshCw | – |

### 5.3 Button Sizes

| Key | Size |
|---|---|
| `sm` | Small |
| `default` | Default |
| `lg` | Large |
| `icon` | Square (icon only) |

### 5.4 Button Group Spacing

```tsx
// Standard spacing between buttons in a group
className="space-x-2"
```

---

## 6. Sidebar Design

- **Width:** `w-64` (256px), fixed – no collapse
- **Buttons:** `rounded-none`, `h-11` for top-level items; `h-9 text-sm` for sub-items
- **Active state:** `bg-primary/70 text-white` + white dot indicator on the right
- **Hover state:** `hover:bg-primary/50 hover:border-l-4 hover:border-primary hover:text-white`
- **Categories:** Uppercase labels, `text-xs font-bold tracking-wide`
- **Icon size:** `h-4 w-4`, `mr-3`
- **Chevron:** `ChevronRight` / `ChevronDown` for expandable sub-menus

---

## 7. Layout Structure

```
┌─────────────────────────────────────────────┐
│  Sidebar (w-64, fixed)  │  Header (h-auto)  │
│                         ├───────────────────│
│  Logo + Hostname        │  Main Content     │
│  Navigation             │  (flex-1,         │
│  User Info + Logout     │   overflow-auto,  │
│                         │   p-4/6/8)        │
└─────────────────────────────────────────────┘
```

- Root: `flex h-screen bg-background`
- Content wrapper: `flex-1 flex flex-col overflow-hidden`
- Main: `flex-1 overflow-auto p-4 md:p-6 lg:p-8`

---

## 8. Icon Library

**Lucide React** (`lucide-react`) – the only icon source in the project.

Default icon size: `h-4 w-4` (16px)

Commonly used icons:

| Icon | Usage |
|---|---|
| `BarChart3` | Dashboard |
| `Terminal` | Shell |
| `Server` | Virtual Machines |
| `Container` | Docker Container |
| `FileText` | Compose, Logs |
| `HardDrive` | Storage |
| `Network` | Network |
| `Shield` | Firewall, Backup |
| `Users` | User Management |
| `Store` | App Store |
| `Settings` | Settings |
| `GitBranch` | Cluster |
| `LogOut` | Logout |
| `User` | User avatar |

---

## 9. Animations & Transitions

| Element | Transition |
|---|---|
| Sidebar buttons | `transition-all duration-200` |
| Primary button hover | `transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1)` |
| Status indicator (green) | `animate-pulse` |
| tw-animate-css | Globally imported for extended animations |

---

## 10. shadcn/ui Configuration

```json
{
  "style": "new-york",
  "tailwind": {
    "cssVariables": true,
    "baseColor": "neutral"
  },
  "iconLibrary": "lucide"
}
```

**Available UI primitives** (`components/ui/`):

| Component | Radix Base |
|---|---|
| `alert.tsx` | – |
| `badge.tsx` | – |
| `button.tsx` | `@radix-ui/react-slot` |
| `card.tsx` | – |
| `dialog.tsx` | `@radix-ui/react-dialog` |
| `dropdown-menu.tsx` | `@radix-ui/react-dropdown-menu` |
| `input.tsx` | – |
| `label.tsx` | `@radix-ui/react-label` |
| `notification.tsx` | – |
| `progress.tsx` | `@radix-ui/react-progress` |
| `scroll-area.tsx` | `@radix-ui/react-scroll-area` |
| `select.tsx` | `@radix-ui/react-select` |
| `switch.tsx` | `@radix-ui/react-switch` |
| `table.tsx` | – |
| `tabs.tsx` | `@radix-ui/react-tabs` |

---

## 11. Theme System

- Provider: `next-themes`
- Default: `system` (follows OS preference)
- Attribute: `class` (`.dark` on `<html>`)
- `suppressHydrationWarning` set on `<html>`

```tsx
<ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
```

---

## 12. Color Palette Quick Reference

```
PRIMARY (Red)
  Light:  #ef4444  (red-500)
  Dark:   #f87171  (red-400)

ACCENT (Indigo)
  Light:  #6366f1  (indigo-500)
  Dark:   #818cf8  (indigo-400)

BACKGROUND
  Light:  #fafbfc
  Dark:   #0f172a  (slate-900)

SURFACE / CARD
  Light:  #ffffff
  Dark:   #1e293b  (slate-800)

SIDEBAR
  Light:  #ffffff
  Dark:   #1e293b  (slate-800)

TEXT PRIMARY
  Light:  #0f172a  (slate-900)
  Dark:   #f8fafc  (slate-50)

TEXT MUTED
  Light:  #64748b  (slate-500)
  Dark:   #94a3b8  (slate-400)

BORDER
  Light:  #e2e8f0  (slate-200)
  Dark:   #334155  (slate-700)
```
