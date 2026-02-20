import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Cpu, HardDrive, MemoryStick, Activity, Container, Server, Disc, Package, Play, Square } from "lucide-react"
import { useEffect, useState } from "react"
import { apiUrl } from "@/lib/api"

export function SystemOverview() {
  const [systemStats, setSystemStats] = useState({
    cpu: { usage: 0, cores: 0, model: "" },
    memory: { used: 0, total: 0, usage: 0 },
    storage: { used: 0, total: 0, usage: 0 },
    network: { in: 0, out: 0 },
    uptime: "",
    kernel: "",
    gpu: "",
    architecture: "",
    services: [] as { name: string; service?: string; status: string; port: number | null }[],
  })

  const [resourceCounts, setResourceCounts] = useState({
    containers: 0,
    vms: 0,
    dockerImages: 0,
    isos: 0,
    lxcImages: 0,
  })

  interface Drive {
    device: string
    name: string
    type: string
    size: number
    used: number
    available: number
    filesystem: string
    mountpoint: string
    mounted: boolean
    temperature?: number | null
  }

  const [drives, setDrives] = useState<Drive[]>([])

  const getUsageColor = (usage: number) => {
    if (usage > 85) return "bg-red-500"
    if (usage >= 76) return "bg-orange-500"
    return "bg-green-500"
  }

  const toggleService = async (serviceName: string, displayName: string, running: boolean) => {
    try {
      const res = await fetch(apiUrl(`/services/${serviceName}/${running ? "stop" : "start"}`), { method: "POST" })
      if (res.ok) {
        setSystemStats((prev) => ({
          ...prev,
          services: prev.services.map((s) => 
            s.name === displayName ? { ...s, status: running ? "stopped" : "running" } : s
          ),
        }))
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch(apiUrl("/metrics"))
        if (res.ok) {
          const data = await res.json()
          setSystemStats(data)
        }
      } catch (err) {
        console.error(err)
      }
    }
    fetchMetrics()
    const id = setInterval(fetchMetrics, 4000)
    return () => clearInterval(id)
  }, [])

  const physicalDrives = drives.reduce((acc, d) => {
    const base = d.device.replace(/^\/dev\//, "").replace(/p?\d+$/, "")
    const entry = acc.get(base) || {
      device: `/dev/${base}`,
      type: d.type,
      size: 0,
      used: 0,
      available: 0,
    }
    entry.size += d.size
    entry.used += d.used
    entry.available += d.available
    acc.set(base, entry)
    return acc
  }, new Map<string, { device: string; type: string; size: number; used: number; available: number }>())
  const physicalDriveList = Array.from(physicalDrives.values())

  useEffect(() => {
    const loadDrives = async () => {
      try {
        const res = await fetch(apiUrl("/drives"))
        if (res.ok) {
          const data = await res.json()
          setDrives(data.drives || [])
        }
      } catch (err) {
        console.error(err)
      }
    }
    loadDrives()
  }, [])

  useEffect(() => {
    const fetchResourceCounts = async () => {
      try {
        const containersRes = await fetch(apiUrl("/containers"), { credentials: "include" })
        let containersCount = 0
        if (containersRes.ok) {
          const containersData = await containersRes.json()
          containersCount = containersData.length || 0
        }

        const vmsRes = await fetch(apiUrl("/vms"), { credentials: "include" })
        let vmsCount = 0
        if (vmsRes.ok) {
          const vmsData = await vmsRes.json()
          vmsCount = vmsData.length || 0
        }

        const dockerImagesRes = await fetch(apiUrl("/images?type=docker"), { credentials: "include" })
        let dockerImagesCount = 0
        if (dockerImagesRes.ok) {
          const dockerData = await dockerImagesRes.json()
          dockerImagesCount = dockerData.images?.length || 0
        }

        const lxcImagesRes = await fetch(apiUrl("/images?type=lxc"), { credentials: "include" })
        let lxcImagesCount = 0
        if (lxcImagesRes.ok) {
          const lxcData = await lxcImagesRes.json()
          lxcImagesCount = lxcData.images?.length || 0
        }

        const isosRes = await fetch(apiUrl("/isos"), { credentials: "include" })
        let isosCount = 0
        if (isosRes.ok) {
          const isosData = await isosRes.json()
          isosCount = isosData.isos?.length || 0
        }

        setResourceCounts({
          containers: containersCount,
          vms: vmsCount,
          dockerImages: dockerImagesCount,
          isos: isosCount,
          lxcImages: lxcImagesCount,
        })
      } catch (err) {
        console.error("Failed to fetch resource counts:", err)
      }
    }

    fetchResourceCounts()
    const interval = setInterval(fetchResourceCounts, 30000) // Update every 30 seconds
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">System Overview</h2>
        <p className="text-muted-foreground">Current system load and status</p>
      </div>

      {/* System Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
            <Cpu className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{systemStats.cpu.usage}%</div>
            <Progress
              value={systemStats.cpu.usage}
              className="mt-2"
              indicatorClassName={getUsageColor(systemStats.cpu.usage)}
            />
            <p className="text-xs text-muted-foreground mt-2">
              {systemStats.cpu.cores} cores • {systemStats.cpu.model}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">RAM Usage</CardTitle>
            <MemoryStick className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{systemStats.memory.usage}%</div>
            <Progress
              value={systemStats.memory.usage}
              className="mt-2"
              indicatorClassName={getUsageColor(systemStats.memory.usage)}
            />
            <p className="text-xs text-muted-foreground mt-2">
              {systemStats.memory.used}GB / {systemStats.memory.total}GB
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Disk Usage</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{systemStats.storage.usage}%</div>
            <Progress
              value={systemStats.storage.usage}
              className="mt-2"
              indicatorClassName={getUsageColor(systemStats.storage.usage)}
            />
            <p className="text-xs text-muted-foreground mt-2">
              {systemStats.storage.used}GB / {systemStats.storage.total}GB
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Network</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">↓{systemStats.network.in}MB/s</div>
            <div className="text-sm text-muted-foreground">↑{systemStats.network.out}MB/s</div>
            <p className="text-xs text-muted-foreground mt-2">Current throughput</p>
          </CardContent>
        </Card>
      </div>

      {/* Resource Statistics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Containers</CardTitle>
            <Container className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{resourceCounts.containers}</div>
            <p className="text-xs text-muted-foreground mt-2">Containers</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Virtual Machines</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{resourceCounts.vms}</div>
            <p className="text-xs text-muted-foreground mt-2">QEMU/KVM VMs</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Docker Images</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{resourceCounts.dockerImages}</div>
            <p className="text-xs text-muted-foreground mt-2">Container images</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">LXC Images</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{resourceCounts.lxcImages}</div>
            <p className="text-xs text-muted-foreground mt-2">LXC container images</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">ISO Images</CardTitle>
            <Disc className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{resourceCounts.isos}</div>
            <p className="text-xs text-muted-foreground mt-2">VM installation media</p>
          </CardContent>
        </Card>
      </div>

      {/* System Info */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>System Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Kernel:</span>
              <span className="text-sm font-medium">{systemStats.kernel}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Uptime:</span>
              <span className="text-sm font-medium">{systemStats.uptime}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">CPU:</span>
              <span className="text-sm font-medium">{systemStats.cpu.model}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">GPU:</span>
              <span className="text-sm font-medium">{systemStats.gpu}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Architecture:</span>
              <span className="text-sm font-medium">{systemStats.architecture}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Services Status</CardTitle>
            <CardDescription>Current service status</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {systemStats.services.map((service) => (
                <div key={service.name} className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Badge className={service.status === "running" ? "bg-green-600 text-white" : "bg-red-600 text-white"}>
                      {service.status === "running" ? "Running" : service.status === "not found" ? "Not found" : "Stopped"}
                    </Badge>
                    <span className="text-sm font-medium">{service.name}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    {service.port && <span className="text-xs text-muted-foreground">:{service.port}</span>}
                    {service.status !== "not found" && service.service && (
                      <Button 
                        variant="outline" 
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => toggleService(service.service!, service.name, service.status === "running")}
                      >
                        {service.status === "running" ? <Square className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Drives Table */}
      <Card>
        <CardHeader>
          <CardTitle>Disks</CardTitle>
          <CardDescription>Available drives</CardDescription>
        </CardHeader>
        <CardContent className="pl-6 pr-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Device</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Used</TableHead>
                <TableHead>Available</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {physicalDriveList.map((d) => (
                <TableRow key={d.device}>
                  <TableCell className="font-mono">{d.device}</TableCell>
                  <TableCell>{d.type}</TableCell>
                  <TableCell>{d.size} GB</TableCell>
                  <TableCell>{d.used} GB</TableCell>
                  <TableCell>{d.available} GB</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
