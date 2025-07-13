"use client"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Server,
  Container,
  Settings,
  BarChart3,
  HardDrive,
  Network,
  Shield,
  Users,
  Disc,
} from "lucide-react"
import { useEffect, useState } from "react"
import { apiUrl } from "@/lib/api"

interface SidebarProps {
  activeSection: string
  onSectionChange: (section: string) => void
}

export function Sidebar({ activeSection, onSectionChange }: SidebarProps) {
  const [hostname, setHostname] = useState("")

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

  const menuItems = [
    { id: "dashboard", label: "Dashboard", icon: BarChart3 },
    { id: "vms", label: "Virtual Machines", icon: Server },
    { id: "containers", label: "Container", icon: Container },
    { id: "images", label: "Images & ISOs", icon: Disc },
    { id: "network", label: "Network", icon: Network },
    { id: "storage", label: "Storage", icon: HardDrive },
    { id: "users", label: "Users", icon: Users },
    { id: "backup", label: "Backup", icon: Shield },
    { id: "settings", label: "Settings", icon: Settings },
  ]

  return (
    <div className="w-64 bg-card border-r border-border flex flex-col">
      <div className="p-6 border-b border-border">
        <h1 className="text-xl font-bold">UpServX</h1>
        <p className="text-sm text-muted-foreground">{hostname}</p>
      </div>
      <nav className="flex-1 p-4 space-y-2">
        {menuItems.map((item) => {
          const Icon = item.icon
          return (
            <Button
              key={item.id}
              variant={activeSection === item.id ? "secondary" : "ghost"}
              className={cn("w-full justify-start", activeSection === item.id && "bg-secondary")}
              onClick={() => onSectionChange(item.id)}
            >
              <Icon className="mr-2 h-4 w-4" />
              {item.label}
            </Button>
          )
        })}
      </nav>
    </div>
  )
}
