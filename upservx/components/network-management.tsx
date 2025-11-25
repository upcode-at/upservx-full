"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Network, Wifi, Settings } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog"
import { Switch } from "@/components/ui/switch"
import { apiUrl } from "@/lib/api"

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
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedIface, setSelectedIface] = useState<NetworkInterface | null>(null)
  const [ifaceConfig, setIfaceConfig] = useState({ method: "dhcp", ip: "", netmask: "", gateway: "", enabled: true })

  const fetchInterfaces = async () => {
    try {
      const res = await fetch(apiUrl("/network/interfaces"))
      if (res.ok) {
        const data = await res.json()
        setNetworkInterfaces(data.interfaces || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const fetchSettings = async () => {
    try {
      const res = await fetch(apiUrl("/network/settings"))
      if (res.ok) {
        const data = await res.json()
        setNetworkSettings(data)
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchInterfaces()
    fetchSettings()
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
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => {
                          setSelectedIface(iface)
                          setIfaceConfig({
                            method: iface.ip && iface.ip !== "-" ? "static" : "dhcp",
                            ip: iface.ip && iface.ip !== "-" ? iface.ip : "",
                            netmask: iface.netmask && iface.netmask !== "-" ? iface.netmask : "",
                            gateway: iface.gateway && iface.gateway !== "-" ? iface.gateway : "",
                            enabled: iface.status === "up",
                          })
                          setDialogOpen(true)
                        }}
                      >
                        <Settings className="h-4 w-4" />
                      </Button>
                    </div>
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
                      const res = await fetch(apiUrl("/network/settings"), {
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
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Configure {selectedIface?.name}</DialogTitle>
            <DialogDescription>Adjust settings for the interface</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 mt-2">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Method</Label>
                <select
                  className="mt-1 block w-full rounded border p-2"
                  value={ifaceConfig.method}
                  onChange={(e) => setIfaceConfig({ ...ifaceConfig, method: e.target.value })}
                >
                  <option value="dhcp">DHCP</option>
                  <option value="static">Static</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <Label>Enabled</Label>
                <div>
                  <Switch
                    checked={ifaceConfig.enabled}
                    onCheckedChange={(v) => setIfaceConfig({ ...ifaceConfig, enabled: v as boolean })}
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div>
                <Label htmlFor="iface-ip">IP Address</Label>
                <Input id="iface-ip" value={ifaceConfig.ip} onChange={(e) => setIfaceConfig({ ...ifaceConfig, ip: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="iface-netmask">Netmask</Label>
                <Input id="iface-netmask" value={ifaceConfig.netmask} onChange={(e) => setIfaceConfig({ ...ifaceConfig, netmask: e.target.value })} />
              </div>
              <div>
                <Label htmlFor="iface-gateway">Gateway</Label>
                <Input id="iface-gateway" value={ifaceConfig.gateway} onChange={(e) => setIfaceConfig({ ...ifaceConfig, gateway: e.target.value })} />
              </div>
            </div>
          </div>

          <DialogFooter>
            <div className="flex w-full justify-end gap-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button
                onClick={async () => {
                  if (!selectedIface) return
                  try {
                    const res = await fetch(apiUrl(`/network/interfaces/${selectedIface.name}`), {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(ifaceConfig),
                    })
                    if (res.ok) {
                      setMessage("Applied")
                      setDialogOpen(false)
                      fetchInterfaces()
                    } else {
                      const txt = await res.text()
                      setMessage("Error: " + txt)
                    }
                  } catch (e) {
                    console.error(e)
                    setMessage("Failed to apply")
                  }
                }}
              >
                Apply
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {message && (
        <div className="fixed top-4 right-4 z-50 bg-green-600 text-white px-3 py-2 rounded shadow">
          {message}
        </div>
      )}
    </div>
  )
}
