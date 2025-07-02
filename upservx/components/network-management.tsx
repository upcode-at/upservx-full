"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Network, Wifi, Settings } from "lucide-react"

export function NetworkManagement() {
  const [networkInterfaces] = useState([
    {
      name: "eth0",
      type: "Ethernet",
      status: "up",
      ip: "192.168.1.10",
      netmask: "255.255.255.0",
      gateway: "192.168.1.1",
      mac: "00:1B:44:11:3A:B7",
      speed: "1000 Mbps",
      rx: "2.5 GB",
      tx: "1.8 GB",
    },
    {
      name: "wlan0",
      type: "WiFi",
      status: "down",
      ip: "-",
      netmask: "-",
      gateway: "-",
      mac: "00:1B:44:11:3A:B8",
      speed: "-",
      rx: "0 B",
      tx: "0 B",
    },
    {
      name: "br0",
      type: "Bridge",
      status: "up",
      ip: "192.168.100.1",
      netmask: "255.255.255.0",
      gateway: "-",
      mac: "00:1B:44:11:3A:B9",
      speed: "1000 Mbps",
      rx: "856 MB",
      tx: "1.2 GB",
    },
  ])

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
                  <Input id="dns-primary" defaultValue="8.8.8.8" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dns-secondary">Sekundärer DNS</Label>
                  <Input id="dns-secondary" defaultValue="8.8.4.4" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="bridge-subnet">Bridge Subnet</Label>
                  <Input id="bridge-subnet" defaultValue="192.168.100.0/24" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="docker-subnet">Docker Subnet</Label>
                  <Input id="docker-subnet" defaultValue="172.17.0.0/16" />
                </div>
              </div>
              <div className="flex justify-end">
                <Button>Konfiguration speichern</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
