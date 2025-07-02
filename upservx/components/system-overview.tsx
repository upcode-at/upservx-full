import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Cpu, HardDrive, MemoryStick, Activity } from "lucide-react"
import { useEffect, useState } from "react"

export function SystemOverview() {
  const [systemStats, setSystemStats] = useState({
    cpu: { usage: 0, cores: 0, model: "" },
    memory: { used: 0, total: 0, usage: 0 },
    storage: { used: 0, total: 0, usage: 0 },
    network: { in: 0, out: 0 },
    uptime: "",
    kernel: "",
    gpu: "",
  })

  const getUsageColor = (usage: number) => {
    if (usage >= 90) return "bg-red-500"
    if (usage >= 80) return "bg-yellow-400"
    return undefined
  }

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const res = await fetch("http://localhost:8000/metrics")
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

  const services = [
    { name: "Docker", status: "running", port: 2376 },
    { name: "Kubernetes", status: "running", port: 6443 },
    { name: "LXC", status: "running", port: null },
    { name: "SSH", status: "running", port: 22 },
    { name: "Web Interface", status: "running", port: 8080 },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">System Übersicht</h2>
        <p className="text-muted-foreground">Aktuelle Systemauslastung und Status</p>
      </div>

      {/* System Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">CPU Auslastung</CardTitle>
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
              {systemStats.cpu.cores} Kerne • {systemStats.cpu.model}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">RAM Auslastung</CardTitle>
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
            <CardTitle className="text-sm font-medium">Festplatte</CardTitle>
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
            <CardTitle className="text-sm font-medium">Netzwerk</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">↓{systemStats.network.in}MB/s</div>
            <div className="text-sm text-muted-foreground">↑{systemStats.network.out}MB/s</div>
            <p className="text-xs text-muted-foreground mt-2">Aktuelle Übertragung</p>
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
              <span className="text-sm text-muted-foreground">Architektur:</span>
              <span className="text-sm font-medium">x86_64</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Services Status</CardTitle>
            <CardDescription>Aktuelle Service-Status</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {services.map((service) => (
                <div key={service.name} className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Badge variant={service.status === "running" ? "default" : "destructive"}>
                      {service.status === "running" ? "Läuft" : "Gestoppt"}
                    </Badge>
                    <span className="text-sm font-medium">{service.name}</span>
                  </div>
                  {service.port && <span className="text-xs text-muted-foreground">:{service.port}</span>}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
