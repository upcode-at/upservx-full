"use client"

import { useState, useEffect } from "react"
import { apiUrl } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Activity, AlertTriangle, CheckCircle, XCircle, TrendingUp } from "lucide-react"
import { Progress } from "@/components/ui/progress"

interface ClusterHealth {
  status: string
  nodes: {
    total: number
    online: number
    offline: number
  }
  load: {
    average_cpu: number
    average_memory: number
    average_disk: number
    total_capacity: number
    total_cpu_cores: number
    total_memory_gb: number
  }
  sync: {
    total_synced_containers: number
    running_containers: number
    sync_rules_count: number
  }
  alerts: {
    total: number
    critical: number
    warning: number
  }
  timestamp: string
}

interface LoadDistribution {
  total_nodes: number
  online_nodes: number
  offline_nodes: number
  average_cpu: number
  average_memory: number
  average_disk: number
  total_capacity: number
}

interface Alert {
  alert_id: string
  level: string
  message: string
  node_id: string
  metric_name: string
  value: number
  timestamp: string
  acknowledged: boolean
}

export default function ClusterHealthDashboard() {
  const [health, setHealth] = useState<ClusterHealth | null>(null)
  const [loadDistribution, setLoadDistribution] = useState<LoadDistribution | null>(null)
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)

  const getApiUrl = apiUrl

  const loadHealthData = async () => {
    try {
      const [healthRes, loadRes, alertsRes] = await Promise.all([
        fetch(getApiUrl("/cluster/health"), { credentials: "include" }),
        fetch(getApiUrl("/cluster/load/distribution"), { credentials: "include" }),
        fetch(getApiUrl("/cluster/alerts"), { credentials: "include" })
      ])

      if (healthRes.ok) {
        const healthData = await healthRes.json()
        setHealth(healthData)
      }

      if (loadRes.ok) {
        const loadData = await loadRes.json()
        setLoadDistribution(loadData)
      }

      if (alertsRes.ok) {
        const alertsData = await alertsRes.json()
        setAlerts(alertsData.alerts || [])
      }
    } catch (err) {
      console.error("Failed to load health data:", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadHealthData()
    const interval = setInterval(loadHealthData, 10000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const getHealthStatusBadge = (status: string) => {
    if (status === "healthy") {
      return (
        <Badge variant="success" className="flex items-center gap-1">
          <CheckCircle className="h-3 w-3" />
          Healthy
        </Badge>
      )
    } else if (status === "warning") {
      return (
        <Badge variant="secondary" className="flex items-center gap-1">
          <AlertTriangle className="h-3 w-3" />
          Warning
        </Badge>
      )
    } else {
      return (
        <Badge variant="destructive" className="flex items-center gap-1">
          <XCircle className="h-3 w-3" />
          Critical
        </Badge>
      )
    }
  }

  const getAlertBadge = (level: string) => {
    if (level === "critical") {
      return <Badge variant="destructive">Critical</Badge>
    } else if (level === "warning") {
      return <Badge variant="secondary">Warning</Badge>
    } else {
      return <Badge variant="outline">Info</Badge>
    }
  }

  const acknowledgeAlert = async (alertId: string) => {
    try {
      const response = await fetch(
        getApiUrl(`/cluster/alerts/${alertId}/acknowledge`),
        {
          method: "POST",
          credentials: "include"
        }
      )

      if (response.ok) {
        setAlerts(alerts.filter(a => a.alert_id !== alertId))
      }
    } catch (err) {
      console.error("Failed to acknowledge alert:", err)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Activity className="h-12 w-12 animate-pulse" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Health Overview */}
      {health && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Activity className="h-6 w-6" />
                <div>
                  <CardTitle>Cluster Health</CardTitle>
                  <CardDescription>Overall system status</CardDescription>
                </div>
              </div>
              {getHealthStatusBadge(health.status)}
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3 mb-4">
              <div>
                <div className="text-sm text-muted-foreground mb-1">Nodes Online</div>
                <div className="text-2xl font-bold">
                  {health.nodes.online}/{health.nodes.total}
                </div>
                <Progress 
                  value={(health.nodes.online / health.nodes.total) * 100} 
                  className="mt-2"
                />
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Total CPU Cores</div>
                <div className="text-2xl font-bold">{health.load.total_cpu_cores}</div>
                <div className="text-xs text-muted-foreground mt-1">Across all nodes</div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Total Memory</div>
                <div className="text-2xl font-bold">{health.load.total_memory_gb} GB</div>
                <div className="text-xs text-muted-foreground mt-1">Across all nodes</div>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <div className="text-sm text-muted-foreground mb-1">Average CPU</div>
                <div className="text-2xl font-bold">{health.load.average_cpu.toFixed(1)}%</div>
                <Progress value={health.load.average_cpu} className="mt-2" />
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Average Memory</div>
                <div className="text-2xl font-bold">{health.load.average_memory.toFixed(1)}%</div>
                <Progress value={health.load.average_memory} className="mt-2" />
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">Average Disk</div>
                <div className="text-2xl font-bold">{health.load.average_disk.toFixed(1)}%</div>
                <Progress value={health.load.average_disk} className="mt-2" />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Load Distribution */}
        {loadDistribution && (
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                <CardTitle>Load Distribution</CardTitle>
              </div>
              <CardDescription>Cluster resource utilization</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span>CPU Usage</span>
                  <span className="font-medium">{loadDistribution.average_cpu.toFixed(1)}%</span>
                </div>
                <Progress value={loadDistribution.average_cpu} />
              </div>
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span>Memory Usage</span>
                  <span className="font-medium">{loadDistribution.average_memory.toFixed(1)}%</span>
                </div>
                <Progress value={loadDistribution.average_memory} />
              </div>
            </CardContent>
          </Card>
        )}

        {/* Synchronization Status */}
        {health && (
          <Card>
            <CardHeader>
              <CardTitle>Container Synchronization</CardTitle>
              <CardDescription>Distributed container status</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Synced Containers</span>
                <span className="text-2xl font-bold">{health.sync.total_synced_containers}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Running Containers</span>
                <span className="text-2xl font-bold">{health.sync.running_containers}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Sync Rules</span>
                <span className="text-2xl font-bold">{health.sync.sync_rules_count}</span>
              </div>
              <Progress 
                value={health.sync.total_synced_containers > 0 
                  ? (health.sync.running_containers / health.sync.total_synced_containers) * 100 
                  : 0
                } 
                className="mt-2"
              />
            </CardContent>
          </Card>
        )}
      </div>

      {/* Active Alerts */}
      {alerts.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                <CardTitle>Active Alerts</CardTitle>
              </div>
              <Badge variant="destructive">{alerts.length}</Badge>
            </div>
            <CardDescription>System notifications and warnings</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {alerts.map((alert) => (
                <div
                  key={alert.alert_id}
                  className="flex items-start justify-between p-3 border rounded-lg"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      {getAlertBadge(alert.level)}
                      <span className="text-sm font-medium">{alert.node_id}</span>
                    </div>
                    <p className="text-sm">{alert.message}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {new Date(alert.timestamp).toLocaleString()}
                    </p>
                  </div>
                  <button
                    onClick={() => acknowledgeAlert(alert.alert_id)}
                    className="text-sm text-blue-600 hover:underline ml-4"
                  >
                    Acknowledge
                  </button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
