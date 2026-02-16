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
} from "lucide-react"
import { useEffect, useState } from "react"
import { apiUrl } from "@/lib/api"
import { useTheme } from "next-themes"

interface SidebarProps {
  activeSection: string
  onSectionChange: (section: string) => void
}

export function Sidebar({ activeSection, onSectionChange }: SidebarProps) {
  const [hostname, setHostname] = useState("")
  const { theme } = useTheme()
  const [storageExpanded, setStorageExpanded] = useState(false)

  useEffect(() => {
    const loadHostname = async () => {
      try {
        const res = await fetch(apiUrl("/settings"))
        if (res.ok) {
          const data = await res.json()
          setHostname(data.hostname)
        }
      } catch (err) {
        console.error(err)
      }
    }
    loadHostname()
  }, [])

  const categories = [
    {
      title: "System",
      items: [
        { id: "dashboard", label: "Dashboard", icon: BarChart3 },
        { id: "shell", label: "Shell", icon: Terminal },
        { id: "cluster", label: "Cluster", icon: GitBranch },
      ],
    },
    {
      title: "Compute",
      items: [
        { id: "vms", label: "Virtual Machines", icon: Server },
        { id: "containers", label: "Container", icon: Container },
        { id: "compose", label: "Compose Builder", icon: FileText },
      ],
    },
    {
      title: "Resources",
      items: [
        { id: "images", label: "Images & ISOs", icon: Disc },
        {
          id: "storage",
          label: "Storage",
          icon: HardDrive,
          subItems: [
            { id: "storage", label: "Physical Storage" },
            { id: "container-storage", label: "Container Storage" },
          ]
        },
      ],
    },
    {
      title: "Administration",
      items: [
        { id: "app-store", label: "App Store", icon: Store },
        { id: "settings", label: "Settings", icon: Settings },
        { id: "users", label: "Users", icon: Users },
        { id: "backup", label: "Backup", icon: Shield },
        { id: "network", label: "Network", icon: Network },
        { id: "firewall", label: "Firewall", icon: Shield },
        { id: "logs", label: "Logs", icon: FileText },
      ],
    },
  ]

  return (
    <div className="w-64 upservx-sidebar flex flex-col">
      <div className="p-6 border-b border-sidebar-border/30">
        <div className="flex items-center space-x-3 mb-2">
          <img 
            src={theme === "dark" ? "/logo_light.png" : "/logo.png"} 
            alt="UpServX Logo" 
            className="h-16 w-auto object-contain" 
          />
        </div>
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <p className="text-sm text-muted-foreground font-medium">{hostname || "Local Server"}</p>
          </div>
          <p className="text-xs text-muted-foreground/60 font-mono pl-4">v0.1.0</p>
        </div>
      </div>
      <nav className="flex-1 p-4 space-y-6">
        {categories.map((category) => (
          <div key={category.title} className="space-y-3">
            <div className="px-3 text-xs font-bold text-muted-foreground uppercase tracking-wide">
              {category.title}
            </div>
            <div className="space-y-1">
              {category.items.map((item) => {
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
                      {!hasSubItems && isActive && (
                        <div className="ml-auto w-2 h-2 bg-white rounded-full"></div>
                      )}
                    </Button>
                    {hasSubItems && isExpanded && (
                      <div className="ml-6 space-y-1 mt-1">
                        {item.subItems.map((subItem) => {
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
                              {subIsActive && (
                                <div className="ml-auto w-2 h-2 bg-white rounded-full"></div>
                              )}
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
        ))}
      </nav>
    </div>
  )
}
