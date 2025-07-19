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
import { Play, Square, Settings, Plus, Monitor, Terminal, Trash2 } from "lucide-react"
import { RDPClient } from "@/components/rdp-client"
import { apiUrl } from "@/lib/api"

export function VirtualMachines() {
  interface VMData {
    id: number
    name: string
    os: string
    status: string
    cpu: number
    memory: number
    disks: number[]
    ip: string
  }

  const [vms, setVms] = useState<VMData[]>([])
  const [name, setName] = useState("")
  const [os, setOs] = useState("")
  const [isoFiles, setIsoFiles] = useState<
    {
      id: number
      name: string
      size: number
      type: string
      version: string
      architecture: string
      created: string
      used: boolean
      path: string
    }[]
  >([])
  const [cpu, setCpu] = useState(1)
  const [memory, setMemory] = useState(2048)
  const [maxCpu, setMaxCpu] = useState(8)
  const [maxMemory, setMaxMemory] = useState(16384)
  const [disks, setDisks] = useState<number[]>([20])
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [activeRDP, setActiveRDP] = useState<{ name: string; ip: string } | null>(null)

  const loadMetrics = async () => {
    try {
      const res = await fetch(apiUrl("/metrics"))
      if (res.ok) {
        const data = await res.json()
        if (data.cpu?.cores) setMaxCpu(data.cpu.cores)
        if (data.memory?.total) setMaxMemory(Math.round(data.memory.total * 1024))
      }
    } catch (e) {
      console.error(e)
    }
  }

  const loadIsos = async () => {
    try {
      const res = await fetch(apiUrl("/isos"))
      if (res.ok) {
        const data = await res.json()
        setIsoFiles(data.isos || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

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
    loadIsos()
  }, [])

  useEffect(() => {
    loadMetrics()
  }, [])

  useEffect(() => {
    if (open) {
      loadMetrics()
      loadIsos()
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "default"
      case "stopped":
        return "secondary"
      case "paused":
        return "outline"
      default:
        return "secondary"
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case "running":
        return "Läuft"
      case "stopped":
        return "Gestoppt"
      case "paused":
        return "Pausiert"
      default:
        return status
    }
  }

  const handleCreate = async () => {
    const payload = { name, os, cpu, memory, disks }
    const creating = name
    try {
      const res = await fetch(apiUrl("/vms"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      if (res.ok) {
        const vm = await res.json()
        setVms((prev) => [...prev, vm])
        setMessage(`VM ${creating} erstellt`)
        setOpen(false)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleStart = async (vmName: string) => {
    try {
      const res = await fetch(apiUrl(`/vms/${vmName}/start`), { method: "POST" })
      if (res.ok) {
        setVms((prev) => prev.map((v) => (v.name === vmName ? { ...v, status: "running" } : v)))
      } else {
        setError("Error starting")
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
    }
  }

  const handleStop = async (vmName: string) => {
    try {
      const res = await fetch(apiUrl(`/vms/${vmName}/stop`), { method: "POST" })
      if (res.ok) {
        setVms((prev) => prev.map((v) => (v.name === vmName ? { ...v, status: "stopped" } : v)))
      } else {
        setError("Error stopping")
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
    }
  }

  const handleDelete = async (vmName: string) => {
    try {
      const res = await fetch(apiUrl(`/vms/${vmName}`), { method: "DELETE" })
      if (res.ok) {
        setVms((prev) => prev.filter((v) => v.name !== vmName))
        setMessage(`VM ${vmName} gelöscht`)
      } else {
        setError("Error deleting")
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
    }
  }


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
          <h2 className="text-3xl font-bold tracking-tight">Virtual Machines</h2>
          <p className="text-muted-foreground">Verwalten Sie Ihre virtuellen Maschinen</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => setOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Neue VM erstellen
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Neue Virtual Machine erstellen</DialogTitle>
              <DialogDescription>Konfigurieren Sie Ihre neue virtuelle Maschine</DialogDescription>
            </DialogHeader>
            <Tabs defaultValue="basic" className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="basic">Grundlagen</TabsTrigger>
                <TabsTrigger value="hardware">Hardware</TabsTrigger>
                <TabsTrigger value="network">Netzwerk</TabsTrigger>
                <TabsTrigger value="storage">Speicher</TabsTrigger>
              </TabsList>
              <TabsContent value="basic" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="vm-name">VM Name</Label>
                    <Input
                      id="vm-name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="z.B. Ubuntu-Server-02"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="vm-os">Betriebssystem</Label>
                    <Select value={os} onValueChange={setOs}>
                      <SelectTrigger>
                        <SelectValue placeholder="ISO auswählen" />
                      </SelectTrigger>
                      <SelectContent>
                        {isoFiles.map((iso) => (
                          <SelectItem key={iso.name} value={iso.name}>
                            {iso.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="hardware" className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="vm-cpu">CPU Kerne: {cpu}</Label>
                    <input
                      id="vm-cpu"
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
                    <Label htmlFor="vm-memory">RAM (MB): {memory}</Label>
                    <input
                      id="vm-memory"
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
                <div className="space-y-2">
                  <Label htmlFor="vm-network">Netzwerk Modus</Label>
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Netzwerk auswählen" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="bridge">Bridge</SelectItem>
                      <SelectItem value="nat">NAT</SelectItem>
                      <SelectItem value="host">Host-only</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </TabsContent>
              <TabsContent value="storage" className="space-y-4">
                <Label>Festplatten (GB)</Label>
                {disks.map((d, idx) => (
                  <div key={idx} className="flex space-x-2 items-center">
                    <Input
                      type="number"
                      value={d}
                      onChange={(e) => {
                        const arr = [...disks]
                        arr[idx] = parseInt(e.target.value)
                        setDisks(arr)
                      }}
                      placeholder="50"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setDisks(disks.filter((_, i) => i !== idx))}
                    >
                      -
                    </Button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setDisks([...disks, 20])}
                >
                  Festplatte hinzufügen
                </Button>
              </TabsContent>
            </Tabs>
            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Abbrechen
              </Button>
              <Button onClick={handleCreate}>VM erstellen</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid gap-4">
        {vms.map((vm) => (
          <Card key={vm.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    {vm.name}
                    <Badge variant={getStatusColor(vm.status)}>{getStatusText(vm.status)}</Badge>
                  </CardTitle>
                  <CardDescription>{vm.os}</CardDescription>
                </div>
                <div className="flex space-x-2">
                  <Button variant="outline" size="icon" onClick={() => setActiveRDP({ name: vm.name, ip: vm.ip })}>
                    <Monitor className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon">
                    <Terminal className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="icon">
                    <Settings className="h-4 w-4" />
                  </Button>
                  {vm.status === "running" ? (
                    <Button variant="outline" size="icon" onClick={() => handleStop(vm.name)}>
                      <Square className="h-4 w-4" />
                    </Button>
                  ) : (
                    <Button variant="outline" size="icon" onClick={() => handleStart(vm.name)}>
                      <Play className="h-4 w-4" />
                    </Button>
                  )}
                  <Button variant="destructive" size="icon" onClick={() => handleDelete(vm.name)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">CPU:</span>
                  <div className="font-medium">{vm.cpu} Kerne</div>
                </div>
                <div>
                  <span className="text-muted-foreground">RAM:</span>
                  <div className="font-medium">{vm.memory / 1024} GB</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Speicher:</span>
                  <div className="font-medium">
                    {vm.disks.map((d) => `${d} GB`).join(', ')}
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground">IP:</span>
                  <div className="font-medium">{vm.ip}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      {activeRDP && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <RDPClient vmName={activeRDP.name} vmIP={activeRDP.ip} onClose={() => setActiveRDP(null)} />
        </div>
      )}
    </div>
  )
}
