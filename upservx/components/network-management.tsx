"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
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
  bridge_subnet: string
  docker_subnet: string
}

export function NetworkManagement() {
  const [networkInterfaces, setNetworkInterfaces] = useState<NetworkInterface[]>([])
  const [networkSettings, setNetworkSettings] = useState<NetworkSettings>({
    dns_primary: "8.8.8.8",
    dns_secondary: "8.8.4.4",
    bridge_subnet: "192.168.100.0/24",
    docker_subnet: "172.17.0.0/16",
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

  const [vmNetworks] = useState([
    {
      name: "Ubuntu-Server-01",
      type: "VM",
      interface: "veth0",
      ip: "192.168.100.10",
      mac: "52:54:00:12:34:56",
      bridge: "br0",
      status: "connected",
      bandwidth: "125 Mbps",
    },
    {
      name: "Windows-Dev",
      type: "VM",
      interface: "veth1",
      ip: "192.168.100.11",
      mac: "52:54:00:12:34:57",
      bridge: "br0",
      status: "disconnected",
      bandwidth: "0 Mbps",
    },
    {
      name: "nginx-web",
      type: "Container",
      interface: "docker0",
      ip: "172.17.0.2",
      mac: "02:42:ac:11:00:02",
      bridge: "docker0",
      status: "connected",
      bandwidth: "89 Mbps",
    },
    {
      name: "mysql-db",
      type: "Container",
      interface: "docker0",
      ip: "172.17.0.3",
      mac: "02:42:ac:11:00:03",
      bridge: "docker0",
      status: "connected",
      bandwidth: "45 Mbps",
    },
  ])

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
        <h2 className="text-3xl font-bold tracking-tight">Netzwerk Management</h2>
        <p className="text-muted-foreground">Netzwerkschnittstellen und VM/Container-Verbindungen verwalten</p>
      </div>

      <Tabs defaultValue="interfaces" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="interfaces">Netzwerkschnittstellen</TabsTrigger>
          <TabsTrigger value="vm-networks">VM/Container Netzwerke</TabsTrigger>
          <TabsTrigger value="configuration">Konfiguration</TabsTrigger>
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
                          {iface.status === "up" ? "Aktiv" : "Inaktiv"}
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
                      <span className="text-muted-foreground">IP-Adresse:</span>
                      <div className="font-medium">{iface.ip}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Netzmaske:</span>
                      <div className="font-medium">{iface.netmask}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Gateway:</span>
                      <div className="font-medium">{iface.gateway}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Geschwindigkeit:</span>
                      <div className="font-medium">{iface.speed}</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm mt-4">
                    <div>
                      <span className="text-muted-foreground">Empfangen:</span>
                      <div className="font-medium">{iface.rx}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Gesendet:</span>
                      <div className="font-medium">{iface.tx}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="vm-networks" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>VM und Container Netzwerke</CardTitle>
              <CardDescription>Netzwerkverbindungen von virtuellen Maschinen und Containern</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Typ</TableHead>
                    <TableHead>IP-Adresse</TableHead>
                    <TableHead>MAC-Adresse</TableHead>
                    <TableHead>Bridge</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Bandbreite</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {vmNetworks.map((network) => (
                    <TableRow key={network.name}>
                      <TableCell className="font-medium">{network.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{network.type}</Badge>
                      </TableCell>
                      <TableCell>{network.ip}</TableCell>
                      <TableCell className="font-mono text-xs">{network.mac}</TableCell>
                      <TableCell>{network.bridge}</TableCell>
                      <TableCell>
                        <Badge variant={getStatusColor(network.status)}>
                          {network.status === "connected" ? "Verbunden" : "Getrennt"}
                        </Badge>
                      </TableCell>
                      <TableCell>{network.bandwidth}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="configuration" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Netzwerk Konfiguration</CardTitle>
              <CardDescription>Globale Netzwerkeinstellungen</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="dns-primary">Primärer DNS</Label>
                  <Input
                    id="dns-primary"
                    value={networkSettings.dns_primary}
                    onChange={(e) =>
                      setNetworkSettings({ ...networkSettings, dns_primary: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dns-secondary">Sekundärer DNS</Label>
                  <Input
                    id="dns-secondary"
                    value={networkSettings.dns_secondary}
                    onChange={(e) =>
                      setNetworkSettings({ ...networkSettings, dns_secondary: e.target.value })
                    }
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="bridge-subnet">Bridge Subnet</Label>
                  <Input
                    id="bridge-subnet"
                    value={networkSettings.bridge_subnet}
                    onChange={(e) =>
                      setNetworkSettings({ ...networkSettings, bridge_subnet: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="docker-subnet">Docker Subnet</Label>
                  <Input
                    id="docker-subnet"
                    value={networkSettings.docker_subnet}
                    onChange={(e) =>
                      setNetworkSettings({ ...networkSettings, docker_subnet: e.target.value })
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
                      if (res.ok) setMessage("Gespeichert")
                    } catch (e) {
                      console.error(e)
                    }
                  }}
                >
                  Konfiguration speichern
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
