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
import {
  Play,
  Square,
  Settings,
  Plus,
  Terminal,
  Container,
  Trash2,
  LayoutGrid,
  List as ListIcon,
} from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
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
  const [cpu, setCpu] = useState(1)
  const [memory, setMemory] = useState(512)
  const [maxCpu, setMaxCpu] = useState(16)
  const [maxMemory, setMaxMemory] = useState(16384)
  const [ports, setPorts] = useState<{ host: string; container: string }[]>([
    { host: "", container: "" },
  ])
  const [mounts, setMounts] = useState<{ host: string; container: string }[]>([
    { host: "", container: "" },
  ])
  const [envs, setEnvs] = useState<{ name: string; value: string }[]>([
    { name: "", value: "" },
  ])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [activeTerminal, setActiveTerminal] = useState<string | null>(null)
  const [filter, setFilter] = useState("")
  const [open, setOpen] = useState(false)
  const [view, setView] = useState<"grid" | "list">("grid")

  const loadMetrics = async () => {
    try {
      const res = await fetch("http://localhost:8000/metrics")
      if (res.ok) {
        const data = await res.json()
        if (data.cpu?.cores) setMaxCpu(data.cpu.cores)
        if (data.memory?.total)
          setMaxMemory(Math.round(data.memory.total * 1024))
      }
    } catch (e) {
      console.error(e)
    }
  }

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
    loadMetrics()
  }, [])

  useEffect(() => {
    if (open) {
      loadMetrics()
    }
  }, [open])

  useEffect(() => {
    if (cpu > maxCpu) setCpu(maxCpu)
  }, [maxCpu])

  useEffect(() => {
    if (memory > maxMemory) setMemory(maxMemory)
  }, [maxMemory])

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
      cpu,
      memory,
      ports: ports
        .filter((p) => p.host.trim() && p.container.trim())
        .map((p) => `${p.host}:${p.container}`),
      mounts: mounts
        .filter((m) => m.host.trim() && m.container.trim())
        .map((m) => `${m.host}:${m.container}`),
      envs: envs
        .filter((e) => e.name.trim() && e.value.trim())
        .map((e) => `${e.name}=${e.value}`),
    }
    const creating = name
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
        setMessage(`Container ${creating} erstellt`)
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
        setMessage(`Container ${name} gelöscht`)
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
          <div className="flex gap-1">
            <Button
              variant={view === "grid" ? "secondary" : "outline"}
              size="icon"
              onClick={() => setView("grid")}
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
            <Button
              variant={view === "list" ? "secondary" : "outline"}
              size="icon"
              onClick={() => setView("list")}
            >
              <ListIcon className="h-4 w-4" />
            </Button>
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
                    <Label htmlFor="container-cpu">CPU Kerne: {cpu}</Label>
                    <input
                      id="container-cpu"
                      type="range"
                      min={1}
                      max={maxCpu}
                      step={1}
                      className="w-full"
                      value={cpu}
                      onChange={(e) => setCpu(parseInt(e.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="container-memory">RAM (MB): {memory}</Label>
                    <input
                      id="container-memory"
                      type="range"
                      min={256}
                      max={maxMemory}
                      step={256}
                      className="w-full"
                      value={memory}
                      onChange={(e) => setMemory(parseInt(e.target.value))}
                    />
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="network" className="space-y-4">
                <Label>Port Mapping</Label>
                {ports.map((p, idx) => (
                  <div key={idx} className="flex space-x-2">
                    <Input
                      type="number"
                      value={p.host}
                      onChange={(e) => {
                        const arr = [...ports]
                        arr[idx].host = e.target.value
                        setPorts(arr)
                      }}
                      placeholder="Host"
                    />
                    <Input
                      type="number"
                      value={p.container}
                      onChange={(e) => {
                        const arr = [...ports]
                        arr[idx].container = e.target.value
                        setPorts(arr)
                      }}
                      placeholder="Container"
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
                  onClick={() => setPorts([...ports, { host: "", container: "" }])}
                >
                  Port hinzufügen
                </Button>
              </TabsContent>
              <TabsContent value="volumes" className="space-y-4">
                <Label>Volume Mounts</Label>
                {mounts.map((m, idx) => (
                  <div key={idx} className="flex space-x-2">
                    <Input
                      value={m.host}
                      onChange={(e) => {
                        const arr = [...mounts]
                        arr[idx].host = e.target.value
                        setMounts(arr)
                      }}
                      placeholder="Host Pfad"
                    />
                    <Input
                      value={m.container}
                      onChange={(e) => {
                        const arr = [...mounts]
                        arr[idx].container = e.target.value
                        setMounts(arr)
                      }}
                      placeholder="Container Pfad"
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
                  onClick={() => setMounts([...mounts, { host: "", container: "" }])}
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

      {view === "grid" ? (
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {containers
            .filter((c) => !filter || c.type.toLowerCase() === filter.toLowerCase())
            .map((container) => (
              <Card key={container.id} className="aspect-square rounded-lg">
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
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Typ</TableHead>
                  <TableHead>Image</TableHead>
                  <TableHead>CPU</TableHead>
                  <TableHead>Memory</TableHead>
                  <TableHead>Ports</TableHead>
                  <TableHead>Erstellt</TableHead>
                  <TableHead>Aktionen</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {containers
                  .filter((c) => !filter || c.type.toLowerCase() === filter.toLowerCase())
                  .map((container) => (
                    <TableRow key={container.id}>
                      <TableCell className="font-medium flex items-center gap-2">
                        <Container className="h-4 w-4" /> {container.name}
                      </TableCell>
                      <TableCell>
                        <Badge className={statusClass(container.status)}>
                          {container.status === "running" ? "Läuft" : "Gestoppt"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{container.type}</Badge>
                      </TableCell>
                      <TableCell className="text-xs">{container.image}</TableCell>
                      <TableCell>{container.cpu}</TableCell>
                      <TableCell>{container.memory}</TableCell>
                      <TableCell className="text-xs">
                        {container.ports.length > 0 ? container.ports.join(", ") : "Keine"}
                      </TableCell>
                      <TableCell className="text-xs">{container.created}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
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
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      {activeTerminal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <TerminalEmulator containerName={activeTerminal} onClose={() => setActiveTerminal(null)} />
        </div>
      )}
    </div>
  )
}
