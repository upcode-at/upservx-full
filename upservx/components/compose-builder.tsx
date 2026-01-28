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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Play,
  Square,
  Plus,
  Trash2,
  FileCode,
  FolderOpen,
  Save,
  Edit,
  Upload,
  Grid3X3,
} from "lucide-react"

import { apiUrl } from "@/lib/api"
import { NotificationContainer } from "@/components/ui/notification"

interface ComposeProject {
  name: string
  path: string
  services: ServiceDetails[]
  service_count: number
  status: string
}

interface ServiceDetails {
  name: string
  image: string
  ports: string[]
  restart: string
  volumes: string[]
  environment: { [key: string]: string }
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
  const [editServiceOpen, setEditServiceOpen] = useState(false)
  const [editingService, setEditingService] = useState<string | null>(null)
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
  
  const [success, setSuccess] = useState<string | null>(null)
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

    setSuccess(null)
    setError(null)

    try {
      const res = await fetch(apiUrl("/containers/compose-projects"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_name: newProjectName }),
      })

      if (res.ok) {
        setSuccess(`Project ${newProjectName} created`)
        setNewProjectName("")
        setCreateProjectOpen(false)
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to create project")
      }
    } catch (e) {
      console.error(e)
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

    setSuccess(null)
    setError(null)

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
        setSuccess(`Service ${serviceName} added to ${selectedProject}`)
        resetServiceForm()
        setAddServiceOpen(false)
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to add service")
      }
    } catch (e) {
      console.error(e)
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
    setEditingService(null)
  }

  const handleEditService = async (projectName: string, serviceName: string) => {
    try {
      const res = await fetch(
        apiUrl(`/containers/compose-projects/${projectName}/services/${serviceName}`)
      )

      if (res.ok) {
        const data = await res.json()
        
        // Populate form with existing data
        setServiceName(data.name)
        setServiceImage(data.image)
        
        // Parse ports
        const ports = (data.ports || []).map((p: string) => {
          const parts = p.split(":")
          return { host: parts[0] || "", container: parts[1] || "" }
        })
        setServicePorts(ports.length > 0 ? ports : [{ host: "", container: "" }])
        
        // Parse volumes
        const volumes = (data.volumes || []).map((v: string) => {
          const parts = v.split(":")
          return { host: parts[0] || "", container: parts[1] || "" }
        })
        setServiceVolumes(volumes.length > 0 ? volumes : [{ host: "", container: "" }])
        
        // Parse environment
        const envs = Object.entries(data.environment || {}).map(([name, value]) => ({
          name,
          value: String(value)
        }))
        setServiceEnvs(envs.length > 0 ? envs : [{ name: "", value: "" }])
        
        setServiceCpu(data.cpu || 1)
        setServiceMemory(data.memory || 512)
        setServiceRestart(data.restart || "unless-stopped")
        
        setSelectedProject(projectName)
        setEditingService(serviceName)
        setEditServiceOpen(true)
      } else {
        setError("Failed to load service details")
      }
    } catch (e) {
      console.error(e)
      setError("Failed to load service details")
    }
  }

  const handleUpdateService = async () => {
    if (!selectedProject || !editingService) {
      setError("Invalid state")
      return
    }

    if (!serviceName || !serviceImage) {
      setError("Service name and image are required")
      return
    }

    setSuccess(null)
    setError(null)

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
        apiUrl(`/containers/compose-projects/${selectedProject}/services/${editingService}`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(serviceConfig),
        }
      )

      if (res.ok) {
        setSuccess(`Service ${serviceName} updated in ${selectedProject}`)
        resetServiceForm()
        setEditServiceOpen(false)
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to update service")
      }
    } catch (e) {
      console.error(e)
      setError("Failed to update service")
    }
  }

  const handleStartProject = async (projectName: string) => {
    setSuccess(null)
    setError(null)
    
    try {
      const res = await fetch(
        apiUrl(`/containers/compose-projects/${projectName}/start`),
        { method: "POST" }
      )

      if (res.ok) {
        setSuccess(`Project ${projectName} started`)
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to start project")
      }
    } catch (e) {
      console.error(e)
      setError("Failed to start project")
    }
  }

  const handleStopProject = async (projectName: string) => {
    setSuccess(null)
    setError(null)
    
    try {
      const res = await fetch(
        apiUrl(`/containers/compose-projects/${projectName}/stop`),
        { method: "POST" }
      )

      if (res.ok) {
        setSuccess(`Project ${projectName} stopped`)
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to stop project")
      }
    } catch (e) {
      console.error(e)
      setError("Failed to stop project")
    }
  }

  const handleDeleteProject = async (projectName: string) => {
    if (!confirm(`Delete project ${projectName}?`)) return

    setSuccess(null)
    setError(null)

    try {
      const res = await fetch(
        apiUrl(`/containers/compose-projects/${projectName}`),
        { method: "DELETE" }
      )

      if (res.ok) {
        setSuccess(`Project ${projectName} deleted`)
        if (selectedProject === projectName) {
          setSelectedProject("")
        }
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to delete project")
      }
    } catch (e) {
      console.error(e)
      setError("Failed to delete project")
    }
  }

  const handleRemoveService = async (projectName: string, serviceName: string) => {
    if (!confirm(`Remove service ${serviceName} from ${projectName}?`)) return

    setSuccess(null)
    setError(null)

    try {
      const res = await fetch(
        apiUrl(`/containers/compose-projects/${projectName}/services/${serviceName}`),
        { method: "DELETE" }
      )

      if (res.ok) {
        setSuccess(`Service ${serviceName} removed from ${projectName}`)
        loadProjects()
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to remove service")
      }
    } catch (e) {
      console.error(e)
      setError("Failed to remove service")
    }
  }

  const handleViewCompose = async (projectName: string) => {
    setError(null)
    
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
      console.error(e)
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
      <NotificationContainer success={success} error={error} onClearSuccess={() => setSuccess(null)} onClearError={() => setError(null)} />

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
                  <Button onClick={handleCreateProject}>
                    <Plus className="mr-2 h-4 w-4" />
                    Create Project
                  </Button>
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

                  <Button onClick={handleAddService}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Service
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          {/* Edit Service Dialog */}
          <Dialog open={editServiceOpen} onOpenChange={(open) => {
            setEditServiceOpen(open)
            if (!open) resetServiceForm()
          }}>
            <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Edit Service</DialogTitle>
                <DialogDescription>
                  Update the configuration of {editingService}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Service Name</Label>
                    <Input
                      placeholder="my-service"
                      value={serviceName}
                      onChange={(e) => setServiceName(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label>Docker Image</Label>
                    <Input
                      placeholder="nginx:latest"
                      value={serviceImage}
                      onChange={(e) => setServiceImage(e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>CPU Limit</Label>
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

                <Button onClick={handleUpdateService}>
                  <Save className="mr-2 h-4 w-4" />
                  Update Service
                </Button>
              </div>
            </DialogContent>
          </Dialog>

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
        {projects.length === 0 ? (
          // Empty State
          <div className="text-center py-12">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
              <Card className="cursor-pointer hover:shadow-lg transition-shadow">
                <CardContent className="p-6">
                  <div className="flex flex-col items-center space-y-4">
                    <div className="p-3 bg-red-100 rounded-full">
                      <FileCode className="h-8 w-8 text-red-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-lg">Import YAML</h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        Upload an existing docker-compose.yml file
                      </p>
                    </div>
                    <Button className="w-full" variant="outline">
                      <Upload className="mr-2 h-4 w-4" />
                      Import File
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card className="cursor-pointer hover:shadow-lg transition-shadow">
                <CardContent className="p-6">
                  <div className="flex flex-col items-center space-y-4">
                    <div className="p-3 bg-indigo-100 rounded-full">
                      <Grid3X3 className="h-8 w-8 text-indigo-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-lg">Use Template</h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        Start with a pre-configured template
                      </p>
                    </div>
                    <Button className="w-full" variant="outline">
                      <Grid3X3 className="mr-2 h-4 w-4" />
                      Browse Templates
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card className="cursor-pointer hover:shadow-lg transition-shadow">
                <CardContent className="p-6">
                  <div className="flex flex-col items-center space-y-4">
                    <div className="p-3 bg-green-100 rounded-full">
                      <Plus className="h-8 w-8 text-green-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-lg">Create New</h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        Build a custom docker-compose project
                      </p>
                    </div>
                    <Button className="w-full" onClick={() => setCreateProjectOpen(true)}>
                      <Plus className="mr-2 h-4 w-4" />
                      New Project
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        ) : (
          projects.map((project) => (
            <Card key={project.name} className="hover:shadow-lg transition-shadow">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-red-100 rounded-lg">
                      <FolderOpen className="h-5 w-5 text-red-600" />
                    </div>
                    <div>
                      <CardTitle className="text-xl pl-2">{project.name}</CardTitle>
                      <CardDescription className="font-mono text-sm pl-2">{project.path}</CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Badge
                      variant={project.status === "running" ? "default" : "secondary"}
                      className={project.status === "running" ? "bg-green-100 text-green-800 hover:bg-green-200" : ""}
                    >
                      <div className="flex items-center space-x-1">
                        <div className={`w-2 h-2 rounded-full ${project.status === "running" ? "bg-green-500" : "bg-gray-400"}`}></div>
                        <span>{project.status}</span>
                      </div>
                    </Badge>
                    <Badge variant="outline" className="bg-indigo-50 text-indigo-700 border-indigo-200">
                      {project.service_count} services
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-semibold">Services</h4>
                    <Button size="sm" variant="outline" onClick={() => setAddServiceOpen(true)}>
                      <Plus className="h-3 w-3 mr-1" />
                      Add Service
                    </Button>
                  </div>
                  {project.services.length > 0 ? (
                    <div className="border overflow-hidden">
                      <Table>
                        <TableHeader>
                          <TableRow className="bg-muted/50">
                            <TableHead className="w-[200px]">Name</TableHead>
                            <TableHead className="w-[250px]">Image</TableHead>
                            <TableHead className="w-[150px]">Ports</TableHead>
                            <TableHead className="w-[120px]">Restart</TableHead>
                            <TableHead className="w-[120px]">Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {project.services.map((service) => (
                            <TableRow key={service.name} className="hover:bg-muted/30">
                              <TableCell className="font-medium pl-4">
                                <div className="flex items-center space-x-2">
                                  <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                                  <span>{service.name}</span>
                                </div>
                              </TableCell>
                              <TableCell className="font-mono text-sm">
                                {service.image || "N/A"}
                              </TableCell>
                              <TableCell>
                                <div className="flex flex-wrap gap-1">
                                  {service.ports && service.ports.length > 0 ? (
                                    service.ports.slice(0, 2).map((port, idx) => (
                                      <Badge key={idx} variant="outline" className="text-xs">
                                        {port}
                                      </Badge>
                                    ))
                                  ) : (
                                    <span className="text-muted-foreground text-xs">None</span>
                                  )}
                                  {service.ports && service.ports.length > 2 && (
                                    <Badge variant="outline" className="text-xs">
                                      +{service.ports.length - 2}
                                    </Badge>
                                  )}
                                </div>
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline" className="text-xs">
                                  {service.restart || "no"}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <div className="flex space-x-1">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => handleEditService(project.name, service.name)}
                                    className="h-8 w-8 p-0"
                                  >
                                    <Edit className="h-3 w-3" />
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => handleRemoveService(project.name, service.name)}
                                    className="h-8 w-8 p-0 text-red-600 hover:text-red-700"
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </Button>
                                </div>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <p className="mb-4">No services configured yet.</p>
                      <p className="text-sm">Click "Add Service" to get started.</p>
                    </div>
                  )}
                </div>

                <div className="flex justify-between items-center pt-2 border-t">
                  <div className="flex space-x-2">
                    {project.status !== "running" ? (
                      <Button
                        size="sm"
                        variant="success"
                        onClick={() => handleStartProject(project.name)}
                      >
                        <Play className="mr-2 h-4 w-4" />
                        Start Project
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="destructive-outline"
                        onClick={() => handleStopProject(project.name)}
                      >
                        <Square className="mr-2 h-4 w-4" />
                        Stop Project
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
                  </div>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleDeleteProject(project.name)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))
        )}
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
