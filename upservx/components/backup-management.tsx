"use client"

import { useState, useEffect } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Server, Plus, Loader2, AlertCircle, Play, Pause, Trash2, HardDrive, Clock, RotateCcw, ShieldCheck } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Progress } from "@/components/ui/progress"
import { apiUrl, getAuthHeaders } from "@/lib/api"
import type { BackupJobCreate, BackupServerCreate } from "@/lib/generated-api-types"
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

type DefinedForm<T, K extends keyof T> = {
  [P in K]-?: NonNullable<T[P]>
}

type BackupServerForm = DefinedForm<
  BackupServerCreate,
  'name' | 'type' | 'host' | 'port' | 'remote_path' | 'local_path' |
  'auth_type' | 'username' | 'password' | 'ssh_key'
>

type BackupJobForm = DefinedForm<BackupJobCreate, keyof BackupJobCreate>

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

interface BackupJobProgress {
  job_id: number
  status: 'idle' | 'queued' | 'running' | 'retry_wait' | 'cancel_requested' | 'completed' | 'failed' | 'cancelled'
  progress: number
  message: string
  updated_at?: string | null
}

interface BackupInstance {
  id: number
  job_id: number
  server_id: number
  backup_name: string
  backup_path: string
  backup_size: number
  backup_type: string
  status: 'in_progress' | 'completed' | 'failed'
  integrity_status?: string
  checksum_sha256?: string
  created: string
}

// Helper functions that use apiUrl at runtime, not at module load
async function fetchBackupServers(): Promise<BackupServer[]> {
  const response = await fetch(apiUrl('/backup/servers'), {
    method: 'GET',
    credentials: 'include',
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
    credentials: 'include',
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
    credentials: 'include',
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
    credentials: 'include',
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
    credentials: 'include',
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
  const response = await fetch(apiUrl(`/backup/jobs/${jobId}/trigger`), {
    method: 'POST',
    credentials: 'include',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json'
    }
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

async function fetchBackupJobProgress(jobId: number): Promise<BackupJobProgress> {
  const response = await fetch(apiUrl(`/backup/jobs/${jobId}/progress`), {
    method: 'GET',
    credentials: 'include',
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
    credentials: 'include',
    headers: {
      ...getAuthHeaders(),
      'Content-Type': 'application/json'
    }
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
}

async function setBackupJobStatus(id: number, status: 'active' | 'paused'): Promise<void> {
  const response = await fetch(apiUrl(`/backup/jobs/${id}`), {
    method: 'PUT',
    credentials: 'include',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ status })
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
}

async function fetchBackupInstances(): Promise<BackupInstance[]> {
  const response = await fetch(apiUrl('/backup/instances'), {
    credentials: 'include',
    headers: getAuthHeaders()
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
  return response.json()
}

async function restoreBackupInstance(id: number, restorePath: string): Promise<void> {
  const response = await fetch(apiUrl(`/backup/instances/${id}/restore`), {
    method: 'POST',
    credentials: 'include',
    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ restore_path: restorePath })
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP error! status: ${response.status}`)
  }
}

async function verifyBackupInstance(id: number): Promise<void> {
  const response = await fetch(apiUrl(`/backup/instances/${id}/verify`), {
    method: 'POST',
    credentials: 'include',
    headers: getAuthHeaders()
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
}

async function deleteBackupInstance(id: number): Promise<void> {
  const response = await fetch(apiUrl(`/backup/instances/${id}`), {
    method: 'DELETE',
    credentials: 'include',
    headers: getAuthHeaders()
  })
  if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
}

async function fetchVMs(): Promise<{ name: string; id: string }[]> {
  try {
    const response = await fetch(apiUrl('/vms'), {
      method: 'GET',
      credentials: 'include',
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
      credentials: 'include',
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
  const [backupInstances, setBackupInstances] = useState<BackupInstance[]>([])
  const [availableVMs, setAvailableVMs] = useState<{ name: string; id: string }[]>([])
  const [availableContainers, setAvailableContainers] = useState<{ name: string; id: string }[]>([])
  const [backupProgress, setBackupProgress] = useState<Record<number, BackupJobProgress>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const [showServerDialog, setShowServerDialog] = useState(false)
  const [showJobDialog, setShowJobDialog] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<{ type: 'server' | 'job' | 'instance', id: number, name: string } | null>(null)
  const [restoreTarget, setRestoreTarget] = useState<BackupInstance | null>(null)
  const [restorePath, setRestorePath] = useState('/var/lib/upservx/restores')
  
  const [serverForm, setServerForm] = useState<BackupServerForm>({
    name: '',
    type: 'local',
    local_path: '/var/lib/upservx/backups',
    host: '',
    port: 22,
    remote_path: '/backups',
    username: 'root',
    auth_type: 'ssh_key',
    password: '',
    ssh_key: ''
  })
  
  const [jobForm, setJobForm] = useState<BackupJobForm>({
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

  useEffect(() => {
    if (backupJobs.length === 0) {
      setBackupProgress({})
      return
    }

    let isActive = true

    const loadProgress = async () => {
      const entries = await Promise.all(
        backupJobs.map(async (job) => {
          try {
            const progress = await fetchBackupJobProgress(job.id)
            return [job.id, progress] as const
          } catch {
            return null
          }
        })
      )

      if (!isActive) return

      const next: Record<number, BackupJobProgress> = {}
      entries.forEach((entry) => {
        if (entry) {
          next[entry[0]] = entry[1]
        }
      })
      setBackupProgress(next)
    }

    loadProgress()
    const timer = setInterval(loadProgress, 2000)

    return () => {
      isActive = false
      clearInterval(timer)
    }
  }, [backupJobs])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [serversData, jobsData, instancesData, vmsData, containersData] = await Promise.all([
        fetchBackupServers(),
        fetchBackupJobs(),
        fetchBackupInstances(),
        fetchVMs(),
        fetchContainers()
      ])
      
      setBackupServers(serversData)
      setBackupJobs(jobsData)
      setBackupInstances(instancesData)
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
        local_path: '/var/lib/upservx/backups',
        host: '',
        port: 22,
        remote_path: '/backups',
        username: 'root',
        auth_type: 'ssh_key',
        password: '',
        ssh_key: ''
      })
      await loadData()
      setShowServerDialog(false)
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
        compression: true
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error creating job')
    }
  }

  const handleExecuteJob = async (jobId: number) => {
    try {
      setBackupProgress((prev) => ({
        ...prev,
        [jobId]: {
          job_id: jobId,
          status: 'running',
          progress: 1,
          message: 'Backup started',
        },
      }))
      await executeBackupJob(jobId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error executing job')
    }
  }

  const handleToggleJob = async (job: BackupJob) => {
    try {
      await setBackupJobStatus(job.id, job.status === 'active' ? 'paused' : 'active')
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error updating job schedule')
    }
  }

  const handleDeleteClick = (type: 'server' | 'job' | 'instance', id: number, name: string) => {
    setDeleteTarget({ type, id, name })
    setShowDeleteDialog(true)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    
    try {
      if (deleteTarget.type === 'server') {
        await deleteBackupServer(deleteTarget.id)
      } else if (deleteTarget.type === 'job') {
        await deleteBackupJob(deleteTarget.id)
      } else {
        await deleteBackupInstance(deleteTarget.id)
      }
      await loadData()
      setShowDeleteDialog(false)
      setDeleteTarget(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error deleting')
    }
  }

  const handleRestore = async () => {
    if (!restoreTarget || !restorePath.startsWith('/')) return
    try {
      await restoreBackupInstance(restoreTarget.id, restorePath)
      setRestoreTarget(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error queueing restore')
    }
  }

  const handleVerify = async (id: number) => {
    try {
      await verifyBackupInstance(id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error queueing verification')
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
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="servers" className="flex items-center gap-2">
            <Server className="h-4 w-4" />
            Backup Servers
          </TabsTrigger>
          <TabsTrigger value="jobs" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Backup Jobs
          </TabsTrigger>
          <TabsTrigger value="instances" className="flex items-center gap-2">
            <HardDrive className="h-4 w-4" />
            Backup Archives
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
                      onValueChange={(value: 'local' | 'remote') => setServerForm(prev => ({ ...prev, type: value }))}
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
                        placeholder="/var/lib/upservx/backups"
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
                          onValueChange={(value: 'password' | 'ssh_key') => setServerForm(prev => ({ ...prev, auth_type: value }))}
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
                          <Label htmlFor="ssh_key">SSH Private Key</Label>
                          <textarea
                            id="ssh_key"
                            value={serverForm.ssh_key}
                            onChange={(e) => setServerForm(prev => ({ ...prev, ssh_key: e.target.value }))}
                            placeholder="-----BEGIN OPENSSH PRIVATE KEY-----&#10;...&#10;-----END OPENSSH PRIVATE KEY-----"
                            className="w-full h-32 p-2 border rounded-md font-mono text-xs"
                          />
                          <p className="text-xs text-muted-foreground mt-1">
                            Paste the private key used by the background backup worker.
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
              <TableHeader className="sticky top-0 bg-background/80 backdrop-blur border-b">
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
                  <TableRow key={server.id} className="hover:bg-muted/40">
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
                      <Badge className={server.status === "connected" ? "bg-green-600 text-white" : server.status === "error" ? "bg-red-600 text-white" : "bg-gray-600 text-white"}>
                        {server.status}
                      </Badge>
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

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label htmlFor="retention_days">Retention (days)</Label>
                      <Input
                        id="retention_days"
                        type="number"
                        min="0"
                        value={jobForm.retention_days}
                        onChange={(e) => setJobForm(prev => ({ ...prev, retention_days: Math.max(0, parseInt(e.target.value) || 0) }))}
                      />
                    </div>
                    <div className="flex items-end pb-2">
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={jobForm.compression}
                          onChange={(e) => setJobForm(prev => ({ ...prev, compression: e.target.checked }))}
                        />
                        Compress archive with gzip
                      </label>
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
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Progress</TableHead>
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
                      <Badge className={job.status === "active" ? "bg-green-600 text-white" : job.status === "error" ? "bg-red-600 text-white" : "bg-gray-600 text-white"}>
                        {job.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="min-w-56">
                      {backupProgress[job.id] && backupProgress[job.id].status !== 'idle' ? (
                        <div className="space-y-1">
                          <Progress value={backupProgress[job.id].progress} />
                          <div className="text-xs text-muted-foreground">
                            {backupProgress[job.id].progress}% - {backupProgress[job.id].message}
                          </div>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm">{job.schedule}</TableCell>
                    <TableCell className="text-sm">{getServerName(job.server_id)}</TableCell>
                    <TableCell className="text-sm">{job.last_run || 'Never'}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button variant="outline" size="sm" onClick={() => handleExecuteJob(job.id)}>
                          <Play className="h-4 w-4" />
                        </Button>
                        <Button variant="outline" size="sm" title={job.status === 'active' ? 'Pause schedule' : 'Activate schedule'} onClick={() => handleToggleJob(job)}>
                          {job.status === 'active' ? <Pause className="h-4 w-4" /> : <Clock className="h-4 w-4" />}
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

        <TabsContent value="instances" className="space-y-4">
          <h3 className="text-xl font-semibold">Backup Archives</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Integrity</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {backupInstances.map((instance) => (
                <TableRow key={instance.id}>
                  <TableCell className="font-medium">{instance.backup_name}</TableCell>
                  <TableCell><Badge variant="outline">{instance.backup_type}</Badge></TableCell>
                  <TableCell>{instance.status}</TableCell>
                  <TableCell>
                    <Badge className={instance.integrity_status === 'verified' ? 'bg-green-600 text-white' : 'bg-gray-600 text-white'}>
                      {instance.integrity_status || 'pending'}
                    </Badge>
                  </TableCell>
                  <TableCell>{(instance.backup_size / 1024 / 1024).toFixed(1)} MB</TableCell>
                  <TableCell>{instance.created}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="outline" size="sm" title="Verify and test restore" disabled={instance.status !== 'completed'} onClick={() => handleVerify(instance.id)}>
                        <ShieldCheck className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="sm" title="Restore" disabled={instance.status !== 'completed'} onClick={() => setRestoreTarget(instance)}>
                        <RotateCcw className="h-4 w-4" />
                      </Button>
                      <Button variant="outline" size="sm" title="Delete archive and metadata" className="text-red-600" onClick={() => handleDeleteClick('instance', instance.id, instance.backup_name)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TabsContent>
      </Tabs>

      <Dialog open={restoreTarget !== null} onOpenChange={(open) => !open && setRestoreTarget(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Restore {restoreTarget?.backup_name}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              The archive is checksum-verified before extraction. Existing files and links are never overwritten.
            </p>
            <div>
              <Label htmlFor="restore-path">Absolute restore destination</Label>
              <Input id="restore-path" value={restorePath} onChange={(event) => setRestorePath(event.target.value)} />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setRestoreTarget(null)}>Cancel</Button>
              <Button onClick={handleRestore} disabled={!restorePath.startsWith('/')}>Queue Restore</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {deleteTarget?.type === 'server' ? 'Delete Backup Server' : deleteTarget?.type === 'job' ? 'Delete Backup Job' : 'Delete Backup Archive'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Are you sure you want to delete <strong>&quot;{deleteTarget?.name}&quot;</strong>?
              {deleteTarget?.type === 'server' && (
                <span className="block mt-2 text-red-600">
                  This server cannot be deleted while backup jobs reference it.
                </span>
              )}
              {deleteTarget?.type === 'instance' && (
                <span className="block mt-2 text-red-600">The stored archive will be deleted before its metadata.</span>
              )}
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
                Cancel
              </Button>
              <Button variant="destructive" onClick={handleDeleteConfirm}>
                {deleteTarget?.type === 'server' ? 'Delete Server' : deleteTarget?.type === 'job' ? 'Delete Job' : 'Delete Archive'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
