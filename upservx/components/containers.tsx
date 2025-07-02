"use client"

import { useState, useEffect } from "react"
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
import { Play, Square, Settings, Plus, Terminal, Container, Trash2 } from "lucide-react"
import { TerminalEmulator } from "@/components/terminal-emulator"

export function Containers() {
  interface ContainerData {
    id: number
    name: string
    type: string
    status: string
    image: string
    ports: string[]
    mounts: string[]
    cpu: number
    memory: number
    created: string
  }

  const [containers, setContainers] = useState<ContainerData[]>([])
  const [name, setName] = useState("")
  const [type, setType] = useState("")
  const [images, setImages] = useState<string[]>([])
  const [image, setImage] = useState("")
  const [cpu, setCpu] = useState("")
  const [memory, setMemory] = useState("")
  const [ports, setPorts] = useState<string[]>([""])
  const [mounts, setMounts] = useState<string[]>([""])
  const [envs, setEnvs] = useState<{ name: string; value: string }[]>([
    { name: "", value: "" },
  ])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [activeTerminal, setActiveTerminal] = useState<string | null>(null)
  const [filter, setFilter] = useState("")
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!type) {
      setImages([])
      setImage("")
      return
    }
    const loadImages = async () => {
      try {
        const res = await fetch(`http://localhost:8000/images?type=${type}`)
        if (res.ok) {
          const data = await res.json()
          setImages(data.images || [])
        }
      } catch (e) {
        console.error(e)
      }
    }
    loadImages()
  }, [type])

  useEffect(() => {
    if (!error) return
    const t = setTimeout(() => setError(null), 3000)
    return () => clearTimeout(t)
  }, [error])

  useEffect(() => {
    if (!message) return
    const t = setTimeout(() => setMessage(null), 3000)
    return () => clearTimeout(t)
  }, [message])

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch("http://localhost:8000/containers")
        if (res.ok) {
          const data = await res.json()
          setContainers(data)
        }
      } catch (e) {
        console.error(e)
      }
    }

    if (!activeTerminal) {
      load()
      const id = setInterval(load, 4000)
      return () => clearInterval(id)
    }
  }, [activeTerminal])

  const handleCreate = async () => {
    const payload = {
      name,
      type,
      image,
      cpu: parseFloat(cpu) || 0,
      memory: parseInt(memory) || 0,
      ports: ports.filter((p) => p.trim() !== ""),
      mounts: mounts.filter((m) => m.trim() !== ""),
      envs: envs
        .filter((e) => e.name.trim() && e.value.trim())
        .map((e) => `${e.name}=${e.value}`),
    }
    try {
      const res = await fetch("http://localhost:8000/containers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      if (res.ok) {
        const c = await res.json()
        if (c.detail) {
          const listRes = await fetch("http://localhost:8000/containers")
          if (listRes.ok) {
            const data = await listRes.json()
            setContainers(data)
          }
        } else {
          setContainers((prev) => [...prev, c])
        }
        setMessage("Container erstellt")
        setOpen(false)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleStart = async (name: string) => {
    try {
      const res = await fetch(`http://localhost:8000/containers/${name}/start`, {
        method: "POST",
      })
      if (res.ok) {
        setContainers((prev) =>
          prev.map((c) => (c.name === name ? { ...c, status: "running" } : c))
        )
        setError(null)
      } else {
        let message = "Fehler beim Starten"
        try {
          const data = await res.json()
          message = data.detail || message
        } catch {
          message = await res.text()
        }
        setError(message)
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
    }
  }

  const handleStop = async (name: string) => {
    try {
      const res = await fetch(`http://localhost:8000/containers/${name}/stop`, {
        method: "POST",
      })
      if (res.ok) {
        setContainers((prev) =>
          prev.map((c) => (c.name === name ? { ...c, status: "stopped" } : c))
        )
        setError(null)
      } else {
        let message = "Fehler beim Stoppen"
        try {
          const data = await res.json()
          message = data.detail || message
        } catch {
          message = await res.text()
        }
        setError(message)
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
    }
  }

  const handleDelete = async (name: string) => {
    try {
      const res = await fetch(`http://localhost:8000/containers/${name}`, {
        method: "DELETE",
      })
      if (res.ok) {
        setContainers((prev) => prev.filter((c) => c.name !== name))
        setError(null)
      } else {
        let message = "Fehler beim Löschen"
        try {
          const data = await res.json()
          message = data.detail || message
        } catch {
          message = await res.text()
        }
        setError(message)
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
    }
  }

  const statusClass = (status: string) =>
    status === "running" ? "bg-green-600 text-white" : "bg-red-600 text-white"


  return (
    <div className="space-y-6">
      {error && (
        <div className="fixed top-4 right-4 z-50 bg-red-600 text-white px-3 py-2 rounded shadow">
          {error}
        </div>
      )}
      {message && (
        <div className="fixed top-4 right-4 z-50 bg-green-600 text-white px-3 py-2 rounded shadow">
          {message}
        </div>
      )}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Container</h2>
          <p className="text-muted-foreground">Verwalten Sie Docker, LXC, Pods und Kubernetes Container</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-48">
            <Select
              value={filter}
              onValueChange={(value) => setFilter(value === "all" ? "" : value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Alle Typen" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Alle</SelectItem>
                <SelectItem value="Docker">Docker</SelectItem>
                <SelectItem value="LXC">LXC</SelectItem>
                <SelectItem value="Kubernetes">Kubernetes</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button onClick={() => setOpen(true)}>
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
                    <Input
                      id="container-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="z.B. my-webapp"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="container-type">Container Typ</Label>
                    <Select value={type} onValueChange={setType}>
                      <SelectTrigger>
                        <SelectValue placeholder="Typ auswählen" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Docker">Docker</SelectItem>
                        <SelectItem value="LXC">LXC</SelectItem>
                        <SelectItem value="Kubernetes">Kubernetes Pod</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="container-image">Image</Label>
                  <Select value={image} onValueChange={setImage}>
                    <SelectTrigger>
                      <SelectValue placeholder="Image auswählen" />
                    </SelectTrigger>
                    <SelectContent>
                      {images.map((img) => (
                        <SelectItem key={img} value={img}>
                          {img}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {type === "Docker" && (
                  <div className="space-y-2">
                    <Label>Environment Variablen</Label>
                    {envs.map((env, idx) => (
                      <div key={idx} className="flex space-x-2">
                        <Input
                          placeholder="NAME"
                          value={env.name}
                          onChange={(e) => {
                            const arr = [...envs]
                            arr[idx].name = e.target.value
                            setEnvs(arr)
                          }}
                        />
                        <Input
                          placeholder="Wert"
                          value={env.value}
                          onChange={(e) => {
                            const arr = [...envs]
                            arr[idx].value = e.target.value
                            setEnvs(arr)
                          }}
                        />
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => setEnvs(envs.filter((_, i) => i !== idx))}
                        >
                          -
                        </Button>
                      </div>
                    ))}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setEnvs([...envs, { name: "", value: "" }])}
                    >
                      Variable hinzufügen
                    </Button>
                  </div>
                )}
              </TabsContent>
              <TabsContent value="resources" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="container-cpu">CPU Limit</Label>
                    <Input
                      id="container-cpu"
                      value={cpu}
                      onChange={(e) => setCpu(e.target.value)}
                      placeholder="z.B. 1.0"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="container-memory">Memory Limit (MB)</Label>
                    <Input
                      id="container-memory"
                      value={memory}
                      onChange={(e) => setMemory(e.target.value)}
                      placeholder="z.B. 512"
                    />
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="network" className="space-y-4">
                <Label>Port Mapping</Label>
                {ports.map((p, idx) => (
                  <div key={idx} className="flex space-x-2">
                    <Input
                      value={p}
                      onChange={(e) => {
                        const arr = [...ports]
                        arr[idx] = e.target.value
                        setPorts(arr)
                      }}
                      placeholder="8080:80"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setPorts(ports.filter((_, i) => i !== idx))}
                    >
                      -
                    </Button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPorts([...ports, ""])}
                >
                  Port hinzufügen
                </Button>
              </TabsContent>
              <TabsContent value="volumes" className="space-y-4">
                <Label>Volume Mounts</Label>
                {mounts.map((m, idx) => (
                  <div key={idx} className="flex space-x-2">
                    <Input
                      value={m}
                      onChange={(e) => {
                        const arr = [...mounts]
                        arr[idx] = e.target.value
                        setMounts(arr)
                      }}
                      placeholder="/host/path:/container/path"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setMounts(mounts.filter((_, i) => i !== idx))}
                    >
                      -
                    </Button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setMounts([...mounts, ""])}
                >
                  Mount hinzufügen
                </Button>
              </TabsContent>
            </Tabs>
            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Abbrechen
              </Button>
              <Button onClick={handleCreate}>Container erstellen</Button>
            </div>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      <div className="grid gap-4">
        {containers
          .filter((c) => !filter || c.type.toLowerCase() === filter.toLowerCase())
          .map((container) => (
          <Card key={container.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Container className="h-5 w-5" />
                    {container.name}
                    <Badge className={statusClass(container.status)}>
                      {container.status === "running" ? "Läuft" : "Gestoppt"}
                    </Badge>
                    <Badge variant="outline">{container.type}</Badge>
                  </CardTitle>
                  <CardDescription>{container.image}</CardDescription>
                </div>
                <div className="flex space-x-2">
                  {container.status === "running" && (
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setActiveTerminal(container.name)}
                    >
                      <Terminal className="h-4 w-4" />
                    </Button>
                  )}
                  <Button variant="outline" size="icon">
                    <Settings className="h-4 w-4" />
                  </Button>
                  {container.status === "running" ? (
                    <Button
                      variant="destructive"
                      size="icon"
                      onClick={() => handleStop(container.name)}
                    >
                      <Square className="h-4 w-4" />
                    </Button>
                  ) : (
                    <>
                      <Button
                        className="bg-green-600 text-white hover:bg-green-700"
                        size="icon"
                        onClick={() => handleStart(container.name)}
                      >
                        <Play className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="destructive"
                        size="icon"
                        onClick={() => handleDelete(container.name)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </>
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
