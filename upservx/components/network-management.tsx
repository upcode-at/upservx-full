"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Network, Wifi, Settings } from "lucide-react"

interface NetworkInterface {
  name: string
  type: string
  status: string
  ip: string
  netmask: string
  gateway: string
  mac: string
  speed: string
  rx: string
  tx: string
}

interface NetworkSettings {
  dns_primary: string
  dns_secondary: string
}

export function NetworkManagement() {
  const [networkInterfaces, setNetworkInterfaces] = useState<NetworkInterface[]>([])
  const [networkSettings, setNetworkSettings] = useState<NetworkSettings>({
    dns_primary: "8.8.8.8",
    dns_secondary: "8.8.4.4",

  })
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    const loadInterfaces = async () => {
      try {
        const res = await fetch("http://localhost:8000/network/interfaces")
        if (res.ok) {
          const data = await res.json()
          setNetworkInterfaces(data.interfaces || [])
        }
      } catch (e) {
        console.error(e)
      }
    }
    loadInterfaces()

    const loadSettings = async () => {
      try {
        const res = await fetch("http://localhost:8000/network/settings")
        if (res.ok) {
          const data = await res.json()
          setNetworkSettings(data)
        }
      } catch (e) {
        console.error(e)
      }
    }
    loadSettings()
  }, [])

  useEffect(() => {
    if (!message) return
    const t = setTimeout(() => setMessage(null), 3000)
    return () => clearTimeout(t)
  }, [message])


  const getStatusColor = (status: string) => {
    switch (status) {
      case "up":
      case "connected":
        return "default"
      case "down":
      case "disconnected":
        return "secondary"
      default:
        return "outline"
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Network Management</h2>
        <p className="text-muted-foreground">Manage network interfaces</p>
      </div>

      <Tabs defaultValue="interfaces" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="interfaces">Network Interfaces</TabsTrigger>
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
        </TabsList>

        <TabsContent value="interfaces" className="space-y-4">
          <div className="grid gap-4">
            {networkInterfaces.map((iface) => (
              <Card key={iface.name}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        {iface.type === "WiFi" ? <Wifi className="h-5 w-5" /> : <Network className="h-5 w-5" />}
                        {iface.name}
                        <Badge variant={getStatusColor(iface.status)}>
                          {iface.status === "up" ? "Active" : "Inactive"}
                        </Badge>
                        <Badge variant="outline">{iface.type}</Badge>
                      </CardTitle>
                      <CardDescription>MAC: {iface.mac}</CardDescription>
                    </div>
                    <Button variant="outline" size="icon">
                      <Settings className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">IP Address:</span>
                      <div className="font-medium">{iface.ip}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Netmask:</span>
                      <div className="font-medium">{iface.netmask}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Gateway:</span>
                      <div className="font-medium">{iface.gateway}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Speed:</span>
                      <div className="font-medium">{iface.speed}</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm mt-4">
                    <div>
                      <span className="text-muted-foreground">Received:</span>
                      <div className="font-medium">{iface.rx}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Sent:</span>
                      <div className="font-medium">{iface.tx}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>


        <TabsContent value="configuration" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Network Configuration</CardTitle>
              <CardDescription>Global network settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="dns-primary">Primary DNS</Label>
                  <Input
                    id="dns-primary"
                    value={networkSettings.dns_primary}
                    onChange={(e) =>
                      setNetworkSettings({ ...networkSettings, dns_primary: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dns-secondary">Secondary DNS</Label>
                  <Input
                    id="dns-secondary"
                    value={networkSettings.dns_secondary}
                    onChange={(e) =>
                      setNetworkSettings({ ...networkSettings, dns_secondary: e.target.value })
                    }
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <Button
                  onClick={async () => {
                    try {
                      const res = await fetch("http://localhost:8000/network/settings", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(networkSettings),
                      })
                      if (res.ok) setMessage("Saved")
                    } catch (e) {
                      console.error(e)
                    }
                  }}
                >
                  Save configuration
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      {message && (
        <div className="fixed top-4 right-4 z-50 bg-green-600 text-white px-3 py-2 rounded shadow">
          {message}
        </div>
      )}
    </div>
  )
}
