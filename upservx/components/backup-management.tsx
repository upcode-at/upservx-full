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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

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
  rsync_enabled?: boolean
  rsync_host?: string
  rsync_port?: number
  rsync_user?: string
  rsync_path?: string
  rsync_ssh_key?: string
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
  rsync_enabled?: boolean
  rsync_host?: string
  rsync_port?: number
  rsync_user?: string
  rsync_path?: string
  rsync_ssh_key?: string
  created: string
}

// Helper functions that use apiUrl at runtime, not at module load
async function fetchBackupServers(): Promise<BackupServer[]> {
  const response = await fetch(apiUrl('/backup/servers'), {
    method: 'GET',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json'
    }
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

async function createBackupServer(data: BackupServerCreate): Promise<BackupServer> {
  const response = await fetch(apiUrl('/backup/servers'), {
    method: 'POST',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

async function deleteBackupServer(id: number): Promise<void> {
  const response = await fetch(apiUrl(`/backup/servers/${id}`), {
    method: 'DELETE',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json'
    }
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
}

async function fetchBackupJobs(): Promise<BackupJob[]> {
  const response = await fetch(apiUrl('/backup/jobs'), {
    method: 'GET',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json'
    }
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

async function createBackupJob(data: BackupJobCreate): Promise<BackupJob> {
  const response = await fetch(apiUrl('/backup/jobs'), {
    method: 'POST',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

async function executeBackupJob(jobId: number): Promise<{ message: string }> {
  const response = await fetch(apiUrl(`/backup/jobs/${jobId}/execute`), {
    method: 'POST',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json'
    }
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

async function deleteBackupJob(id: number): Promise<void> {
  const response = await fetch(apiUrl(`/backup/jobs/${id}`), {
    method: 'DELETE',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json'
    }
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
}

async function fetchVMs(): Promise<{ name: string; id: string }[]> {
  try {
    const response = await fetch(apiUrl('/vms'), {
      method: 'GET',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json'
      }
    })
    if (!response.ok) return []
    return response.json()
  } catch {
    return []
  }
}

async function fetchContainers(): Promise<{ name: string; id: string }[]> {
  try {
    const response = await fetch(apiUrl('/containers'), {
      method: 'GET',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json'
      }
    })
    if (!response.ok) return []
    return response.json()
  } catch {
    return []
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
    local_path: '/var/backups',
    host: '',
    port: 22,
    remote_path: '',
    username: 'root',
    auth_type: 'ssh_key',
    password: '',
    ssh_key: ''
  })
  
  const [jobForm, setJobForm] = useState<{
    name: string
    backup_type: 'vm' | 'container' | 'system' | 'database'
    targets: string[]
    schedule: string
    server_id: number
    retention_days: number
    compression: boolean
    rsync_enabled: boolean
    rsync_host: string
    rsync_port: number
    rsync_user: string
    rsync_path: string
    rsync_ssh_key: string
  }>({
    name: '',
    backup_type: 'system',
    targets: [''],
    schedule: '0 2 * * *',
    server_id: 0,
    retention_days: 30,
    compression: true,
    rsync_enabled: false,
    rsync_host: '',
    rsync_port: 22,
    rsync_user: 'root',
    rsync_path: '/backups',
    rsync_ssh_key: ''
  })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [serversData, jobsData, vmsData, containersData] = await Promise.all([
        fetchBackupServers(),
        fetchBackupJobs(),
        fetchVMs(),
        fetchContainers()
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
      await createBackupServer(serverForm)
      setServerForm({ 
        name: '', 
        type: 'local', 
        local_path: '/var/backups',
        host: '',
        port: 22,
        remote_path: '',
        username: 'root',
        auth_type: 'ssh_key',
        password: '',
        ssh_key: ''
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error creating server')
    }
  }

  const handleCreateJob = async () => {
    try {
      const filteredTargets = jobForm.targets.filter(t => t.trim() !== '')
      await createBackupJob({ ...jobForm, targets: filteredTargets })
      await loadData()
      setShowJobDialog(false)
      setJobForm({
        name: '',
        backup_type: 'system',
        targets: [''],
        schedule: '0 2 * * *',
        server_id: 0,
        retention_days: 30,
        compression: true,
        rsync_enabled: false,
        rsync_host: '',
        rsync_port: 22,
        rsync_user: 'root',
        rsync_path: '/backups',
        rsync_ssh_key: ''
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error creating job')
    }
  }

  const handleExecuteJob = async (jobId: number) => {
    try {
      await executeBackupJob(jobId)
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
        await deleteBackupServer(deleteTarget.id)
      } else {
        await deleteBackupJob(deleteTarget.id)
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
        <TabsList className="grid w-full grid-cols-2">
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
                  {serverForm.type === 'remote' && (
                    <>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label htmlFor="host">Host</Label>
                          <Input
                            id="host"
                            value={serverForm.host}
                            onChange={(e) => setServerForm(prev => ({ ...prev, host: e.target.value }))}
                            placeholder="backup.example.com"
                          />
                        </div>
                        <div>
                          <Label htmlFor="port">Port</Label>
                          <Input
                            id="port"
                            type="number"
                            value={serverForm.port}
                            onChange={(e) => setServerForm(prev => ({ ...prev, port: parseInt(e.target.value) || 22 }))}
                            placeholder="22"
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label htmlFor="username">Username</Label>
                          <Input
                            id="username"
                            value={serverForm.username}
                            onChange={(e) => setServerForm(prev => ({ ...prev, username: e.target.value }))}
                            placeholder="root"
                          />
                        </div>
                        <div>
                          <Label htmlFor="remote_path">Remote Path</Label>
                          <Input
                            id="remote_path"
                            value={serverForm.remote_path}
                            onChange={(e) => setServerForm(prev => ({ ...prev, remote_path: e.target.value }))}
                            placeholder="/backups"
                          />
                        </div>
                      </div>
                      <div>
                        <Label htmlFor="auth_type">Authentication Method</Label>
                        <Select
                          value={serverForm.auth_type}
                          onValueChange={(value) => setServerForm(prev => ({ ...prev, auth_type: value }))}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="ssh_key">SSH Key</SelectItem>
                            <SelectItem value="password">Password</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      {serverForm.auth_type === 'password' ? (
                        <div>
                          <Label htmlFor="password">Password</Label>
                          <Input
                            id="password"
                            type="password"
                            value={serverForm.password}
                            onChange={(e) => setServerForm(prev => ({ ...prev, password: e.target.value }))}
                            placeholder="Enter password"
                          />
                        </div>
                      ) : (
                        <div>
                          <Label htmlFor="ssh_key">SSH Private Key (optional)</Label>
                          <textarea
                            id="ssh_key"
                            value={serverForm.ssh_key}
                            onChange={(e) => setServerForm(prev => ({ ...prev, ssh_key: e.target.value }))}
                            placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;-----END RSA PRIVATE KEY-----"
                            className="w-full h-32 p-2 border rounded-md font-mono text-xs"
                          />
                          <p className="text-xs text-muted-foreground mt-1">
                            Paste your SSH private key or leave empty to use SSH agent
                          </p>
                        </div>
                      )}
                    </>
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
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {backupServers.map((server) => (
                  <TableRow key={server.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        {server.type === 'local' ? (
                          <HardDrive className="h-4 w-4" />
                        ) : (
                          <Server className="h-4 w-4" />
                        )}
                        {server.name}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{server.type}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{server.status}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">
                      {server.type === 'remote' ? server.host : server.local_path}
                    </TableCell>
                    <TableCell className="text-sm">{server.created}</TableCell>
                    <TableCell>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleDeleteClick('server', server.id, server.name)}
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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

                  {/* Rsync Remote Sync Configuration */}
                  <div className="space-y-4 border-t pt-4">
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="rsync_enabled"
                        checked={jobForm.rsync_enabled}
                        onChange={(e) => setJobForm(prev => ({ ...prev, rsync_enabled: e.target.checked }))}
                        className="rounded"
                      />
                      <Label htmlFor="rsync_enabled" className="cursor-pointer">
                        Sync backup to remote server via rsync after creation
                      </Label>
                    </div>

                    {jobForm.rsync_enabled && (
                      <div className="space-y-4 pl-6 border-l-2 border-primary/20">
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <Label htmlFor="rsync_host">Remote Host</Label>
                            <Input
                              id="rsync_host"
                              value={jobForm.rsync_host}
                              onChange={(e) => setJobForm(prev => ({ ...prev, rsync_host: e.target.value }))}
                              placeholder="backup.example.com"
                            />
                          </div>
                          <div>
                            <Label htmlFor="rsync_port">SSH Port</Label>
                            <Input
                              id="rsync_port"
                              type="number"
                              value={jobForm.rsync_port}
                              onChange={(e) => setJobForm(prev => ({ ...prev, rsync_port: parseInt(e.target.value) || 22 }))}
                              placeholder="22"
                            />
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <Label htmlFor="rsync_user">Remote User</Label>
                            <Input
                              id="rsync_user"
                              value={jobForm.rsync_user}
                              onChange={(e) => setJobForm(prev => ({ ...prev, rsync_user: e.target.value }))}
                              placeholder="root"
                            />
                          </div>
                          <div>
                            <Label htmlFor="rsync_path">Remote Path</Label>
                            <Input
                              id="rsync_path"
                              value={jobForm.rsync_path}
                              onChange={(e) => setJobForm(prev => ({ ...prev, rsync_path: e.target.value }))}
                              placeholder="/backups"
                            />
                          </div>
                        </div>
                        <div>
                          <Label htmlFor="rsync_ssh_key">SSH Private Key Path (optional)</Label>
                          <Input
                            id="rsync_ssh_key"
                            value={jobForm.rsync_ssh_key}
                            onChange={(e) => setJobForm(prev => ({ ...prev, rsync_ssh_key: e.target.value }))}
                            placeholder="/root/.ssh/id_rsa"
                          />
                          <p className="text-xs text-muted-foreground mt-1">
                            Leave empty to use SSH agent or default key
                          </p>
                        </div>
                      </div>
                    )}
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
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Schedule</TableHead>
                  <TableHead>Server</TableHead>
                  <TableHead>Last Run</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {backupJobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4" />
                        {job.name}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{job.backup_type}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{job.status}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">{job.schedule}</TableCell>
                    <TableCell className="text-sm">{getServerName(job.server_id)}</TableCell>
                    <TableCell className="text-sm">{job.last_run || 'Never'}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
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
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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
