"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Play, Square } from "lucide-react"
import { apiUrl } from "@/lib/api"

interface ServiceInfo {
  name: string
  status: string
  enabled: boolean
}

export function Services() {
  const [services, setServices] = useState<ServiceInfo[]>([])

  const loadServices = async () => {
    try {
      const res = await fetch(apiUrl("/services"))
      if (res.ok) {
        const data = await res.json()
        setServices(data.services || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    loadServices()
  }, [])

  const toggleService = async (name: string, running: boolean) => {
    try {
      const res = await fetch(apiUrl(`/services/${name}/${running ? "stop" : "start"}`), { method: "POST" })
      if (res.ok) {
        setServices((prev) => prev.map((s) => (s.name === name ? { ...s, status: running ? "stopped" : "running" } : s)))
      }
    } catch (e) {
      console.error(e)
    }
  }

  const toggleEnabled = async (name: string, enabled: boolean) => {
    try {
      const res = await fetch(apiUrl(`/services/${name}/${enabled ? "disable" : "enable"}`), { method: "POST" })
      if (res.ok) {
        setServices((prev) => prev.map((s) => (s.name === name ? { ...s, enabled: !enabled } : s)))
      }
    } catch (e) {
      console.error(e)
    }
  }

  const badgeVariant = (status: string) => (status === "running" ? "default" : status === "not found" ? "destructive" : "secondary")

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Services</h2>
      </div>
      <div className="grid gap-4">
        {services.map((service) => (
          <Card key={service.name}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  {service.name}
                  <Badge variant={badgeVariant(service.status)}>
                    {service.status === "running" ? "Running" : service.status === "not found" ? "Not found" : "Stopped"}
                  </Badge>
                </CardTitle>
                <div className="flex items-center space-x-2">
                  <Switch checked={service.enabled} onCheckedChange={() => toggleEnabled(service.name, service.enabled)} />
                  <Button variant="outline" size="icon" onClick={() => toggleService(service.name, service.status === "running")}>
                    {service.status === "running" ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent />
          </Card>
        ))}
      </div>
    </div>
  )
}
