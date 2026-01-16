"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { LayoutGrid, List as ListIcon, Play, Square, Plus, Trash2, Pencil, Save, Monitor } from "lucide-react"
import { NotificationContainer } from "@/components/ui/notification"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { apiUrl, getAuthHeaders } from "@/lib/api"

export function VirtualMachines() {
  interface VMData {
    id: number
    name: string
    status: string
    cpu: number
    memory: number
    iso: string
    disks: string[]
    created: string
    autostart?: boolean
    network_bridge?: string
  }

  const [vms, setVms] = useState<VMData[]>([])
  const [isos, setIsos] = useState<string[]>([])
  const [drives, setDrives] = useState<Array<{device: string, mountpoint: string, mounted: boolean, name: string}>>([])
  const [storagePath, setStoragePath] = useState<string>("")
  const [name, setName] = useState("")
  const [cpu, setCpu] = useState(1)
  const [memory, setMemory] = useState(2048)
  const maxCpu = 16
  const maxMemory = 32768
  const [systemCpuCores, setSystemCpuCores] = useState<number | null>(null)
  const [systemMemoryMB, setSystemMemoryMB] = useState<number | null>(null)
  const [iso, setIso] = useState("")
  const [disks, setDisks] = useState<number[]>([20])
  const [autostart, setAutostart] = useState(false)
  const [cloudInit, setCloudInit] = useState("")
  const [networkMode, setNetworkMode] = useState<"bridge" | "nat" | "none" | "unconfigured">("nat")
  const [bridgeInterface, setBridgeInterface] = useState<string>("")
  const [networkInterfaces, setNetworkInterfaces] = useState<string[]>([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<VMData | null>(null)
  const [view, setView] = useState<"grid" | "list">("list")
  const [success, setSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [consoleOpen, setConsoleOpen] = useState(false)
  const [consoleVm, setConsoleVm] = useState<string | null>(null)
  const [vncUrl, setVncUrl] = useState<string | null>(null)
  const [disksToRemove, setDisksToRemove] = useState<string[]>([])

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(apiUrl("/vms"))
        if (res.ok) {
          const data = await res.json()
          setVms(data)
        }
      } catch (e) {
        console.error(e)
      }
    }
    load()
    const id = setInterval(load, 4000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const loadMetrics = async () => {
      try {
        const res = await fetch(apiUrl("/metrics"), { headers: getAuthHeaders() })
        if (res.ok) {
          const data = await res.json()
          if (data?.cpu?.cores) setSystemCpuCores(data.cpu.cores)
          if (data?.memory?.total) setSystemMemoryMB(Math.round(data.memory.total * 1024))
        }
      } catch (e) {
        console.error(e)
      }
    }
    loadMetrics()
    const id = setInterval(loadMetrics, 10000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const loadIsos = async () => {
      try {
        const res = await fetch(apiUrl("/isos"))
        if (res.ok) {
          const data = await res.json()
          setIsos(data.isos.map((i: { name: string }) => i.name))
        }
      } catch (e) {
        console.error(e)
      }
    }
    loadIsos()
  }, [])

  useEffect(() => {
    const loadDrives = async () => {
      try {
        const res = await fetch(apiUrl("/drives"))
        if (res.ok) {
          const data = await res.json()
          // Filter only mounted drives
          const mountedDrives = (data.drives || []).filter((d: { mounted: boolean, mountpoint: string }) => 
            d.mounted && d.mountpoint && d.mountpoint !== "/"
          )
          setDrives(mountedDrives)
        }
      } catch (e) {
        console.error(e)
      }
    }
    loadDrives()
  }, [])

  useEffect(() => {
    const loadInterfaces = async () => {
      try {
        const res = await fetch(apiUrl("/network/interfaces"))
        if (res.ok) {
          const data = await res.json()
          // Filter physical interfaces (exclude lo, docker, virbr, veth, etc.)
          const physical = (data.interfaces || [])
            .filter((iface: { name: string }) => 
              !iface.name.startsWith('lo') && 
              !iface.name.startsWith('docker') && 
              !iface.name.startsWith('virbr') && 
              !iface.name.startsWith('veth') &&
              !iface.name.startsWith('lxc')
            )
            .map((iface: { name: string }) => iface.name)
          setNetworkInterfaces(physical)
          if (physical.length > 0) setBridgeInterface(physical[0])
        }
      } catch (e) {
        console.error(e)
      }
    }
    loadInterfaces()
  }, [])



  const handleSave = async () => {
    setSuccess(null)
    setError(null)
    const payload = editing
      ? { cpu, memory, iso, add_disks: disks, autostart, remove_disks: disksToRemove, network_mode: networkMode, bridge_interface: bridgeInterface, storage_path: storagePath || undefined }
      : { name, cpu, memory, iso, disks, autostart, cloud_init: cloudInit, network_mode: networkMode, bridge_interface: bridgeInterface, storage_path: storagePath || undefined }
    const target = editing ? `/vms/${editing.name}` : "/vms"
    const method = editing ? "PATCH" : "POST"
    const vmName = editing ? editing.name : name
    try {
      const res = await fetch(apiUrl(target), {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
      if (res.ok) {
        // Reload VM list to get fresh data
        const refreshRes = await fetch(apiUrl("/vms"))
        if (refreshRes.ok) {
          const allVms = await refreshRes.json()
          setVms(allVms)
        }
        setOpen(false)
        setEditing(null)
        setSuccess(`VM ${vmName} ${editing ? "updated" : "created"}`)
      } else {
        const data = await res.json().catch(() => null)
        setError(data?.detail || "Error saving VM")
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
      else setError("Failed to save VM")
    }
  }

  const handleStart = async (name: string) => {
    try {
      const res = await fetch(apiUrl(`/vms/${name}/start`), { method: "POST" })
      if (res.ok) {
        setVms(prev => prev.map(vm => vm.name === name ? { ...vm, status: "running" } : vm))
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleStop = async (name: string) => {
    try {
      const res = await fetch(apiUrl(`/vms/${name}/shutdown`), { method: "POST" })
      if (res.ok) {
        // Force immediate status update
        setVms(prev => prev.map(vm => vm.name === name ? { ...vm, status: "stopped" } : vm))
        // Reload to get actual status
        setTimeout(async () => {
          const refreshRes = await fetch(apiUrl("/vms"))
          if (refreshRes.ok) {
            const data = await refreshRes.json()
            setVms(data)
          }
        }, 3000)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleDelete = async (name: string) => {
    try {
      const res = await fetch(apiUrl(`/vms/${name}`), { method: "DELETE" })
      if (res.ok) {
        setVms(prev => prev.filter(vm => vm.name !== name))
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleConsole = async (name: string) => {
    try {
      const res = await fetch(apiUrl(`/vms/${name}/vnc`))
      if (res.ok) {
        // Use websockify proxy on port 6080 with noVNC from public/novnc/
        const url = `/novnc/vnc.html?host=${window.location.hostname}&port=6080&path=websockify&autoconnect=true&resize=scale`
        setVncUrl(url)
        setConsoleVm(name)
        setConsoleOpen(true)
      } else {
        setError("VM is not running or VNC not configured")
      }
    } catch (e) {
      console.error(e)
      setError("Failed to connect to console")
    }
  }

  const openEdit = (vm: VMData) => {
    setEditing(vm)
    setName(vm.name)
    setCpu(vm.cpu)
    setMemory(vm.memory)
    setIso(vm.iso)
    // Start with empty array - only new disks to be added
    setDisks([])
    setDisksToRemove([])
    setAutostart(!!vm.autostart)
    setCloudInit("")
    setStoragePath("")
    // Determine network mode from network_bridge
    const mode = vm.network_bridge === "virbr0" ? "nat" : vm.network_bridge === "none" ? "none" : "bridge"
    setNetworkMode(mode)
    if (mode === "bridge" && vm.network_bridge) {
      setBridgeInterface(vm.network_bridge)
    }
    setOpen(true)
  }

  const statusClass = (status: string) =>
    status === "running" ? "bg-green-600 text-white" : status === "stopped" ? "bg-red-600 text-white" : "bg-gray-600 text-white"

  return (
    <div className="space-y-6">
      <NotificationContainer success={success} error={error} onClearSuccess={() => setSuccess(null)} onClearError={() => setError(null)} />
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Virtual Machines</h2>
          <p className="text-muted-foreground">Manage your virtual machines</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant={view === "grid" ? "secondary" : "outline"} size="icon" onClick={() => setView("grid")}> <LayoutGrid className="h-4 w-4" /></Button>
          <Button variant={view === "list" ? "secondary" : "outline"} size="icon" onClick={() => setView("list")}> <ListIcon className="h-4 w-4" /></Button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button onClick={() => { setEditing(null); setName(""); setCpu(1); setMemory(2048); setIso(""); setDisks([20]); setAutostart(false); setCloudInit(""); setNetworkMode("nat"); setBridgeInterface(networkInterfaces[0] || ""); setStoragePath(""); setOpen(true) }}>
                <Plus className="mr-2 h-4 w-4" /> Create VM
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>{editing ? `Edit ${editing.name}` : "Create New VM"}</DialogTitle>
                <DialogDescription>{editing ? "Update virtual machine settings" : "Configure your new virtual machine"}</DialogDescription>
              </DialogHeader>
              <Tabs defaultValue="basic" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="basic">Basics</TabsTrigger>
                  <TabsTrigger value="resources">Resources</TabsTrigger>
                  <TabsTrigger value="storage">Storage</TabsTrigger>
                </TabsList>
                <TabsContent value="basic" className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="vm-name">VM Name</Label>
                    <Input id="vm-name" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. ubuntu-vm" disabled={!!editing} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="vm-iso">ISO Image</Label>
                    <Select value={iso} onValueChange={setIso}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select ISO" />
                      </SelectTrigger>
                      <SelectContent>
                        {isos.map(i => (
                          <SelectItem key={i} value={i}>{i}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="vm-autostart">Autostart</Label>
                    <div className="flex items-center gap-2">
                      <input id="vm-autostart" type="checkbox" checked={autostart} onChange={e => setAutostart(e.target.checked)} />
                      <span className="text-sm text-muted-foreground">Start VM automatically on host boot</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="vm-network">Network</Label>
                    <Select value={networkMode} onValueChange={(v) => setNetworkMode(v as "bridge" | "nat" | "none" | "unconfigured")}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select network mode" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="nat">NAT (virbr0)</SelectItem>
                        <SelectItem value="bridge">Bridge (Direct)</SelectItem>
                        <SelectItem value="unconfigured">Unconfigured Interface</SelectItem>
                        <SelectItem value="none">No Network</SelectItem>
                      </SelectContent>
                    </Select>
                    {networkMode === "bridge" && (
                      <div className="mt-2">
                        <Label htmlFor="bridge-interface">Network Interface</Label>
                        <Select value={bridgeInterface} onValueChange={setBridgeInterface}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select interface" />
                          </SelectTrigger>
                          <SelectContent>
                            {networkInterfaces.map(iface => (
                              <SelectItem key={iface} value={iface}>{iface}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}
                    <p className="text-xs text-muted-foreground">
                      NAT: Internet access via host NAT | Bridge: Direct network access | Unconfigured: Manual network setup required | None: No network
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="vm-cloudinit">Cloud-Init (user-data)</Label>
                    <textarea id="vm-cloudinit" className="w-full border rounded p-2 text-sm" rows={6} value={cloudInit} onChange={e => setCloudInit(e.target.value)} placeholder="#cloud-config\nusers: ..." />
                  </div>
                </TabsContent>
                <TabsContent value="resources" className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="vm-cpu">CPU Cores: {cpu}</Label>
                      <input
                        id="vm-cpu"
                        type="range"
                        min={1}
                        max={systemCpuCores || maxCpu}
                        step={1}
                        className="w-full"
                        value={cpu}
                        onChange={e => setCpu(parseInt(e.target.value))}
                      />
                      <div className="text-sm text-muted-foreground">Available cores: {systemCpuCores ?? 'unknown'}</div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="vm-memory">RAM (MB): {memory}</Label>
                      <input
                        id="vm-memory"
                        type="range"
                        min={512}
                        max={systemMemoryMB || maxMemory}
                        step={256}
                        className="w-full"
                        value={memory}
                        onChange={e => setMemory(parseInt(e.target.value))}
                      />
                      <div className="text-sm text-muted-foreground">
                        Total system RAM: {systemMemoryMB ? `${systemMemoryMB} MB` : 'unknown'}
                      </div>
                    </div>
                  </div>
                </TabsContent>
                <TabsContent value="storage" className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="vm-storage-path">Storage Location</Label>
                    <Select value={storagePath || "default"} onValueChange={(val) => setStoragePath(val === "default" ? "" : val)}>
                      <SelectTrigger>
                        <SelectValue placeholder="Default (/var/lib/libvirt/images)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="default">Default (/var/lib/libvirt/images)</SelectItem>
                        {drives.map(drive => (
                          <SelectItem key={drive.device} value={drive.mountpoint}>
                            {drive.name} - {drive.mountpoint}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {storagePath 
                        ? `VM disks will be stored in ${storagePath}/vms/${name || editing?.name || '[vm-name]'}/` 
                        : "VM disks will be stored in /var/lib/libvirt/images/"}
                    </p>
                  </div>
                  {editing && editing.disks && editing.disks.length > 0 && (
                    <div className="space-y-2">
                      <Label>Existing Disks</Label>
                      {editing.disks.filter(disk => !disksToRemove.includes(disk)).map((disk) => (
                        <div key={disk} className="flex space-x-2 items-center">
                          <Input 
                            type="text" 
                            value={disk.split('/').pop() || disk} 
                            disabled 
                            className="flex-1"
                          />
                          <Button 
                            variant="destructive" 
                            size="icon" 
                            onClick={() => setDisksToRemove([...disksToRemove, disk])}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                  {!editing && <Label>Disks (GB)</Label>}
                  {editing && <Label>Add New Disks (GB)</Label>}
                  {disks.map((d, idx) => (
                    <div key={idx} className="flex space-x-2 items-center">
                      <Input type="number" value={d || 20} onChange={e => { const arr = [...disks]; arr[idx] = parseInt(e.target.value) || 0; setDisks(arr) }} placeholder="Size in GB" />
                      <Button variant="outline" size="icon" onClick={() => setDisks(disks.filter((_, i) => i !== idx))}>-</Button>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" onClick={() => setDisks([...disks, 20])}>Add disk</Button>
                </TabsContent>
              </Tabs>
              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => { setOpen(false); setEditing(null) }}>Cancel</Button>
                <Button onClick={handleSave}>
                  {editing ? <><Save className="mr-2 h-4 w-4" />Save</> : <><Plus className="mr-2 h-4 w-4" />Create VM</>}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {view === "grid" ? (
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
          {vms.map(vm => (
            <Card key={vm.id} className="rounded-lg aspect-[4/3] flex flex-col">
              <CardHeader className="p-3 pb-2">
                <CardTitle className="flex items-center gap-2">
                  {vm.name}
                  <Badge className={statusClass(vm.status)}>
                    {vm.status === "running" ? "Running" : vm.status === "stopped" ? "Stopped" : vm.status}
                  </Badge>
                </CardTitle>
                <CardDescription>{vm.iso}</CardDescription>
              </CardHeader>
              <CardContent className="p-3 pt-0 flex-grow">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">CPU</span>
                    <div className="font-medium">{vm.cpu}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">RAM</span>
                    <div className="font-medium">{vm.memory} MB</div>
                  </div>
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Created</span>
                    <div className="font-medium">{vm.created}</div>
                  </div>
                </div>
              </CardContent>
              <div className="p-3 pt-0 mt-auto flex justify-end space-x-2">
                {vm.status === "running" ? (
                  <Button variant="destructive" size="icon" onClick={() => handleStop(vm.name)}>
                    <Square className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button className="bg-green-600 text-white hover:bg-green-700" size="icon" onClick={() => handleStart(vm.name)}>
                    <Play className="h-4 w-4" />
                  </Button>
                )}
                {vm.status === "running" && (
                  <Button variant="outline" size="icon" onClick={() => handleConsole(vm.name)}>
                    <Monitor className="h-4 w-4" />
                  </Button>
                )}
                <Button variant="outline" size="icon" onClick={() => openEdit(vm)}>
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button variant="destructive" size="icon" onClick={() => handleDelete(vm.name)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-0 pl-6 pr-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="font-normal">Name</TableHead>
                  <TableHead className="font-normal">Status</TableHead>
                  <TableHead className="font-normal">ISO</TableHead>
                  <TableHead className="font-normal">CPU</TableHead>
                  <TableHead className="font-normal">Memory</TableHead>
                  <TableHead className="font-normal">Created</TableHead>
                  <TableHead className="font-normal">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {vms.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center">
                      No virtual machines found
                    </TableCell>
                  </TableRow>
                ) : (
                  vms.map((vm) => (
                    <TableRow key={vm.id}>
                      <TableCell className="py-2">{vm.name}</TableCell>
                      <TableCell>
                        <Badge className={statusClass(vm.status)}>
                          {vm.status === "running" ? "Running" : vm.status === "stopped" ? "Stopped" : vm.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">{vm.iso}</TableCell>
                      <TableCell>{vm.cpu}</TableCell>
                      <TableCell>{vm.memory}</TableCell>
                      <TableCell className="text-sm">{vm.created}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {vm.status === "running" ? (
                            <Button variant="destructive" size="icon" onClick={() => handleStop(vm.name)}>
                              <Square className="h-4 w-4" />
                            </Button>
                          ) : (
                            <Button className="bg-green-600 text-white hover:bg-green-700" size="icon" onClick={() => handleStart(vm.name)}>
                              <Play className="h-4 w-4" />
                            </Button>
                          )}
                          {vm.status === "running" && (
                            <Button variant="outline" size="icon" onClick={() => handleConsole(vm.name)}>
                              <Monitor className="h-4 w-4" />
                            </Button>
                          )}
                          <Button variant="outline" size="icon" onClick={() => openEdit(vm)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="destructive" size="icon" onClick={() => handleDelete(vm.name)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* VNC Console Dialog */}
      <Dialog open={consoleOpen} onOpenChange={setConsoleOpen}>
        <DialogContent className="!max-w-[98vw] max-h-[98vh] w-[98vw] h-[98vh] p-0" style={{ maxWidth: '98vw', width: '98vw' }}>
          <DialogHeader className="px-6 pt-6 pb-2">
            <DialogTitle>Console - {consoleVm}</DialogTitle>
            <DialogDescription>Virtual Machine Console (VNC)</DialogDescription>
          </DialogHeader>
          <div className="w-full h-[calc(98vh-100px)] px-6 pb-6">
            {vncUrl && (
              <iframe
                src={vncUrl}
                className="w-full h-full border-0 rounded"
                title={`Console for ${consoleVm}`}
              />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
