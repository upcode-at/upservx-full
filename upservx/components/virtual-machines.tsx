"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Play, Square, Pause, Settings, Plus, Monitor, Terminal } from "lucide-react"
import { RDPClient } from "@/components/rdp-client"

export function VirtualMachines() {
  const [vms] = useState([
    {
      id: 1,
      name: "Ubuntu-Server-01",
      status: "running",
      os: "Ubuntu 22.04 LTS",
      cpu: 4,
      memory: 8192,
      storage: 100,
      ip: "192.168.1.100",
    },
    {
      id: 2,
      name: "Windows-Dev",
      status: "stopped",
      os: "Windows Server 2022",
      cpu: 8,
      memory: 16384,
      storage: 250,
      ip: "192.168.1.101",
    },
    {
      id: 3,
      name: "CentOS-Web",
      status: "running",
      os: "CentOS 8",
      cpu: 2,
      memory: 4096,
      storage: 50,
      ip: "192.168.1.102",
    },
  ])

  const [activeRDP, setActiveRDP] = useState<{ name: string; ip: string } | null>(null)

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "default"
      case "stopped":
        return "secondary"
      case "paused":
        return "outline"
      default:
        return "secondary"
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case "running":
        return "Läuft"
      case "stopped":
        return "Gestoppt"
      case "paused":
        return "Pausiert"
      default:
        return status
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Virtual Machines</h2>
          <p className="text-muted-foreground">Verwalten Sie Ihre virtuellen Maschinen</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Neue VM erstellen
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Neue Virtual Machine erstellen</DialogTitle>
              <DialogDescription>Konfigurieren Sie Ihre neue virtuelle Maschine</DialogDescription>
            </DialogHeader>
            <Tabs defaultValue="basic" className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="basic">Grundlagen</TabsTrigger>
                <TabsTrigger value="hardware">Hardware</TabsTrigger>
                <TabsTrigger value="network">Netzwerk</TabsTrigger>
                <TabsTrigger value="storage">Speicher</TabsTrigger>
              </TabsList>
              <TabsContent value="basic" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="vm-name">VM Name</Label>
                    <Input id="vm-name" placeholder="z.B. Ubuntu-Server-02" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="vm-os">Betriebssystem</Label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="OS auswählen" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ubuntu">Ubuntu 22.04 LTS</SelectItem>
                        <SelectItem value="centos">CentOS 8</SelectItem>
                        <SelectItem value="debian">Debian 11</SelectItem>
                        <SelectItem value="windows">Windows Server 2022</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="hardware" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="vm-cpu">CPU Kerne</Label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="Kerne auswählen" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">1 Kern</SelectItem>
                        <SelectItem value="2">2 Kerne</SelectItem>
                        <SelectItem value="4">4 Kerne</SelectItem>
                        <SelectItem value="8">8 Kerne</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="vm-memory">RAM (MB)</Label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="RAM auswählen" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="2048">2 GB</SelectItem>
                        <SelectItem value="4096">4 GB</SelectItem>
                        <SelectItem value="8192">8 GB</SelectItem>
                        <SelectItem value="16384">16 GB</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="network" className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="vm-network">Netzwerk Modus</Label>
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Netzwerk auswählen" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="bridge">Bridge</SelectItem>
                      <SelectItem value="nat">NAT</SelectItem>
                      <SelectItem value="host">Host-only</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </TabsContent>
              <TabsContent value="storage" className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="vm-storage">Festplattengröße (GB)</Label>
                  <Input id="vm-storage" type="number" placeholder="50" />
                </div>
              </TabsContent>
            </Tabs>
            <div className="flex justify-end space-x-2">
              <Button variant="outline">Abbrechen</Button>
              <Button>VM erstellen</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-4">
        {vms.map((vm) => (
          <Card key={vm.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    {vm.name}
                    <Badge variant={getStatusColor(vm.status)}>{getStatusText(vm.status)}</Badge>
                  </CardTitle>
                  <CardDescription>{vm.os}</CardDescription>
                </div>
                <div className="flex space-x-2">
                  <Button variant="outline" size="icon" onClick={() => setActiveRDP({ name: vm.name, ip: vm.ip })}>
                    <Monitor className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon">
                    <Terminal className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon">
                    <Settings className="h-4 w-4" />
                  </Button>
                  {vm.status === "running" ? (
                    <>
                      <Button variant="outline" size="icon">
                        <Pause className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="icon">
                        <Square className="h-4 w-4" />
                      </Button>
                    </>
                  ) : (
                    <Button variant="outline" size="icon">
                      <Play className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">CPU:</span>
                  <div className="font-medium">{vm.cpu} Kerne</div>
                </div>
                <div>
                  <span className="text-muted-foreground">RAM:</span>
                  <div className="font-medium">{vm.memory / 1024} GB</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Speicher:</span>
                  <div className="font-medium">{vm.storage} GB</div>
                </div>
                <div>
                  <span className="text-muted-foreground">IP:</span>
                  <div className="font-medium">{vm.ip}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      {activeRDP && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <RDPClient vmName={activeRDP.name} vmIP={activeRDP.ip} onClose={() => setActiveRDP(null)} />
        </div>
      )}
    </div>
  )
}
