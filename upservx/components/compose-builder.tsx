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
import {
  Play,
  Square,
  Plus,
  Trash2,
  FileCode,
  FolderOpen,
} from "lucide-react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { apiUrl } from "@/lib/api"

interface ComposeProject {
  name: string
  path: string
  services: string[]
  service_count: number
  status: string
}

interface ServiceForm {
  name: string
  image: string
  ports: string[]
  volumes: string[]
  environment: { [key: string]: string }
  cpu?: number
  memory?: number
  restart: string
}

export function ComposeBuilder() {
  const [projects, setProjects] = useState<ComposeProject[]>([])
  const [selectedProject, setSelectedProject] = useState<string>("")
  const [newProjectName, setNewProjectName] = useState("")
  const [createProjectOpen, setCreateProjectOpen] = useState(false)
  const [addServiceOpen, setAddServiceOpen] = useState(false)
  const [viewComposeOpen, setViewComposeOpen] = useState(false)
  const [composeContent, setComposeContent] = useState("")
  
  // Service form state
  const [serviceName, setServiceName] = useState("")
  const [serviceImage, setServiceImage] = useState("")
  const [servicePorts, setServicePorts] = useState<{ host: string; container: string }[]>([
    { host: "", container: "" },
  ])
  const [serviceVolumes, setServiceVolumes] = useState<{ host: string; container: string }[]>([
    { host: "", container: "" },
  ])
  const [serviceEnvs, setServiceEnvs] = useState<{ name: string; value: string }[]>([
    { name: "", value: "" },
  ])
  const [serviceCpu, setServiceCpu] = useState<number>(1)
  const [serviceMemory, setServiceMemory] = useState<number>(512)
  const [serviceRestart, setServiceRestart] = useState("unless-stopped")
  
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    try {
      const res = await fetch(apiUrl("/containers/compose-projects"))
      if (res.ok) {
        const data = await res.json()
        setProjects(data)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleCreateProject = async () => {
    if (!newProjectName) {
      setError("Project name is required")
      return
    }

    try {
      const res = await fetch(apiUrl("/containers/compose-projects"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_name: newProjectName }),
      })

      if (res.ok) {
        setMessage(`Project ${newProjectName} created`)
        setNewProjectName("")
        setCreateProjectOpen(false)
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to create project")
      }
    } catch (e) {
      setError("Failed to create project")
    }
  }

  const handleAddService = async () => {
    if (!selectedProject) {
      setError("Please select a project first")
      return
    }

    if (!serviceName || !serviceImage) {
      setError("Service name and image are required")
      return
    }

    // Build service config
    const serviceConfig: ServiceForm = {
      name: serviceName,
      image: serviceImage,
      ports: servicePorts
        .filter(p => p.host && p.container)
        .map(p => `${p.host}:${p.container}`),
      volumes: serviceVolumes
        .filter(v => v.host && v.container)
        .map(v => `${v.host}:${v.container}`),
      environment: Object.fromEntries(
        serviceEnvs.filter(e => e.name && e.value).map(e => [e.name, e.value])
      ),
      cpu: serviceCpu,
      memory: serviceMemory,
      restart: serviceRestart,
    }

    try {
      const res = await fetch(
        apiUrl(`/containers/compose-projects/${selectedProject}/services`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(serviceConfig),
        }
      )

      if (res.ok) {
        setMessage(`Service ${serviceName} added to ${selectedProject}`)
        resetServiceForm()
        setAddServiceOpen(false)
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to add service")
      }
    } catch (e) {
      setError("Failed to add service")
    }
  }

  const resetServiceForm = () => {
    setServiceName("")
    setServiceImage("")
    setServicePorts([{ host: "", container: "" }])
    setServiceVolumes([{ host: "", container: "" }])
    setServiceEnvs([{ name: "", value: "" }])
    setServiceCpu(1)
    setServiceMemory(512)
    setServiceRestart("unless-stopped")
  }

  const handleStartProject = async (projectName: string) => {
    try {
      const res = await fetch(
        apiUrl(`/containers/compose-projects/${projectName}/start`),
        { method: "POST" }
      )

      if (res.ok) {
        setMessage(`Project ${projectName} started`)
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to start project")
      }
    } catch (e) {
      setError("Failed to start project")
    }
  }

  const handleStopProject = async (projectName: string) => {
    try {
      const res = await fetch(
        apiUrl(`/containers/compose-projects/${projectName}/stop`),
        { method: "POST" }
      )

      if (res.ok) {
        setMessage(`Project ${projectName} stopped`)
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to stop project")
      }
    } catch (e) {
      setError("Failed to stop project")
    }
  }

  const handleDeleteProject = async (projectName: string) => {
    if (!confirm(`Delete project ${projectName}?`)) return

    try {
      const res = await fetch(
        apiUrl(`/containers/compose-projects/${projectName}`),
        { method: "DELETE" }
      )

      if (res.ok) {
        setMessage(`Project ${projectName} deleted`)
        if (selectedProject === projectName) {
          setSelectedProject("")
        }
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to delete project")
      }
    } catch (e) {
      setError("Failed to delete project")
    }
  }

  const handleViewCompose = async (projectName: string) => {
    try {
      const res = await fetch(
        apiUrl(`/containers/compose-projects/${projectName}/compose`)
      )

      if (res.ok) {
        const data = await res.json()
        setComposeContent(JSON.stringify(data, null, 2))
        setViewComposeOpen(true)
      } else {
        setError("Failed to load compose file")
      }
    } catch (e) {
      setError("Failed to load compose file")
    }
  }

  const addPort = () => {
    setServicePorts([...servicePorts, { host: "", container: "" }])
  }

  const addVolume = () => {
    setServiceVolumes([...serviceVolumes, { host: "", container: "" }])
  }

  const addEnv = () => {
    setServiceEnvs([...serviceEnvs, { name: "", value: "" }])
  }

  return (
    <div className="space-y-4">
      {message && (
        <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded relative">
          {message}
          <button onClick={() => setMessage(null)} className="absolute top-0 right-0 px-4 py-3">
            ×
          </button>
        </div>
      )}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative">
          {error}
          <button onClick={() => setError(null)} className="absolute top-0 right-0 px-4 py-3">
            ×
          </button>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Docker Compose Builder</CardTitle>
          <CardDescription>
            Create and manage Docker Compose projects with a visual interface
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Dialog open={createProjectOpen} onOpenChange={setCreateProjectOpen}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  New Project
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create Compose Project</DialogTitle>
                  <DialogDescription>
                    Create a new Docker Compose project in /opt/upservx/compose
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label>Project Name</Label>
                    <Input
                      value={newProjectName}
                      onChange={(e) => setNewProjectName(e.target.value)}
                      placeholder="my-project"
                    />
                  </div>
                  <Button onClick={handleCreateProject}>Create Project</Button>
                </div>
              </DialogContent>
            </Dialog>

            <Dialog open={addServiceOpen} onOpenChange={setAddServiceOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" disabled={!selectedProject}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Service
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Add Service to {selectedProject}</DialogTitle>
                  <DialogDescription>
                    Configure a new service for your compose project
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label>Service Name</Label>
                    <Input
                      value={serviceName}
                      onChange={(e) => setServiceName(e.target.value)}
                      placeholder="web"
                    />
                  </div>

                  <div>
                    <Label>Image</Label>
                    <Input
                      value={serviceImage}
                      onChange={(e) => setServiceImage(e.target.value)}
                      placeholder="nginx:latest"
                    />
                  </div>

                  <div>
                    <Label>CPU Cores</Label>
                    <Input
                      type="number"
                      value={serviceCpu}
                      onChange={(e) => setServiceCpu(parseFloat(e.target.value))}
                      step="0.1"
                      min="0.1"
                    />
                  </div>

                  <div>
                    <Label>Memory (MB)</Label>
                    <Input
                      type="number"
                      value={serviceMemory}
                      onChange={(e) => setServiceMemory(parseInt(e.target.value))}
                      min="128"
                    />
                  </div>

                  <div>
                    <Label>Restart Policy</Label>
                    <Select value={serviceRestart} onValueChange={setServiceRestart}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="no">No</SelectItem>
                        <SelectItem value="always">Always</SelectItem>
                        <SelectItem value="on-failure">On Failure</SelectItem>
                        <SelectItem value="unless-stopped">Unless Stopped</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <Label>Ports</Label>
                      <Button size="sm" variant="outline" onClick={addPort}>
                        <Plus className="h-3 w-3" />
                      </Button>
                    </div>
                    {servicePorts.map((port, idx) => (
                      <div key={idx} className="grid grid-cols-2 gap-2 mb-2">
                        <Input
                          placeholder="Host Port (8080)"
                          value={port.host}
                          onChange={(e) => {
                            const newPorts = [...servicePorts]
                            newPorts[idx].host = e.target.value
                            setServicePorts(newPorts)
                          }}
                        />
                        <Input
                          placeholder="Container Port (80)"
                          value={port.container}
                          onChange={(e) => {
                            const newPorts = [...servicePorts]
                            newPorts[idx].container = e.target.value
                            setServicePorts(newPorts)
                          }}
                        />
                      </div>
                    ))}
                  </div>

                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <Label>Volumes</Label>
                      <Button size="sm" variant="outline" onClick={addVolume}>
                        <Plus className="h-3 w-3" />
                      </Button>
                    </div>
                    {serviceVolumes.map((volume, idx) => (
                      <div key={idx} className="grid grid-cols-2 gap-2 mb-2">
                        <Input
                          placeholder="Host Path (/data)"
                          value={volume.host}
                          onChange={(e) => {
                            const newVolumes = [...serviceVolumes]
                            newVolumes[idx].host = e.target.value
                            setServiceVolumes(newVolumes)
                          }}
                        />
                        <Input
                          placeholder="Container Path (/app/data)"
                          value={volume.container}
                          onChange={(e) => {
                            const newVolumes = [...serviceVolumes]
                            newVolumes[idx].container = e.target.value
                            setServiceVolumes(newVolumes)
                          }}
                        />
                      </div>
                    ))}
                  </div>

                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <Label>Environment Variables</Label>
                      <Button size="sm" variant="outline" onClick={addEnv}>
                        <Plus className="h-3 w-3" />
                      </Button>
                    </div>
                    {serviceEnvs.map((env, idx) => (
                      <div key={idx} className="grid grid-cols-2 gap-2 mb-2">
                        <Input
                          placeholder="Variable Name"
                          value={env.name}
                          onChange={(e) => {
                            const newEnvs = [...serviceEnvs]
                            newEnvs[idx].name = e.target.value
                            setServiceEnvs(newEnvs)
                          }}
                        />
                        <Input
                          placeholder="Value"
                          value={env.value}
                          onChange={(e) => {
                            const newEnvs = [...serviceEnvs]
                            newEnvs[idx].value = e.target.value
                            setServiceEnvs(newEnvs)
                          }}
                        />
                      </div>
                    ))}
                  </div>

                  <Button onClick={handleAddService}>Add Service</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          <div>
            <Label>Active Project</Label>
            <Select value={selectedProject} onValueChange={setSelectedProject}>
              <SelectTrigger>
                <SelectValue placeholder="Select a project" />
              </SelectTrigger>
              <SelectContent>
                {projects.map((project) => (
                  <SelectItem key={project.name} value={project.name}>
                    {project.name} ({project.service_count} services)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4">
        {projects.map((project) => (
          <Card key={project.name}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <FolderOpen className="h-5 w-5" />
                    {project.name}
                  </CardTitle>
                  <CardDescription>{project.path}</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={project.status === "running" ? "default" : "secondary"}>
                    {project.status}
                  </Badge>
                  <Badge variant="outline">{project.service_count} services</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex flex-wrap gap-2">
                  {project.services.map((service) => (
                    <Badge key={service} variant="outline">
                      {service}
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-2 pt-2">
                  {project.status !== "running" ? (
                    <Button
                      size="sm"
                      onClick={() => handleStartProject(project.name)}
                    >
                      <Play className="mr-2 h-4 w-4" />
                      Start
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleStopProject(project.name)}
                    >
                      <Square className="mr-2 h-4 w-4" />
                      Stop
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleViewCompose(project.name)}
                  >
                    <FileCode className="mr-2 h-4 w-4" />
                    View YAML
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleDeleteProject(project.name)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={viewComposeOpen} onOpenChange={setViewComposeOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Docker Compose File</DialogTitle>
          </DialogHeader>
          <pre className="bg-slate-950 text-slate-50 p-4 rounded font-mono text-sm overflow-x-auto">
            {composeContent}
          </pre>
        </DialogContent>
      </Dialog>
    </div>
  )
}
