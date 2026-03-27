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
import { LayoutGrid, List as ListIcon, Play, Square, Plus, Trash2, Pencil, Save, Monitor, Copy, Camera, RotateCcw, Download, Upload } from "lucide-react"
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
    vlan_id?: number
    graphics?: string
    cloud_init_iso?: string
    storage_path?: string
    cpu_usage?: number
    memory_usage?: number
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
  const [disks, setDisks] = useState<Array<{ size: number; format: "qcow2" | "raw" | "vmdk" }>>([{ size: 20, format: "qcow2" }])
  const [autostart, setAutostart] = useState(false)
  const [cloudInit, setCloudInit] = useState("")
  const [networkMode, setNetworkMode] = useState<"bridge" | "nat" | "none" | "unconfigured">("nat")
  const [bridgeInterface, setBridgeInterface] = useState<string>("")
  const [vlanId, setVlanId] = useState<number | "">("")
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
  const [duplicateOpen, setDuplicateOpen] = useState(false)
  const [duplicateVm, setDuplicateVm] = useState<VMData | null>(null)
  const [duplicateName, setDuplicateName] = useState("")
  const [snapshotOpen, setSnapshotOpen] = useState(false)
  const [snapshotVm, setSnapshotVm] = useState<VMData | null>(null)
  const [snapshots, setSnapshots] = useState<Array<{ name: string; created: string; state: string; description: string }>>([  ])
  const [newSnapshotName, setNewSnapshotName] = useState("")
  const [newSnapshotDesc, setNewSnapshotDesc] = useState("")
  const [snapshotLoading, setSnapshotLoading] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const [exportVm, setExportVm] = useState<VMData | null>(null)
  const [exportFormat, setExportFormat] = useState<"ova" | "ovf">("ova")
  const [exportLoading, setExportLoading] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importName, setImportName] = useState("")
  const [importNetworkMode, setImportNetworkMode] = useState<"nat" | "bridge" | "none" | "unconfigured">("nat")
  const [importBridgeInterface, setImportBridgeInterface] = useState("")
  const [importVlanId, setImportVlanId] = useState<number | "">("") 
  const [importAutostart, setImportAutostart] = useState(false)
  const [importStoragePath, setImportStoragePath] = useState("")
  const [importLoading, setImportLoading] = useState(false)

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
      ? { cpu, memory, iso, add_disks: disks, autostart, remove_disks: disksToRemove, network_mode: networkMode, bridge_interface: bridgeInterface, vlan_id: networkMode === "bridge" && vlanId !== "" ? vlanId : undefined, storage_path: storagePath || undefined }
      : { name, cpu, memory, iso, disks, autostart, cloud_init: cloudInit, network_mode: networkMode, bridge_interface: bridgeInterface, vlan_id: networkMode === "bridge" && vlanId !== "" ? vlanId : undefined, storage_path: storagePath || undefined }
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
        setVms(prev => prev.map(vm => vm.name === name ? { ...vm, status: "stopped" } : vm))
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

  const handleDuplicate = async () => {
    if (!duplicateVm || !duplicateName.trim()) return
    
    setSuccess(null)
    setError(null)
    
    try {
      const payload = {
        new_name: duplicateName,
        storage_path: duplicateVm.storage_path || undefined
      }
      
      const res = await fetch(apiUrl(`/vms/${duplicateVm.name}/clone`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
      
      if (res.ok) {
        const refreshRes = await fetch(apiUrl("/vms"))
        if (refreshRes.ok) {
          const allVms = await refreshRes.json()
          setVms(allVms)
        }
        setDuplicateOpen(false)
        setDuplicateVm(null)
        setDuplicateName("")
        setSuccess(`VM ${duplicateName} created as clone of ${duplicateVm.name}`)
      } else {
        const data = await res.json().catch(() => null)
        setError(data?.detail || "Error cloning VM")
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
      else setError("Failed to clone VM")
    }
  }

  const openDuplicate = (vm: VMData) => {
    setDuplicateVm(vm)
    setDuplicateName(`${vm.name}-copy`)
    setDuplicateOpen(true)
  }

  const loadSnapshots = async (vmName: string) => {
    try {
      const res = await fetch(apiUrl(`/vms/${vmName}/snapshots`), { headers: getAuthHeaders() })
      if (res.ok) setSnapshots(await res.json())
    } catch (e) {
      console.error(e)
    }
  }

  const openSnapshots = async (vm: VMData) => {
    setSnapshotVm(vm)
    setSnapshots([])
    setNewSnapshotName("")
    setNewSnapshotDesc("")
    setSnapshotOpen(true)
    await loadSnapshots(vm.name)
  }

  const handleCreateSnapshot = async () => {
    if (!snapshotVm || !newSnapshotName.trim()) return
    setSnapshotLoading(true)
    try {
      const res = await fetch(apiUrl(`/vms/${snapshotVm.name}/snapshots`), {
        method: "POST",
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ name: newSnapshotName.trim(), description: newSnapshotDesc }),
      })
      if (res.ok) {
        setNewSnapshotName("")
        setNewSnapshotDesc("")
        setSuccess("Snapshot created")
        await loadSnapshots(snapshotVm.name)
      } else {
        const err = await res.json().catch(() => null)
        setError(err?.detail || "Failed to create snapshot")
      }
    } catch (e) {
      setError("Network error")
    } finally {
      setSnapshotLoading(false)
    }
  }

  const handleDeleteSnapshot = async (snapshotName: string) => {
    if (!snapshotVm) return
    try {
      const res = await fetch(apiUrl(`/vms/${snapshotVm.name}/snapshots/${snapshotName}`), {
        method: "DELETE",
        headers: getAuthHeaders(),
      })
      if (res.ok) {
        setSuccess("Snapshot deleted")
        await loadSnapshots(snapshotVm.name)
      } else {
        const err = await res.json().catch(() => null)
        setError(err?.detail || "Failed to delete snapshot")
      }
    } catch (e) {
      setError("Network error")
    }
  }

  const handleRestoreSnapshot = async (snapshotName: string) => {
    if (!snapshotVm) return
    try {
      const res = await fetch(apiUrl(`/vms/${snapshotVm.name}/snapshots/${snapshotName}/restore`), {
        method: "POST",
        headers: getAuthHeaders(),
      })
      if (res.ok) {
        setSuccess(`Restored to snapshot "${snapshotName}"`)
        setSnapshotOpen(false)
      } else {
        const err = await res.json().catch(() => null)
        setError(err?.detail || "Failed to restore snapshot")
      }
    } catch (e) {
      setError("Network error")
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

  const openExport = (vm: VMData) => {
    setExportVm(vm)
    setExportFormat("ova")
    setExportOpen(true)
  }

  const handleExport = async () => {
    if (!exportVm) return
    setExportLoading(true)
    setSuccess(null)
    setError(null)
    try {
      const res = await fetch(apiUrl(`/vms/${exportVm.name}/export`), {
        method: "POST",
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ format: exportFormat }),
      })
      const data = await res.json().catch(() => null)
      if (res.ok && data?.filename) {
        // Trigger browser download
        const link = document.createElement("a")
        link.href = apiUrl(`/vms/exports/${encodeURIComponent(data.filename)}`)
        link.download = data.filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        setExportOpen(false)
        setSuccess(`VM "${exportVm.name}" exported as ${exportFormat.toUpperCase()} — download started`)
      } else {
        setError(data?.detail || "Export failed")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed")
    } finally {
      setExportLoading(false)
    }
  }

  const handleImport = async () => {
    if (!importFile || !importName.trim()) return
    setImportLoading(true)
    setSuccess(null)
    setError(null)
    try {
      const form = new FormData()
      form.append("file", importFile)
      form.append("name", importName.trim())
      form.append("network_mode", importNetworkMode)
      if (importNetworkMode === "bridge" && importBridgeInterface) {
        form.append("bridge_interface", importBridgeInterface)
        if (importVlanId !== "") form.append("vlan_id", String(importVlanId))
      }
      form.append("autostart", String(importAutostart))
      if (importStoragePath && importStoragePath !== "__default__") form.append("storage_path", importStoragePath)

      const res = await fetch(apiUrl("/vms/import"), {
        method: "POST",
        headers: getAuthHeaders(),
        body: form,
      })
      const data = await res.json().catch(() => null)
      if (res.ok) {
        const refreshRes = await fetch(apiUrl("/vms"), { headers: getAuthHeaders() })
        if (refreshRes.ok) setVms(await refreshRes.json())
        setImportOpen(false)
        setImportFile(null)
        setImportName("")
        setImportStoragePath("")
        setSuccess(`VM "${importName.trim()}" erfolgreich importiert`)
      } else {
        setError(data?.detail || "Import fehlgeschlagen")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import fehlgeschlagen")
    } finally {
      setImportLoading(false)
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
    const mode = vm.network_bridge === "virbr0" ? "nat" : vm.network_bridge === "none" ? "none" : vm.network_bridge === "unconfigured" ? "unconfigured" : "bridge"
    setNetworkMode(mode)
    if (mode === "bridge" && vm.network_bridge) {
      setBridgeInterface(vm.network_bridge)
    }
    setVlanId(vm.vlan_id ?? "")
    setOpen(true)
  }

  const statusClass = (status: string) =>
    status === "running" ? "bg-green-600 text-white" : status === "stopped" ? "bg-red-600 text-white" : "bg-gray-600 text-white"

  const getUsageColor = (usage: number | undefined) => {
    if (!usage) return "text-green-600"
    if (usage >= 86) return "text-red-600"
    if (usage >= 75) return "text-orange-600"
    return "text-green-600"
  }

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
          <Button variant="outline" onClick={() => { setImportFile(null); setImportName(""); setImportNetworkMode("nat"); setImportBridgeInterface(""); setImportVlanId(""); setImportAutostart(false); setImportStoragePath(""); setImportOpen(true) }}>
            <Upload className="mr-2 h-4 w-4" /> Import VM
          </Button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button onClick={() => { setEditing(null); setName(""); setCpu(1); setMemory(2048); setIso(""); setDisks([{ size: 20, format: "qcow2" }]); setAutostart(false); setCloudInit(""); setNetworkMode("nat"); setBridgeInterface(networkInterfaces[0] || ""); setVlanId(""); setStoragePath(""); setOpen(true) }}>
                <Plus className="mr-2 h-4 w-4" /> Create VM
              </Button>
            </DialogTrigger>
            <DialogContent className="overflow-y-auto" style={{ width: '70vw', maxWidth: '70vw', maxHeight: '90vh' }}>
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
                        <div className="mt-2">
                          <Label htmlFor="vlan-id">VLAN ID (optional)</Label>
                          <input
                            id="vlan-id"
                            type="number"
                            min={1}
                            max={4094}
                            placeholder="e.g. 100"
                            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            value={vlanId}
                            onChange={e => setVlanId(e.target.value === "" ? "" : parseInt(e.target.value))}
                          />
                          <p className="text-xs text-muted-foreground mt-1">Creates a VLAN sub-interface (e.g. eth0.100) and bridges to it</p>
                        </div>
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
                  {!editing && <Label>Disks</Label>}
                  {editing && <Label>Add New Disks</Label>}
                  {disks.map((d, idx) => (
                    <div key={idx} className="flex space-x-2 items-center">
                      <Input
                        type="number"
                        value={d.size || 20}
                        onChange={e => {
                          const arr = [...disks]
                          arr[idx] = { ...arr[idx], size: parseInt(e.target.value) || 0 }
                          setDisks(arr)
                        }}
                        placeholder="20"
                        className="w-24"
                      />
                      <span className="text-sm text-muted-foreground shrink-0">GB</span>
                      <Select
                        value={d.format}
                        onValueChange={(v) => {
                          const arr = [...disks]
                          arr[idx] = { ...arr[idx], format: v as "qcow2" | "raw" | "vmdk" }
                          setDisks(arr)
                        }}
                      >
                        <SelectTrigger className="flex-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="qcow2">qcow2 – Copy-on-write (recommended)</SelectItem>
                          <SelectItem value="raw">raw – Maximum performance</SelectItem>
                          <SelectItem value="vmdk">vmdk – VMware compatible</SelectItem>
                        </SelectContent>
                      </Select>
                      <Button variant="outline" size="icon" onClick={() => setDisks(disks.filter((_, i) => i !== idx))}>-</Button>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" onClick={() => setDisks([...disks, { size: 20, format: "qcow2" }])}>Add disk</Button>
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
                    <div className="font-medium">{vm.cpu} cores</div>
                    {vm.status === "running" && (
                      <div className={`text-xs font-semibold ${getUsageColor(vm.cpu_usage)}`}>{vm.cpu_usage?.toFixed(1) ?? 0}%</div>
                    )}
                  </div>
                  <div>
                    <span className="text-muted-foreground">RAM</span>
                    <div className="font-medium">{vm.memory} MB</div>
                    {vm.status === "running" && (
                      <div className={`text-xs font-semibold ${getUsageColor(vm.memory_usage)}`}>{vm.memory_usage?.toFixed(1) ?? 0}%</div>
                    )}
                  </div>
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Created</span>
                    <div className="font-medium text-xs">{vm.created}</div>
                  </div>
                </div>
              </CardContent>
              <div className="p-3 pt-0 mt-auto flex justify-end space-x-2">
                {vm.status === "running" ? (
                  <Button variant="destructive" size="icon" onClick={() => handleStop(vm.name)}>
                    <Square className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button variant="success" size="icon" onClick={() => handleStart(vm.name)}>
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
                <Button variant="outline" size="icon" onClick={() => openDuplicate(vm)}>
                  <Copy className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="icon" title="Snapshots" onClick={() => openSnapshots(vm)}>
                  <Camera className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="icon" title="Export OVA/OVF" onClick={() => openExport(vm)}>
                  <Download className="h-4 w-4" />
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
              <TableHeader className="sticky top-0 bg-background/80 backdrop-blur border-b">
                <TableRow>
                  <TableHead className="font-normal">Name</TableHead>
                  <TableHead className="font-normal">Status</TableHead>
                  <TableHead className="font-normal">CPU</TableHead>
                  <TableHead className="font-normal">Memory</TableHead>
                  <TableHead className="font-normal">CPU Usage</TableHead>
                  <TableHead className="font-normal">Memory Usage</TableHead>
                  <TableHead className="font-normal">Created</TableHead>
                  <TableHead className="font-normal">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {vms.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center">
                      No virtual machines found
                    </TableCell>
                  </TableRow>
                ) : (
                  vms.map((vm) => (
                    <TableRow key={vm.id} className="hover:bg-muted/40">
                      <TableCell className="py-2">{vm.name}</TableCell>
                      <TableCell>
                        <Badge className={statusClass(vm.status)}>
                          {vm.status === "running" ? "Running" : vm.status === "stopped" ? "Stopped" : vm.status}
                        </Badge>
                      </TableCell>
                      <TableCell>{vm.cpu}</TableCell>
                      <TableCell>{vm.memory} MB</TableCell>
                      <TableCell className={vm.status === "running" ? getUsageColor(vm.cpu_usage) : ""}>
                        <span className="font-semibold">{vm.status === "running" ? `${vm.cpu_usage?.toFixed(1) ?? 0}%` : "-"}</span>
                      </TableCell>
                      <TableCell className={vm.status === "running" ? getUsageColor(vm.memory_usage) : ""}>
                        <span className="font-semibold">{vm.status === "running" ? `${vm.memory_usage?.toFixed(1) ?? 0}%` : "-"}</span>
                      </TableCell>
                      <TableCell className="text-sm">{vm.created}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {vm.status === "running" ? (
                            <Button variant="destructive" size="icon" onClick={() => handleStop(vm.name)}>
                              <Square className="h-4 w-4" />
                            </Button>
                          ) : (
                            <Button variant="success" size="icon" onClick={() => handleStart(vm.name)}>
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
                          <Button variant="outline" size="icon" onClick={() => openDuplicate(vm)}>
                            <Copy className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" size="icon" title="Snapshots" onClick={() => openSnapshots(vm)}>
                            <Camera className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" size="icon" title="Export OVA/OVF" onClick={() => openExport(vm)}>
                            <Download className="h-4 w-4" />
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

      {/* Snapshot Dialog */}
      <Dialog open={snapshotOpen} onOpenChange={setSnapshotOpen}>
        <DialogContent style={{ width: '60vw', maxWidth: '60vw', maxHeight: '85vh' }} className="overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Snapshots — {snapshotVm?.name}</DialogTitle>
            <DialogDescription>Create, restore or delete disk snapshots. Requires qcow2 disk format.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {/* Create new snapshot */}
            <div className="space-y-2 border rounded p-3">
              <Label className="font-semibold">New Snapshot</Label>
              <Input
                value={newSnapshotName}
                onChange={e => setNewSnapshotName(e.target.value)}
                placeholder="Snapshot name (e.g. before-update)"
              />
              <Input
                value={newSnapshotDesc}
                onChange={e => setNewSnapshotDesc(e.target.value)}
                placeholder="Description (optional)"
              />
              <Button onClick={handleCreateSnapshot} disabled={snapshotLoading || !newSnapshotName.trim()} size="sm">
                <Camera className="mr-2 h-4 w-4" />
                {snapshotLoading ? "Creating…" : "Create Snapshot"}
              </Button>
            </div>
            {/* Snapshot list */}
            <div className="space-y-2">
              <Label className="font-semibold">Existing Snapshots</Label>
              {snapshots.length === 0 ? (
                <p className="text-sm text-muted-foreground">No snapshots found.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>State</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {snapshots.map(snap => (
                      <TableRow key={snap.name}>
                        <TableCell className="font-mono text-sm">{snap.name}</TableCell>
                        <TableCell>{snap.state}</TableCell>
                        <TableCell className="text-sm">{snap.created}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">{snap.description}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button variant="outline" size="icon" title="Restore" onClick={() => handleRestoreSnapshot(snap.name)}>
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                            <Button variant="destructive" size="icon" title="Delete" onClick={() => handleDeleteSnapshot(snap.name)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Import VM Dialog */}
      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent style={{ width: '60vw', maxWidth: '60vw' }} className="overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Import Virtual Machine</DialogTitle>
            <DialogDescription>
              Import a VM from an OVA or OVF file. Disks will be converted from VMDK to qcow2.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="import-file">OVA / OVF File</Label>
              <input
                id="import-file"
                type="file"
                accept=".ova,.ovf"
                className="block w-full text-sm text-muted-foreground file:mr-4 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-muted file:text-foreground hover:file:bg-muted/80 cursor-pointer"
                onChange={e => {
                  const f = e.target.files?.[0] ?? null
                  setImportFile(f)
                  if (f && !importName) {
                    // Pre-fill name from filename without extension
                    setImportName(f.name.replace(/\.(ova|ovf)$/i, "").replace(/[^a-zA-Z0-9_-]/g, "-").slice(0, 40))
                  }
                }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="import-name">VM Name</Label>
              <Input
                id="import-name"
                value={importName}
                onChange={e => setImportName(e.target.value)}
                placeholder="e.g. my-imported-vm"
              />
            </div>
            <div className="space-y-2">
              <Label>Network</Label>
              <Select value={importNetworkMode} onValueChange={v => setImportNetworkMode(v as typeof importNetworkMode)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="nat">NAT (virbr0)</SelectItem>
                  <SelectItem value="bridge">Bridge (Direct)</SelectItem>
                  <SelectItem value="unconfigured">Unconfigured Interface</SelectItem>
                  <SelectItem value="none">No Network</SelectItem>
                </SelectContent>
              </Select>
              {importNetworkMode === "bridge" && (
                <div className="mt-2">
                  <Label>Bridge Interface</Label>
                  <Select value={importBridgeInterface} onValueChange={setImportBridgeInterface}>
                    <SelectTrigger><SelectValue placeholder="Select interface" /></SelectTrigger>
                    <SelectContent>
                      {networkInterfaces.map(iface => (
                        <SelectItem key={iface} value={iface}>{iface}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="mt-2">
                    <Label>VLAN ID (optional)</Label>
                    <input
                      type="number"
                      min={1}
                      max={4094}
                      placeholder="e.g. 100"
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      value={importVlanId}
                      onChange={e => setImportVlanId(e.target.value === "" ? "" : parseInt(e.target.value))}
                    />
                    <p className="text-xs text-muted-foreground mt-1">Creates a VLAN sub-interface (e.g. eth0.100) and bridges to it</p>
                  </div>
                </div>
              )}
            </div>
            {drives.length > 0 && (
              <div className="space-y-2">
                <Label>Storage (optional)</Label>
                <Select value={importStoragePath} onValueChange={setImportStoragePath}>
                  <SelectTrigger><SelectValue placeholder="Default (/var/lib/libvirt/images)" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__default__">Default (/var/lib/libvirt/images)</SelectItem>
                    {drives.map(d => (
                      <SelectItem key={d.mountpoint} value={d.mountpoint}>{d.name || d.device} – {d.mountpoint}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="flex items-center gap-2">
              <input id="import-autostart" type="checkbox" checked={importAutostart} onChange={e => setImportAutostart(e.target.checked)} />
              <Label htmlFor="import-autostart" className="cursor-pointer">Autostart on host boot</Label>
            </div>
            <div className="text-sm text-muted-foreground rounded border p-3 space-y-1">
              <p className="font-medium">Note:</p>
              <ul className="list-disc list-inside pl-2 space-y-0.5">
                <li>VMDK disks will be converted to qcow2 – this may take several minutes</li>
                <li>CPU and RAM settings are read from the OVF descriptor</li>
                <li>The VM will be registered with libvirt and appear in stopped state</li>
              </ul>
            </div>
          </div>
          <div className="flex justify-end space-x-2">
            <Button variant="outline" onClick={() => setImportOpen(false)} disabled={importLoading}>Cancel</Button>
            <Button onClick={handleImport} disabled={importLoading || !importFile || !importName.trim()}>
              <Upload className="mr-2 h-4 w-4" />
              {importLoading ? "Importing…" : "Import VM"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Export VM Dialog */}
      <Dialog open={exportOpen} onOpenChange={setExportOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Export Virtual Machine</DialogTitle>
            <DialogDescription>
              Export <strong>{exportVm?.name}</strong> as OVA or OVF. The VM must be stopped.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Export Format</Label>
              <Select value={exportFormat} onValueChange={(v) => setExportFormat(v as "ova" | "ovf")}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ova">OVA – single archive (recommended)</SelectItem>
                  <SelectItem value="ovf">OVF – directory with OVF + VMDKs</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="text-sm text-muted-foreground space-y-1 rounded border p-3">
              <p className="font-medium">What happens:</p>
              <ul className="list-disc list-inside pl-2 space-y-0.5">
                <li>Disks are converted from qcow2 to VMDK</li>
                <li>An OVF descriptor is generated with CPU/RAM config</li>
                {exportFormat === "ova" && <li>Everything is packaged into a single <code>.ova</code> TAR archive</li>}
                {exportFormat === "ovf" && <li>Files are placed in a directory on the server</li>}
                <li>The download starts automatically when ready</li>
              </ul>
              <p className="mt-2 text-xs text-orange-500 font-medium">Note: Disk conversion may take several minutes depending on disk size.</p>
            </div>
          </div>
          <div className="flex justify-end space-x-2">
            <Button variant="outline" onClick={() => setExportOpen(false)} disabled={exportLoading}>Cancel</Button>
            <Button onClick={handleExport} disabled={exportLoading}>
              <Download className="mr-2 h-4 w-4" />
              {exportLoading ? "Exporting…" : `Export as ${exportFormat.toUpperCase()}`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Duplicate VM Dialog */}
      <Dialog open={duplicateOpen} onOpenChange={setDuplicateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Duplicate Virtual Machine</DialogTitle>
            <DialogDescription>
              Create a complete clone of {duplicateVm?.name} including all disk data
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="duplicate-name">New VM Name</Label>
              <Input
                id="duplicate-name"
                value={duplicateName}
                onChange={(e) => setDuplicateName(e.target.value)}
                placeholder="Enter new VM name"
              />
            </div>
            {duplicateVm && (
              <div className="text-sm text-muted-foreground space-y-1">
                <p>Configuration to be cloned:</p>
                <ul className="list-disc list-inside pl-2">
                  <li>CPU: {duplicateVm.cpu} cores</li>
                  <li>Memory: {duplicateVm.memory} MB</li>
                  <li>ISO: {duplicateVm.iso}</li>
                  <li>Network: {duplicateVm.network_bridge || "default"}</li>
                  <li>Disks: {duplicateVm.disks?.length || 0} disk(s) will be copied</li>
                </ul>
                <p className="mt-2 text-xs font-semibold">Note: All disk files will be cloned (full copy)</p>
              </div>
            )}
          </div>
          <div className="flex justify-end space-x-2">
            <Button variant="outline" onClick={() => setDuplicateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleDuplicate} disabled={!duplicateName.trim()}>
              <Copy className="mr-2 h-4 w-4" />
              Duplicate
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
