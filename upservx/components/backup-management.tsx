"use client"

import { useState, useEffect } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Server, Plus, Loader2, AlertCircle, Play, Trash2, HardDrive, Clock } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { apiUrl, getAuthHeaders } from "@/lib/api"

interface BackupServer {
  id: number
  name: string
  type: string
  status: string
  host?: string
  port?: number
  remote_path?: string
  local_path?: string
  created: string
}

interface BackupServerCreate {
  name: string
  type: string
  host?: string
  port?: number
  remote_path?: string
  local_path?: string
}

interface BackupJobCreate {
  name: string
  backup_type: 'vm' | 'container' | 'system' | 'database'
  targets: string[]
  schedule: string
  server_id: number
}

interface BackupJob {
  id: number
  name: string
  backup_type: 'vm' | 'container' | 'system' | 'database'
  targets: string[]
  schedule: string
  server_id: number
  status: 'active' | 'paused' | 'error'
  last_run?: string
  next_run?: string
  last_size?: number
  retention_days: number
  compression: boolean
  created: string
}

const backupApi = {
  servers: {
    list: async (): Promise<BackupServer[]> => {
      const response = await fetch(apiUrl('/backup/servers'), {
        method: 'GET',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        }
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return response.json()
    },
    create: async (data: BackupServerCreate): Promise<BackupServer> => {
      const response = await fetch(apiUrl('/backup/servers'), {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return response.json()
    },
    delete: async (id: number): Promise<void> => {
      const response = await fetch(apiUrl(`/backup/servers/${id}`), {
        method: 'DELETE',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        }
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
    }
  },
  jobs: {
    list: async (): Promise<BackupJob[]> => {
      const response = await fetch(apiUrl('/backup/jobs'), {
        method: 'GET',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        }
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return response.json()
    },
    create: async (data: BackupJobCreate): Promise<BackupJob> => {
      const response = await fetch(apiUrl('/backup/jobs'), {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return response.json()
    },
    execute: async (jobId: number): Promise<{ message: string }> => {
      const response = await fetch(apiUrl(`/backup/jobs/${jobId}/execute`), {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        }
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return response.json()
    },
    delete: async (id: number): Promise<void> => {
      const response = await fetch(apiUrl(`/backup/jobs/${id}`), {
        method: 'DELETE',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        }
      })
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
    }
  },
  // API for available backup targets
  targets: {
    getVMs: async (): Promise<{ name: string; id: string }[]> => {
      const response = await fetch(apiUrl('/vms'), {
        method: 'GET',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json'
        }
      })
      if (!response.ok) {
        return [] // No VMs available
      }
      return response.json()
    },
    getContainers: async (): Promise<{ name: string; id: string }[]> => {
      try {
        const response = await fetch(apiUrl('/containers'), {
          method: 'GET',
          headers: {
            ...getAuthHeaders(),
            'Content-Type': 'application/json'
          }
        })
        if (!response.ok) {
          return [] // No containers available
        }
        return response.json()
      } catch {
        return []
      }
    }
  }
}

export default function BackupManagement() {
  const [activeTab, setActiveTab] = useState('servers')
  const [backupServers, setBackupServers] = useState<BackupServer[]>([])
  const [backupJobs, setBackupJobs] = useState<BackupJob[]>([])
  const [availableVMs, setAvailableVMs] = useState<{ name: string; id: string }[]>([])
  const [availableContainers, setAvailableContainers] = useState<{ name: string; id: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Dialog states
  const [showServerDialog, setShowServerDialog] = useState(false)
  const [showJobDialog, setShowJobDialog] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<{ type: 'server' | 'job', id: number, name: string } | null>(null)
  
  // Forms
  const [serverForm, setServerForm] = useState({
    name: '',
    type: 'local',
    local_path: '/var/backups'
  })
  
  const [jobForm, setJobForm] = useState<{
    name: string
    backup_type: 'vm' | 'container' | 'system' | 'database'
    targets: string[]
    schedule: string
    server_id: number
    retention_days: number
    compression: boolean
  }>({
    name: '',
    backup_type: 'system',
    targets: [''],
    schedule: '0 2 * * *',
    server_id: 0,
    retention_days: 30,
    compression: true
  })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [serversData, jobsData, vmsData, containersData] = await Promise.all([
        backupApi.servers.list(),
        backupApi.jobs.list(),
        backupApi.targets.getVMs(),
        backupApi.targets.getContainers()
      ])
      
      setBackupServers(serversData)
      setBackupJobs(jobsData)
      setAvailableVMs(vmsData)
      setAvailableContainers(containersData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading data')
      console.error('Error fetching backup data:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateServer = async () => {
    try {
      await backupApi.servers.create(serverForm)
      await loadData()
      setShowServerDialog(false)
      setServerForm({ name: '', type: 'local', local_path: '/var/backups' })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error creating server')
    }
  }

  const handleCreateJob = async () => {
    try {
      const filteredTargets = jobForm.targets.filter(t => t.trim() !== '')
      await backupApi.jobs.create({ ...jobForm, targets: filteredTargets })
      await loadData()
      setShowJobDialog(false)
      setJobForm({
        name: '',
        backup_type: 'system',
        targets: [''],
        schedule: '0 2 * * *',
        server_id: 0,
        retention_days: 30,
        compression: true
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error creating job')
    }
  }

  const handleExecuteJob = async (jobId: number) => {
    try {
      await backupApi.jobs.execute(jobId)
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error executing job')
    }
  }

  const handleDeleteClick = (type: 'server' | 'job', id: number, name: string) => {
    setDeleteTarget({ type, id, name })
    setShowDeleteDialog(true)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    
    try {
      if (deleteTarget.type === 'server') {
        await backupApi.servers.delete(deleteTarget.id)
      } else {
        await backupApi.jobs.delete(deleteTarget.id)
      }
      await loadData()
      setShowDeleteDialog(false)
      setDeleteTarget(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error deleting')
    }
  }

  const addTarget = () => {
    setJobForm(prev => ({ ...prev, targets: [...prev.targets, ''] }))
  }

  const removeTarget = (index: number) => {
    setJobForm(prev => ({ ...prev, targets: prev.targets.filter((_, i) => i !== index) }))
  }

  const updateTarget = (index: number, value: string) => {
    setJobForm(prev => ({
      ...prev,
      targets: prev.targets.map((target, i) => i === index ? value : target)
    }))
  }

  const getBackupTargetOptions = () => {
    const options: { value: string, label: string, group: string }[] = []
    
    // System Paths
    const systemPaths = [
      { value: '/home', label: '/home - User Directories', group: 'System Paths' },
      { value: '/var/www', label: '/var/www - Web Files', group: 'System Paths' },
      { value: '/etc', label: '/etc - Configuration Files', group: 'System Paths' },
      { value: '/opt', label: '/opt - Software Packages', group: 'System Paths' },
      { value: '/srv', label: '/srv - Service Data', group: 'System Paths' }
    ]
    options.push(...systemPaths)

    // Virtual Machines
    if (availableVMs.length > 0) {
      availableVMs.forEach(vm => {
        options.push({
          value: `vm:${vm.name}`,
          label: `${vm.name} (VM)`,
          group: 'Virtual Machines'
        })
      })
    }

    // Containers
    if (availableContainers.length > 0) {
      availableContainers.forEach(container => {
        options.push({
          value: `container:${container.name}`,
          label: `${container.name} (Container)`,
          group: 'Containers'
        })
      })
    }

    return options
  }



  const getServerName = (serverId: number) => {
    const server = backupServers.find(s => s.id === serverId)
    return server?.name || `Server ${serverId}`
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin" />
        <span className="ml-2">Loading backup data...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-700">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setError(null)}
                className="ml-auto"
              >
                Close
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Backup Management</h2>
          <p className="text-muted-foreground">Manage backup servers and automated backups</p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="servers" className="flex items-center gap-2">
            <Server className="h-4 w-4" />
            Backup Servers
          </TabsTrigger>
          <TabsTrigger value="jobs" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Backup Jobs
          </TabsTrigger>
        </TabsList>

        <TabsContent value="servers" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-xl font-semibold">Backup Servers</h3>
            <Dialog open={showServerDialog} onOpenChange={setShowServerDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  New Server
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Backup Server</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="name">Name</Label>
                    <Input
                      id="name"
                      value={serverForm.name}
                      onChange={(e) => setServerForm(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="My Backup Server"
                    />
                  </div>
                  <div>
                    <Label htmlFor="type">Type</Label>
                    <Select
                      value={serverForm.type}
                      onValueChange={(value) => setServerForm(prev => ({ ...prev, type: value }))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="local">Local Storage</SelectItem>
                        <SelectItem value="remote">Remote Server</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {serverForm.type === 'local' && (
                    <div>
                      <Label htmlFor="local_path">Local Path</Label>
                      <Input
                        id="local_path"
                        value={serverForm.local_path}
                        onChange={(e) => setServerForm(prev => ({ ...prev, local_path: e.target.value }))}
                        placeholder="/var/backups"
                      />
                    </div>
                  )}
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowServerDialog(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleCreateServer}>
                      Create Server
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
          
          <div className="grid gap-4">
            {backupServers.map((server) => (
              <Card key={server.id}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-blue-100 rounded">
                        {server.type === 'local' ? (
                          <HardDrive className="h-5 w-5 text-blue-600" />
                        ) : (
                          <Server className="h-5 w-5 text-blue-600" />
                        )}
                      </div>
                      <div>
                        <h3 className="font-medium">{server.name}</h3>
                        <p className="text-sm text-muted-foreground">
                          {server.type === 'remote' ? server.host : server.local_path}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">{server.status}</Badge>
                      <Badge variant="outline">{server.type}</Badge>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleDeleteClick('server', server.id, server.name)}
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="jobs" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-xl font-semibold">Backup Jobs</h3>
            <Dialog open={showJobDialog} onOpenChange={setShowJobDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  New Job
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Create Backup Job</DialogTitle>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="job_name">Job Name</Label>
                      <Input
                        id="job_name"
                        value={jobForm.name}
                        onChange={(e) => setJobForm(prev => ({ ...prev, name: e.target.value }))}
                        placeholder="Daily System Backup"
                      />
                    </div>
                    <div>
                      <Label htmlFor="backup_type">Backup Type</Label>
                      <Select
                        value={jobForm.backup_type}
                        onValueChange={(value: 'vm' | 'container' | 'system' | 'database') => setJobForm(prev => ({ ...prev, backup_type: value }))}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="vm">Virtual Machine</SelectItem>
                          <SelectItem value="container">Container</SelectItem>
                          <SelectItem value="system">System Files</SelectItem>
                          <SelectItem value="database">Database</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div>
                    <Label>Backup Targets</Label>
                    {jobForm.targets.map((target, index) => (
                      <div key={index} className="flex gap-2 mt-2">
                        <Select
                          value={target}
                          onValueChange={(value) => updateTarget(index, value)}
                        >
                          <SelectTrigger className="flex-1">
                            <SelectValue placeholder={
                              jobForm.backup_type === 'vm' ? 'Select Virtual Machine' :
                              jobForm.backup_type === 'container' ? 'Select Container' :
                              jobForm.backup_type === 'system' ? 'Select System Path' :
                              'Select Backup Target'
                            } />
                          </SelectTrigger>
                          <SelectContent>
                            {getBackupTargetOptions()
                              .filter(opt => 
                                jobForm.backup_type === 'vm' ? opt.group === 'Virtual Machines' :
                                jobForm.backup_type === 'container' ? opt.group === 'Containers' :
                                jobForm.backup_type === 'system' ? opt.group === 'System Paths' :
                                true
                              )
                              .map((option) => (
                                <SelectItem key={option.value} value={option.value}>
                                  {option.label}
                                </SelectItem>
                              ))
                            }
                          </SelectContent>
                        </Select>
                        {index > 0 && (
                          <Button variant="outline" size="sm" onClick={() => removeTarget(index)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    ))}
                    <Button variant="outline" size="sm" className="mt-2" onClick={addTarget}>
                      <Plus className="h-4 w-4 mr-2" />
                      Add Target
                    </Button>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="server_select">Backup Server</Label>
                      <Select
                        value={jobForm.server_id.toString()}
                        onValueChange={(value) => setJobForm(prev => ({ ...prev, server_id: parseInt(value) }))}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select Server" />
                        </SelectTrigger>
                        <SelectContent>
                          {backupServers.map((server) => (
                            <SelectItem key={server.id} value={server.id.toString()}>
                              {server.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="schedule">Schedule (Cron)</Label>
                      <Input
                        id="schedule"
                        value={jobForm.schedule}
                        onChange={(e) => setJobForm(prev => ({ ...prev, schedule: e.target.value }))}
                        placeholder="0 2 * * *"
                      />
                    </div>
                  </div>

                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowJobDialog(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleCreateJob} disabled={jobForm.server_id === 0}>
                      Create Job
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid gap-4">
            {backupJobs.map((job) => (
              <Card key={job.id}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-green-100 rounded">
                        <Clock className="h-5 w-5 text-green-600" />
                      </div>
                      <div>
                        <h3 className="font-medium">{job.name}</h3>
                        <p className="text-sm text-muted-foreground">
                          {job.backup_type} • {getServerName(job.server_id)} • {job.schedule}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Targets: {job.targets.join(', ')}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">{job.status}</Badge>
                      <Button variant="outline" size="sm" onClick={() => handleExecuteJob(job.id)}>
                        <Play className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleDeleteClick('job', job.id, job.name)}
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {deleteTarget?.type === 'server' ? 'Delete Backup Server' : 'Delete Backup Job'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Are you sure you want to delete <strong>&quot;{deleteTarget?.name}&quot;</strong>?
              {deleteTarget?.type === 'server' && (
                <span className="block mt-2 text-red-600">
                  Warning: All associated backup jobs will also be deleted.
                </span>
              )}
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
                Cancel
              </Button>
              <Button variant="destructive" onClick={handleDeleteConfirm}>
                {deleteTarget?.type === 'server' ? 'Delete Server' : 'Delete Job'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
