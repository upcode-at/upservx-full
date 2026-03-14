"use client"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Server,
  Container,
  BarChart3,
  HardDrive,
  Network,
  Shield,
  Users,
  Disc,
  FileText,
  Settings,
  Terminal,
  Store,
  GitBranch,
  ChevronDown,
  ChevronRight,
  LogOut,
  User,
  Sun,
  Moon,
  Monitor,
} from "lucide-react"
import { useEffect, useState } from "react"
import { apiUrl } from "@/lib/api"
import { useTheme } from "next-themes"
import { useAuth } from "@/components/auth-provider"
import { useRouter } from "next/navigation"
import { UserSettings } from "@/components/user-settings"

interface SidebarProps {
  activeSection: string
  onSectionChange: (section: string) => void
}

interface SidebarItem {
  id: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  requires: "admin" | "containers" | "vms" | "storage" | "shell" | "logs" | null
  subItems?: { id: string; label: string }[]
}

export function Sidebar({ activeSection, onSectionChange }: SidebarProps) {
  const [hostname, setHostname] = useState("")
  const { theme, setTheme, resolvedTheme } = useTheme()
  const [storageExpanded, setStorageExpanded] = useState(false)
  const [userSettingsOpen, setUserSettingsOpen] = useState(false)
  const { setToken, username, permissions } = useAuth()
  const router = useRouter()
  const [hasCustomLogo, setHasCustomLogo] = useState(false)
  const [logoTimestamp, setLogoTimestamp] = useState(Date.now())

  const handleLogout = () => {
    setToken(null)
    router.push("/login")
  }

  useEffect(() => {
    const loadHostname = async () => {
      try {
        const res = await fetch(apiUrl("/info"))
        if (res.ok) {
          const data = await res.json()
          setHostname(data.hostname)
        }
      } catch (err) {
        console.error(err)
      }
    }
    const loadCustomization = async () => {
      try {
        const res = await fetch(apiUrl("/settings/customization"))
        if (res.ok) {
          const data = await res.json()
          setHasCustomLogo(data.has_logo === true)
          setLogoTimestamp(Date.now())
        }
      } catch {
        // silently fall back to default
      }
    }
    loadHostname()
    loadCustomization()
  }, [])

  const categories: { title: string; items: SidebarItem[] }[] = [
    {
      title: "System",
      items: [
        { id: "dashboard", label: "Dashboard", icon: BarChart3, requires: null },
        { id: "shell",     label: "Shell",     icon: Terminal,  requires: "shell" as const },
        { id: "cluster",  label: "Cluster",   icon: GitBranch, requires: null },
      ],
    },
    {
      title: "Compute",
      items: [
        { id: "vms",        label: "Virtual Machines", icon: Server,    requires: "vms" as const },
        { id: "containers", label: "Container",        icon: Container, requires: "containers" as const },
        { id: "compose",    label: "Compose Builder",  icon: FileText,  requires: "containers" as const },
      ],
    },
    {
      title: "Resources",
      items: [
        { id: "images", label: "Images & ISOs", icon: Disc, requires: null },
        {
          id: "storage",
          label: "Storage",
          icon: HardDrive,
          requires: "storage" as const,
          subItems: [
            { id: "storage",           label: "Physical Storage" },
            { id: "container-storage", label: "Container Storage" },
          ]
        },
      ],
    },
    {
      title: "Administration",
      items: [
        { id: "app-store", label: "App Store", icon: Store,    requires: "containers" as const },
        { id: "settings",  label: "Settings",  icon: Settings, requires: "admin" as const },
        { id: "users",     label: "Users",     icon: Users,    requires: "admin" as const },
        { id: "backup",    label: "Backup",    icon: Shield,   requires: "admin" as const },
        { id: "network",   label: "Network",   icon: Network,  requires: "admin" as const },
        { id: "firewall",  label: "Firewall",  icon: Shield,   requires: "admin" as const },
        { id: "logs",      label: "Logs",      icon: FileText, requires: "logs" as const },
      ],
    },
  ]

  // Filter items the current user has no access to
  const hasPermission = (requires: "admin" | "containers" | "vms" | "storage" | "shell" | "logs" | null) => {
    if (!requires) return true
    return permissions[requires] === true
  }

  return (
    <div className="w-64 upservx-sidebar flex flex-col">
      <div className="p-6 border-b border-sidebar-border/30">
        <div className="flex items-center space-x-3 mb-2">
          <img
            src={
              hasCustomLogo
                ? `${apiUrl("/settings/customization/logo/file")}?t=${logoTimestamp}`
                : theme === "dark"
                ? "/logo_light.png"
                : "/logo.png"
            }
            alt="UpServX Logo"
            className="h-16 w-auto object-contain"
          />
        </div>
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <p className="text-sm text-muted-foreground font-medium">{hostname || "Local Server"}</p>
          </div>
          <p className="text-xs text-muted-foreground/60 font-mono pl-4">v0.3.0</p>
        </div>
      </div>
      <nav className="flex-1 p-4 space-y-6">
        {categories.map((category) => {
          const visibleItems = category.items.filter((item) => hasPermission(item.requires ?? null))
          if (visibleItems.length === 0) return null
          return (
          <div key={category.title} className="space-y-3">
            <div className="px-3 text-xs font-bold text-muted-foreground uppercase tracking-wide">
              {category.title}
            </div>
            <div className="space-y-1">
              {visibleItems.map((item) => {
                const Icon = item.icon
                const isActive = activeSection === item.id
                const hasSubItems = item.subItems && item.subItems.length > 0
                const isExpanded = item.id === "storage" ? storageExpanded : false

                return (
                  <div key={item.id}>
                    <Button
                      variant="ghost"
                      className={cn(
                        "w-full justify-start h-11 font-medium transition-all duration-200 rounded-none",
                        isActive 
                          ? "bg-primary/70 text-white shadow-sm" 
                          : "hover:bg-primary/50 hover:border-l-4 hover:border-primary hover:text-white"
                      )}
                      onClick={() => {
                        if (hasSubItems) {
                          if (item.id === "storage") {
                            setStorageExpanded(!storageExpanded)
                          }
                        } else {
                          onSectionChange(item.id)
                        }
                      }}
                    >
                      <Icon className={cn(
                        "mr-3 h-4 w-4 transition-colors",
                        isActive ? "text-white" : "text-muted-foreground"
                      )} />
                      {item.label}
                      {hasSubItems && (
                        <div className="ml-auto">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4" />
                          ) : (
                            <ChevronRight className="h-4 w-4" />
                          )}
                        </div>
                      )}

                    </Button>
                    {hasSubItems && isExpanded && (
                      <div className="ml-6 space-y-1 mt-1">
                        {item.subItems?.map((subItem) => {
                          const subIsActive = activeSection === subItem.id
                          return (
                            <Button
                              key={subItem.id}
                              variant="ghost"
                              className={cn(
                                "w-full justify-start h-9 font-normal text-sm transition-all duration-200 rounded-none",
                                subIsActive 
                                  ? "bg-primary/50 text-white" 
                                  : "hover:bg-primary/30 hover:text-white"
                              )}
                              onClick={() => onSectionChange(subItem.id)}
                            >
                              {subItem.label}

                            </Button>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
          )
        })}
      </nav>
      <div className="p-4 border-t border-sidebar-border/30">
        <div className="flex items-center gap-2 px-3 py-2 mb-1">
          <div className="flex items-center gap-1.5 flex-1">
            <Sun className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <button
              onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
              className={cn(
                "relative w-8 h-4 rounded-full transition-colors shrink-0",
                resolvedTheme === "dark" ? "bg-primary" : "bg-muted-foreground/40"
              )}
              aria-label="Toggle light/dark mode"
            >
              <span
                className={cn(
                  "absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform duration-200",
                  resolvedTheme === "dark" ? "translate-x-0" : "translate-x-4"
                )}
              />
            </button>
            <Moon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          </div>
          <button
            onClick={() => setTheme("system")}
            className={cn(
              "flex items-center gap-1 px-2 py-0.5 rounded text-xs transition-colors",
              theme === "system"
                ? "bg-primary/20 text-primary font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
            )}
            aria-label="Use system theme"
          >
            <Monitor className="h-3 w-3" />
            <span>System</span>
          </button>
        </div>
        <div
          onClick={() => setUserSettingsOpen(true)}
          className="flex items-center space-x-2 px-3 py-2 w-full rounded-md transition-colors hover:bg-primary/10 cursor-pointer group"
          role="button"
          aria-label="Open user settings"
        >
          <div className="flex items-center justify-center w-7 h-7 rounded-full bg-primary/20 shrink-0 group-hover:bg-primary/30 transition-colors">
            <User className="h-3.5 w-3.5 text-primary" />
          </div>
          <span className="text-sm font-medium text-muted-foreground truncate flex-1 text-left">{username || "User"}</span>
          <button
            onClick={(e) => { e.stopPropagation(); handleLogout() }}
            className="text-muted-foreground hover:text-destructive transition-colors p-1 rounded"
            aria-label="Logout"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
        <UserSettings open={userSettingsOpen} onOpenChange={setUserSettingsOpen} />
      </div>
    </div>
  )
}
