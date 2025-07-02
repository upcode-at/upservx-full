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
import { Play, Square, Pause, Settings, Plus, Terminal, Container } from "lucide-react"
import { TerminalEmulator } from "@/components/terminal-emulator"

export function Containers() {
  const [containers] = useState([
    {
      id: 1,
      name: "nginx-web",
      type: "Docker",
      status: "running",
      image: "nginx:latest",
      ports: ["80:8080", "443:8443"],
      cpu: 0.5,
      memory: 128,
      created: "2024-01-15",
    },
    {
      id: 2,
      name: "mysql-db",
      type: "Docker",
      status: "running",
      image: "mysql:8.0",
      ports: ["3306:3306"],
      cpu: 1.2,
      memory: 512,
      created: "2024-01-14",
    },
    {
      id: 3,
      name: "ubuntu-lxc",
      type: "LXC",
      status: "stopped",
      image: "ubuntu:22.04",
      ports: [],
      cpu: 0,
      memory: 256,
      created: "2024-01-10",
    },
    {
      id: 4,
      name: "webapp-pod",
      type: "Kubernetes",
      status: "running",
      image: "webapp:v1.2",
      ports: ["8080:80"],
      cpu: 0.8,
      memory: 256,
      created: "2024-01-12",
    },
  ])

  const [activeTerminal, setActiveTerminal] = useState<string | null>(null)

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

  const getTypeColor = (type: string) => {
    switch (type) {
      case "Docker":
        return "blue"
      case "LXC":
        return "green"
      case "Kubernetes":
        return "purple"
      case "Pod":
        return "orange"
      default:
        return "gray"
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Container</h2>
          <p className="text-muted-foreground">Verwalten Sie Docker, LXC, Pods und Kubernetes Container</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Neuen Container erstellen
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Neuen Container erstellen</DialogTitle>
              <DialogDescription>Konfigurieren Sie Ihren neuen Container</DialogDescription>
            </DialogHeader>
            <Tabs defaultValue="basic" className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="basic">Grundlagen</TabsTrigger>
                <TabsTrigger value="resources">Ressourcen</TabsTrigger>
                <TabsTrigger value="network">Netzwerk</TabsTrigger>
                <TabsTrigger value="volumes">Volumes</TabsTrigger>
              </TabsList>
              <TabsContent value="basic" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="container-name">Container Name</Label>
                    <Input id="container-name" placeholder="z.B. my-webapp" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="container-type">Container Typ</Label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="Typ auswählen" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="docker">Docker</SelectItem>
                        <SelectItem value="lxc">LXC</SelectItem>
                        <SelectItem value="kubernetes">Kubernetes Pod</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="container-image">Image</Label>
                  <Input id="container-image" placeholder="z.B. nginx:latest" />
                </div>
              </TabsContent>
              <TabsContent value="resources" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="container-cpu">CPU Limit</Label>
                    <Input id="container-cpu" placeholder="z.B. 1.0" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="container-memory">Memory Limit (MB)</Label>
                    <Input id="container-memory" placeholder="z.B. 512" />
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="network" className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="container-ports">Port Mapping</Label>
                  <Input id="container-ports" placeholder="z.B. 8080:80" />
                </div>
              </TabsContent>
              <TabsContent value="volumes" className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="container-volumes">Volume Mounts</Label>
                  <Input id="container-volumes" placeholder="z.B. /host/path:/container/path" />
                </div>
              </TabsContent>
            </Tabs>
            <div className="flex justify-end space-x-2">
              <Button variant="outline">Abbrechen</Button>
              <Button>Container erstellen</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-4">
        {containers.map((container) => (
          <Card key={container.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Container className="h-5 w-5" />
                    {container.name}
                    <Badge variant={getStatusColor(container.status)}>
                      {container.status === "running" ? "Läuft" : "Gestoppt"}
                    </Badge>
                    <Badge variant="outline">{container.type}</Badge>
                  </CardTitle>
                  <CardDescription>{container.image}</CardDescription>
                </div>
                <div className="flex space-x-2">
                  <Button variant="outline" size="icon" onClick={() => setActiveTerminal(container.name)}>
                    <Terminal className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon">
                    <Settings className="h-4 w-4" />
                  </Button>
                  {container.status === "running" ? (
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
                  <div className="font-medium">{container.cpu} Kerne</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Memory:</span>
                  <div className="font-medium">{container.memory} MB</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Ports:</span>
                  <div className="font-medium">{container.ports.length > 0 ? container.ports.join(", ") : "Keine"}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Erstellt:</span>
                  <div className="font-medium">{container.created}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      {activeTerminal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <TerminalEmulator containerName={activeTerminal} onClose={() => setActiveTerminal(null)} />
        </div>
      )}
    </div>
  )
}
