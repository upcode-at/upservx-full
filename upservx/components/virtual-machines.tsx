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
import { LayoutGrid, List as ListIcon, Play, Square, Plus, Trash2, Pencil } from "lucide-react"
import { apiUrl } from "@/lib/api"

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
  }

  const [vms, setVms] = useState<VMData[]>([])
  const [isos, setIsos] = useState<string[]>([])
  const [name, setName] = useState("")
  const [cpu, setCpu] = useState(1)
  const [memory, setMemory] = useState(2048)
  const maxCpu = 16
  const maxMemory = 32768
  const [iso, setIso] = useState("")
  const [disks, setDisks] = useState<number[]>([20])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<VMData | null>(null)
  const [view, setView] = useState<"grid" | "list">("grid")
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

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
    if (!error && !message) return
    const t = setTimeout(() => { setError(null); setMessage(null) }, 3000)
    return () => clearTimeout(t)
  }, [error, message])

  const handleSave = async () => {
    const payload = editing
      ? { cpu, memory, iso, add_disks: disks }
      : { name, cpu, memory, iso, disks }
    const target = editing ? `/vms/${editing.name}` : "/vms"
    const method = editing ? "PATCH" : "POST"
    const vmName = name
    try {
      const res = await fetch(apiUrl(target), {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
      if (res.ok) {
        const vm = await res.json()
        if (editing) {
          setVms(prev => prev.map(v => v.name === editing.name ? vm : v))
        } else {
          setVms(prev => [...prev, vm])
        }
        setOpen(false)
        setEditing(null)
        setMessage(`VM ${vmName} ${editing ? "updated" : "created"}`)
      } else {
        const data = await res.json().catch(() => null)
        setError(data?.detail || "Error saving")
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
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
        setVms(prev => prev.map(vm => vm.name === name ? { ...vm, status: "shut off" } : vm))
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

  const openEdit = (vm: VMData) => {
    setEditing(vm)
    setName(vm.name)
    setCpu(vm.cpu)
    setMemory(vm.memory)
    setIso(vm.iso)
    setDisks([])
    setOpen(true)
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
          <p className="text-muted-foreground">Manage your virtual machines</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant={view === "grid" ? "secondary" : "outline"} size="icon" onClick={() => setView("grid")}> <LayoutGrid className="h-4 w-4" /></Button>
          <Button variant={view === "list" ? "secondary" : "outline"} size="icon" onClick={() => setView("list")}> <ListIcon className="h-4 w-4" /></Button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button onClick={() => { setEditing(null); setName(""); setCpu(1); setMemory(2048); setIso(""); setDisks([20]); setOpen(true) }}>
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
                </TabsContent>
                <TabsContent value="resources" className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="vm-cpu">CPU Cores: {cpu}</Label>
                      <input id="vm-cpu" type="range" min={1} max={maxCpu} step={1} className="w-full" value={cpu} onChange={e => setCpu(parseInt(e.target.value))} />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="vm-memory">RAM (MB): {memory}</Label>
                      <input id="vm-memory" type="range" min={512} max={maxMemory} step={512} className="w-full" value={memory} onChange={e => setMemory(parseInt(e.target.value))} />
                    </div>
                  </div>
                </TabsContent>
                <TabsContent value="storage" className="space-y-4">
                  <Label>Disks (GB)</Label>
                  {disks.map((d, idx) => (
                    <div key={idx} className="flex space-x-2 items-center">
                      <Input type="number" value={d} onChange={e => { const arr = [...disks]; arr[idx] = parseInt(e.target.value); setDisks(arr) }} />
                      <Button variant="outline" size="icon" onClick={() => setDisks(disks.filter((_, i) => i !== idx))}>-</Button>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" onClick={() => setDisks([...disks, 20])}>Add disk</Button>
                </TabsContent>
              </Tabs>
              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => { setOpen(false); setEditing(null) }}>Cancel</Button>
                <Button onClick={handleSave}>{editing ? "Save" : "Create VM"}</Button>
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
                  <Badge className={vm.status.includes("running") ? "bg-green-600 text-white" : "bg-red-600 text-white"}>{vm.status}</Badge>
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
                {vm.status.includes("running") ? (
                  <Button variant="destructive" size="icon" onClick={() => handleStop(vm.name)}>
                    <Square className="h-4 w-4" />
                  </Button>
                ) : (
                  <Button className="bg-green-600 text-white hover:bg-green-700" size="icon" onClick={() => handleStart(vm.name)}>
                    <Play className="h-4 w-4" />
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
            <table className="w-full">
              <thead>
                <tr className="text-left">
                  <th>Name</th>
                  <th>Status</th>
                  <th>ISO</th>
                  <th>CPU</th>
                  <th>Memory</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {vms.length === 0 ? (
                  <tr className="border-t border-border">
                    <td colSpan={7} className="text-center">
                      No virtual machines found
                    </td>
                  </tr>
                ) : (
                  vms.map((vm) => (
                    <tr key={vm.id} className="border-t border-border">
                      <td className="py-2">{vm.name}</td>
                      <td>{vm.status}</td>
                      <td className="text-sm">{vm.iso}</td>
                      <td>{vm.cpu}</td>
                      <td>{vm.memory}</td>
                      <td className="text-sm">{vm.created}</td>
                      <td>
                        <div className="flex gap-1">
                          {vm.status.includes("running") ? (
                            <Button variant="destructive" size="icon" onClick={() => handleStop(vm.name)}>
                              <Square className="h-4 w-4" />
                            </Button>
                          ) : (
                            <Button className="bg-green-600 text-white hover:bg-green-700" size="icon" onClick={() => handleStart(vm.name)}>
                              <Play className="h-4 w-4" />
                            </Button>
                          )}
                          <Button variant="outline" size="icon" onClick={() => openEdit(vm)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="destructive" size="icon" onClick={() => handleDelete(vm.name)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
