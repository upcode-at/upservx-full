"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Play, Square, Settings, RefreshCw } from "lucide-react"

export function Services() {
  const [services, setServices] = useState([
    {
      id: 1,
      name: "Apache HTTP Server",
      status: "running",
      autostart: true,
      port: 80,
      description: "Web Server für statische Inhalte",
      uptime: "5 Tage, 12 Stunden",
    },
    {
      id: 2,
      name: "MySQL Database",
      status: "running",
      autostart: true,
      port: 3306,
      description: "Relationale Datenbank",
      uptime: "15 Tage, 7 Stunden",
    },
    {
      id: 3,
      name: "Redis Cache",
      status: "stopped",
      autostart: false,
      port: 6379,
      description: "In-Memory Datenbank für Caching",
      uptime: "0 Minuten",
    },
    {
      id: 4,
      name: "Nginx Proxy",
      status: "running",
      autostart: true,
      port: 443,
      description: "Reverse Proxy und Load Balancer",
      uptime: "2 Tage, 18 Stunden",
    },
    {
      id: 5,
      name: "Docker Daemon",
      status: "running",
      autostart: true,
      port: 2376,
      description: "Container Runtime",
      uptime: "15 Tage, 7 Stunden",
    },
  ])

  const toggleService = (id: number) => {
    setServices(
      services.map((service) =>
        service.id === id ? { ...service, status: service.status === "running" ? "stopped" : "running" } : service,
      ),
    )
  }

  const toggleAutostart = (id: number) => {
    setServices(
      services.map((service) => (service.id === id ? { ...service, autostart: !service.autostart } : service)),
    )
  }

  const getStatusColor = (status: string) => {
    return status === "running" ? "default" : "secondary"
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Services</h2>
        <p className="text-muted-foreground">Verwalten Sie Systemdienste und Anwendungen</p>
      </div>

      <div className="grid gap-4">
        {services.map((service) => (
          <Card key={service.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    {service.name}
                    <Badge variant={getStatusColor(service.status)}>
                      {service.status === "running" ? "Läuft" : "Gestoppt"}
                    </Badge>
                  </CardTitle>
                  <CardDescription>{service.description}</CardDescription>
                </div>
                <div className="flex items-center space-x-2">
                  <Button variant="outline" size="icon">
                    <Settings className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon">
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon" onClick={() => toggleService(service.id)}>
                    {service.status === "running" ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Port:</span>
                  <div className="font-medium">{service.port}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Uptime:</span>
                  <div className="font-medium">{service.uptime}</div>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-muted-foreground">Autostart:</span>
                  <Switch checked={service.autostart} onCheckedChange={() => toggleAutostart(service.id)} />
                </div>
                <div>
                  <span className="text-muted-foreground">PID:</span>
                  <div className="font-medium">
                    {service.status === "running" ? Math.floor(Math.random() * 10000) + 1000 : "-"}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
