"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardFooter, CardTitle } from "@/components/ui/card"
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
  Plus,
  Terminal,
  Container,
  Trash2,
  LayoutGrid,
  List as ListIcon,
  FileText,
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
import { apiUrl } from "@/lib/api"
import { NotificationContainer } from "@/components/ui/notification"

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
  const [success, setSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTerminal, setActiveTerminal] = useState<string | null>(null)
  const [filter, setFilter] = useState("")
  const [open, setOpen] = useState(false)
  const [view, setView] = useState<"grid" | "list">("list")
  const [composeOpen, setComposeOpen] = useState(false)
  const [composeName, setComposeName] = useState("")
  const [composeFile, setComposeFile] = useState<File | null>(null)
  const [composeYaml, setComposeYaml] = useState("")
  const [logsOpen, setLogsOpen] = useState(false)
  const [logsContainer, setLogsContainer] = useState<string | null>(null)
  const [logs, setLogs] = useState("")

  const loadMetrics = async () => {
    try {
      const res = await fetch(apiUrl("/metrics"))
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
        const res = await fetch(apiUrl(`/images?type=${type}`))
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
  }, [maxCpu, cpu])

  useEffect(() => {
    if (memory > maxMemory) setMemory(maxMemory)
  }, [maxMemory, memory])

useEffect(() => {
    const load = async () => {
      try {
        const includeCompose = filter === "Docker-Compose"
        const url = includeCompose ? "/containers?include_compose=true" : "/containers"
        const res = await fetch(apiUrl(url))
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
  }, [activeTerminal, filter])

  const handleCreateComposeFromYaml = async () => {
    if (!composeYaml || !composeName) return
    
    setSuccess(null)
    setError(null)
    
    try {
      // Create a File object from the YAML string
      const blob = new Blob([composeYaml], { type: "text/yaml" })
      const file = new File([blob], "docker-compose.yml", { type: "text/yaml" })
      
      const formData = new FormData()
      formData.append("compose_file", file)
      
      const res = await fetch(apiUrl(`/containers/compose?project_name=${composeName}`), {
        method: "POST",
        body: formData,
      })
      
      if (res.ok) {
        setSuccess(`Docker Compose stack "${composeName}" created`)
        setComposeOpen(false)
        setComposeName("")
        setComposeYaml("")
        
        // Reload containers
        const listRes = await fetch(apiUrl("/containers"))
        if (listRes.ok) {
          const data = await listRes.json()
          setContainers(data)
        }
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to create compose stack")
      }
    } catch (e) {
      console.error(e)
      setError("Failed to create compose stack")
    }
  }

  const handleCreateComposeFromFile = async () => {
    if (!composeFile || !composeName) return
    
    setSuccess(null)
    setError(null)
    
    try {
      const formData = new FormData()
      formData.append("compose_file", composeFile)
      
      const res = await fetch(apiUrl(`/containers/compose?project_name=${composeName}`), {
        method: "POST",
        body: formData,
      })
      
      if (res.ok) {
        setSuccess(`Docker Compose stack "${composeName}" created`)
        setComposeOpen(false)
        setComposeName("")
        setComposeFile(null)
        
        // Reload containers
        const listRes = await fetch(apiUrl("/containers"))
        if (listRes.ok) {
          const data = await listRes.json()
          setContainers(data)
        }
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to create compose stack")
      }
    } catch (e) {
      console.error(e)
      setError("Failed to create compose stack")
    }
  }

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
    
    setSuccess(null)
    setError(null)
    
    try {
      const res = await fetch(apiUrl("/containers"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      if (res.ok) {
        const c = await res.json()
        if (c.detail) {
          const listRes = await fetch(apiUrl("/containers"))
          if (listRes.ok) {
            const data = await listRes.json()
            setContainers(data)
          }
        } else {
          setContainers((prev) => [...prev, c])
        }
        setSuccess(`Container ${creating} created`)
        setOpen(false)
      } else {
        const data = await res.json().catch(() => null)
        setError(data?.detail || "Failed to create container")
      }
    } catch (e) {
      console.error(e)
      setError("Failed to create container")
    }
  }

  const handleStart = async (name: string) => {
    try {
      const res = await fetch(apiUrl(`/containers/${name}/start`), {
        method: "POST",
      })
      if (res.ok) {
        setContainers((prev) =>
          prev.map((c) => (c.name === name ? { ...c, status: "running" } : c))
        )
        setSuccess(null)
        setError(null)
      } else {
        let message = "Error starting"
        try {
          const data = await res.json()
          message = data.detail || message
        } catch {
          message = await res.text()
        }
        setSuccess(null)
        setError(message)
      }
    } catch (e) {
      console.error(e)
      setSuccess(null)
      setError("Failed to start container")
    }
  }

  const handleStop = async (name: string) => {
    try {
      const res = await fetch(apiUrl(`/containers/${name}/stop`), {
        method: "POST",
      })
      if (res.ok) {
        setContainers((prev) =>
          prev.map((c) => (c.name === name ? { ...c, status: "stopped" } : c))
        )
        setError(null)
      } else {
        let message = "Error stopping"
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
      const res = await fetch(apiUrl(`/containers/${name}`), {
        method: "DELETE",
      })
      if (res.ok) {
        setContainers((prev) => prev.filter((c) => c.name !== name))
        setError(null)
        setSuccess(`Container ${name} deleted`)
      } else {
        let message = "Error deleting"
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

  const handleViewLogs = async (name: string, type: string) => {
    if (type.toLowerCase() !== "docker") {
      setError("Logs are only available for Docker containers")
      return
    }
    
    try {
      const res = await fetch(apiUrl(`/containers/${name}/logs?lines=500`))
      if (res.ok) {
        const data = await res.json()
        setLogs(data.logs || "No logs available")
        setLogsContainer(name)
        setLogsOpen(true)
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to fetch logs")
      }
    } catch (e) {
      console.error(e)
      setError("Failed to fetch logs")
    }
  }

  const statusClass = (status: string) =>
    status === "running" ? "bg-green-600 text-white" : "bg-red-600 text-white"

  // Group Docker Compose containers by project
  const groupedContainers = () => {
    const filtered = containers.filter(
      (c) => !filter || c.type.toLowerCase() === filter.toLowerCase()
    )
    
    if (filter.toLowerCase() !== "docker-compose") {
      return { ungrouped: filtered, groups: {} }
    }
    
    const groups: Record<string, ContainerData[]> = {}
    const ungrouped: ContainerData[] = []
    
    filtered.forEach((c) => {
      if (c.type === "Docker-Compose" && c.name.includes("/")) {
        const project = c.name.split("/")[0]
        if (!groups[project]) groups[project] = []
        groups[project].push(c)
      } else {
        ungrouped.push(c)
      }
    })
    
    return { ungrouped, groups }
  }

  const { ungrouped: filteredContainers, groups: composeGroups } = groupedContainers()

  return (
    <div className="space-y-6">
      <NotificationContainer success={success} error={error} onClearSuccess={() => setSuccess(null)} onClearError={() => setError(null)} />
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Container</h2>
          <p className="text-muted-foreground">Manage Docker, LXC, Pods and Kubernetes containers</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-48">
            <Select
              value={filter}
              onValueChange={(value) => setFilter(value === "all" ? "" : value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="All types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="Docker">Docker</SelectItem>
                <SelectItem value="Docker-Compose">Docker Compose</SelectItem>
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
          <Dialog open={composeOpen} onOpenChange={setComposeOpen}>
            <DialogTrigger asChild>
              <Button variant="outline">
                <Plus className="mr-2 h-4 w-4" />
                Docker Compose Stack
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Create Docker Compose Stack</DialogTitle>
                <DialogDescription>Write or upload a docker-compose.yml file</DialogDescription>
              </DialogHeader>
              <Tabs defaultValue="editor" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="editor">Write YAML</TabsTrigger>
                  <TabsTrigger value="upload">Upload File</TabsTrigger>
                </TabsList>
                <TabsContent value="editor" className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="project-name-editor">Project Name</Label>
                    <Input
                      id="project-name-editor"
                      value={composeName}
                      onChange={(e) => setComposeName(e.target.value)}
                      placeholder="e.g. my-app-stack"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="compose-yaml">docker-compose.yml Content</Label>
                    <textarea
                      id="compose-yaml"
                      className="w-full h-96 p-3 font-mono text-sm border rounded-md bg-slate-950 text-slate-50"
                      value={composeYaml}
                      onChange={(e) => setComposeYaml(e.target.value)}
                      placeholder={`version: '3.8'

services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./html:/usr/share/nginx/html
    
  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: example
    volumes:
      - db_data:/var/lib/postgresql/data

volumes:
  db_data:`}
                    />
                  </div>
                  <Button onClick={handleCreateComposeFromYaml} disabled={!composeName || !composeYaml}>
                    <Plus className="mr-2 h-4 w-4" />
                    Create Stack from YAML
                  </Button>
                </TabsContent>
                <TabsContent value="upload" className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="project-name-upload">Project Name</Label>
                    <Input
                      id="project-name-upload"
                      value={composeName}
                      onChange={(e) => setComposeName(e.target.value)}
                      placeholder="e.g. my-app-stack"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="compose-file">docker-compose.yml File</Label>
                    <Input
                      id="compose-file"
                      type="file"
                      accept=".yml,.yaml"
                      onChange={(e) => setComposeFile(e.target.files?.[0] || null)}
                    />
                  </div>
                  <Button onClick={handleCreateComposeFromFile} disabled={!composeName || !composeFile}>
                    <Plus className="mr-2 h-4 w-4" />
                    Create Stack from File
                  </Button>
                </TabsContent>
              </Tabs>
            </DialogContent>
          </Dialog>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button onClick={() => setOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Create Container
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create New Container</DialogTitle>
              <DialogDescription>Configure your new container</DialogDescription>
            </DialogHeader>
            <Tabs defaultValue="basic" className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="basic">Basics</TabsTrigger>
                <TabsTrigger value="resources">Resources</TabsTrigger>
                <TabsTrigger value="network">Network</TabsTrigger>
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
                      placeholder="e.g. my-webapp"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="container-type">Container Type</Label>
                    <Select value={type} onValueChange={setType}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select type" />
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
                      <SelectValue placeholder="Select image" />
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
                    <Label>Environment Variables</Label>
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
                          placeholder="VALUE"
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
                      Add variable
                    </Button>
                  </div>
                )}
              </TabsContent>
              <TabsContent value="resources" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="container-cpu">CPU Cores: {cpu}</Label>
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
                  Add port
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
                      placeholder="Host path"
                    />
                    <Input
                      value={m.container}
                      onChange={(e) => {
                        const arr = [...mounts]
                        arr[idx].container = e.target.value
                        setMounts(arr)
                      }}
                      placeholder="Container path"
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
                  Add mount
                </Button>
              </TabsContent>
            </Tabs>
            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreate}>
                <Plus className="mr-2 h-4 w-4" />
                Create Container
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {/* Docker Compose Groups */}
      {Object.keys(composeGroups).length > 0 && (
        <div className="space-y-4">
          {Object.entries(composeGroups).map(([project, projectContainers]) => (
            <Card key={project}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Container className="h-5 w-5" />
                  Docker Compose Stack: {project}
                  <Badge variant="outline">{projectContainers.length} services</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-2">
                  {projectContainers.map((container) => (
                    <div key={container.id} className="flex items-center justify-between p-2 border rounded">
                      <div className="flex items-center gap-2">
                        <Badge className={statusClass(container.status)}>
                          {container.status}
                        </Badge>
                        <span className="font-medium">{container.name.split("/")[1]}</span>
                        <span className="text-sm text-muted-foreground">{container.image}</span>
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
                        {container.type === "docker" && (
                          <Button 
                            variant="outline" 
                            size="icon"
                            onClick={() => handleViewLogs(container.name, container.type)}
                          >
                            <FileText className="h-4 w-4" />
                          </Button>
                        )}
                        {container.status === "running" ? (
                          <Button
                            variant="destructive"
                            size="icon"
                            onClick={() => handleStop(container.name)}
                          >
                            <Square className="h-4 w-4" />
                          </Button>
                        ) : (
                          <Button
                            variant="default"
                            size="icon"
                            onClick={() => handleStart(container.name)}
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="destructive"
                          size="icon"
                          onClick={() => handleDelete(container.name)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {filter !== "Docker-Compose" && (view === "grid" ? (
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
          {filteredContainers.map((container) => (
            <Card key={container.id} className="rounded-lg aspect-[4/3] flex flex-col">
                <CardHeader className="p-3 pb-2">
                  <CardTitle className="flex items-center gap-2">
                    <Container className="h-5 w-5" />
                    {container.name}
                    <Badge className={statusClass(container.status)}>
                      {container.status === "running" ? "Running" : "Stopped"}
                    </Badge>
                    <Badge variant="outline">{container.type}</Badge>
                  </CardTitle>
                  <CardDescription>{container.image}</CardDescription>
                </CardHeader>
                <CardContent className="p-3 pt-0 flex-grow">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">CPU</span>
                      <div className="font-medium">{container.cpu}</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">RAM</span>
                      <div className="font-medium">{container.memory} MB</div>
                    </div>
                    <div className="col-span-2">
                      <span className="text-muted-foreground">Ports</span>
                      <div className="font-medium truncate">
                        {container.ports.length > 0 ? container.ports.join(", ") : "None"}
                      </div>
                    </div>
                    <div className="col-span-2">
                      <span className="text-muted-foreground">Created</span>
                      <div className="font-medium">{container.created}</div>
                    </div>
                  </div>
                </CardContent>
                <CardFooter className="p-3 pt-0 mt-auto justify-end">
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
                    {container.type.toLowerCase() === "docker" && (
                      <Button 
                        variant="outline" 
                        size="icon"
                        onClick={() => handleViewLogs(container.name, container.type)}
                      >
                        <FileText className="h-4 w-4" />
                      </Button>
                    )}
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
                </CardFooter>
              </Card>
            ))}
        </div>
      ) : (
        <Card>
            <CardContent className="py-0 pl-6 pr-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Image</TableHead>
                    <TableHead>CPU</TableHead>
                    <TableHead>Memory</TableHead>
                    <TableHead>Ports</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredContainers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} className="text-center">
                      No containers found
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredContainers.map((container) => (
                    <TableRow key={container.id}>
                      <TableCell className="font-medium flex items-center gap-2">
                        <Container className="h-4 w-4" /> {container.name}
                      </TableCell>
                      <TableCell>
                        <Badge className={statusClass(container.status)}>
                          {container.status === "running" ? "Running" : "Stopped"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{container.type}</Badge>
                      </TableCell>
                      <TableCell className="text-sm">{container.image}</TableCell>
                      <TableCell>{container.cpu}</TableCell>
                      <TableCell>{container.memory}</TableCell>
                      <TableCell className="text-sm">
                        {container.ports.length > 0 ? container.ports.join(", ") : "None"}
                      </TableCell>
                      <TableCell className="text-sm">{container.created}</TableCell>
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
                          {container.type.toLowerCase() === "docker" && (
                            <Button 
                              variant="outline" 
                              size="icon"
                              onClick={() => handleViewLogs(container.name, container.type)}
                            >
                              <FileText className="h-4 w-4" />
                            </Button>
                          )}
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
                  )))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
      ))}
      {activeTerminal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <TerminalEmulator containerName={activeTerminal} onClose={() => setActiveTerminal(null)} />
        </div>
      )}

      {logsOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-5xl h-[80vh] flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 border-b">
              <div>
                <CardTitle className="text-sm font-medium">Container Logs: {logsContainer}</CardTitle>
                <p className="text-xs text-muted-foreground mt-1">Last 500 lines of logs</p>
              </div>
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setLogsOpen(false)}>
                <Terminal className="h-3 w-3" />
              </Button>
            </CardHeader>
            <CardContent className="flex-1 p-0 overflow-hidden">
              <div className="h-full w-full bg-black text-green-400 p-4 overflow-auto font-mono text-sm">
                <pre className="whitespace-pre-wrap">{logs}</pre>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
