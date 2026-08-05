"use client"

import { useState, useEffect } from "react"
import { apiUrl } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { NotificationContainer } from "@/components/ui/notification"
import { Server, Plus, Trash2, Network, Database, Settings as SettingsIcon, Activity, GitBranch, Play, ShieldCheck, Zap, Radio } from "lucide-react"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog"
import ClusterHealthDashboard from "@/components/cluster-health-dashboard"

interface ClusterNode {
  id: string
  hostname: string
  ip_address: string
  port: number
  status: "online" | "offline" | "syncing"
  role: "master" | "child"
  resources: {
    cpu_usage: number
    memory_usage: number
    disk_usage: number
    running_containers?: number
    total_containers?: number
    running_vms?: number
    total_vms?: number
  }
  last_seen: string
}

interface ClusterInfo {
  is_master: boolean
  is_member: boolean
  master_ip?: string
  nodes: ClusterNode[]
}

interface Replication {
  id: string
  origin_node: string
  destination_node: string
  name: string
  type: string
  sync_schedule: string
}

interface ReplicationProgress {
  replication_id: string
  status: "idle" | "running" | "completed" | "failed"
  progress: number
  message: string
  updated_at?: string | null
}

export default function ClusterManagement() {
  const [clusterInfo, setClusterInfo] = useState<ClusterInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [replications, setReplications] = useState<Replication[]>([])
  const [replicationProgress, setReplicationProgress] = useState<Record<string, ReplicationProgress>>({})

  const [createClusterOpen, setCreateClusterOpen] = useState(false)
  const [joinClusterOpen, setJoinClusterOpen] = useState(false)
  const [addReplicationOpen, setAddReplicationOpen] = useState(false)
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugInfo, setDebugInfo] = useState<any>(null)

  const [clusterName, setClusterName] = useState("")
  const [masterIp, setMasterIp] = useState("")
  const [masterPort, setMasterPort] = useState("9501")
  const [joinToken, setJoinToken] = useState("")

  const [replicationOriginNode, setReplicationOriginNode] = useState("")
  const [replicationDestNode, setReplicationDestNode] = useState("")
  const [replicationResource, setReplicationResource] = useState("")
  const [replicationCronSchedule, setReplicationCronSchedule] = useState("0 2 * * *") // Daily at 2 AM
  const [availableResources, setAvailableResources] = useState<Array<{name: string, type: string}>>([])
  const [loadingResources, setLoadingResources] = useState(false)

  // ── High Availability ────────────────────────────────────────────────────
  interface HAHeartbeat {
    hostname: string
    ip_address: string
    port: number
    role: string
    priority: number
    last_seen: string
    alive: boolean
    age_seconds: number
  }
  interface HAStatus {
    enabled: boolean
    vip: string
    vip_interface: string
    vip_ha_interface?: string
    vip_owner: boolean
    vip_owner_hostname?: string | null
    vip_owner_ip?: string | null
    active_master: string | null
    last_election: string | null
    heartbeat_interval: number
    failure_threshold: number
    priority: number
    my_hostname: string
    my_ip: string
    is_master: boolean
    is_child: boolean
    total_nodes_tracked: number
    alive_nodes: number
    heartbeats: HAHeartbeat[]
  }
  const [haStatus, setHaStatus] = useState<HAStatus | null>(null)
  const [haVip, setHaVip] = useState("")
  const [haVipInterface, setHaVipInterface] = useState("")
  const [haHeartbeatInterval, setHaHeartbeatInterval] = useState("5")
  const [haFailureThreshold, setHaFailureThreshold] = useState("3")
  const [haPriority, setHaPriority] = useState("100")
  const [haConfigOpen, setHaConfigOpen] = useState(false)
  const [haLoading, setHaLoading] = useState(false)

  const getApiUrl = apiUrl

  const loadClusterInfo = async (isInitialLoad = false) => {
    try {
      if (isInitialLoad) {
        setLoading(true)
      }
      setError(null)

      const response = await fetch(getApiUrl("/cluster/info"), {
        credentials: "include"
      })

      if (!response.ok) {
        throw new Error("Failed to fetch cluster info")
      }

      const data = await response.json()
      setClusterInfo(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cluster info")
    } finally {
      if (isInitialLoad) {
        setLoading(false)
      }
    }
  }

  useEffect(() => {
    loadClusterInfo(true)
    const interval = setInterval(() => loadClusterInfo(false), 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (clusterInfo?.is_master) {
      loadReplications()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clusterInfo?.is_master])

  useEffect(() => {
    if (replications.length === 0) {
      setReplicationProgress({})
      return
    }

    let active = true

    const loadProgress = async () => {
      const entries = await Promise.all(
        replications.map(async (replication) => {
          try {
            const response = await fetch(getApiUrl(`/cluster/replications/${replication.id}/progress`), {
              credentials: "include"
            })
            if (!response.ok) return null
            const data = await response.json()
            return [replication.id, data as ReplicationProgress] as const
          } catch {
            return null
          }
        })
      )

      if (!active) return

      const next: Record<string, ReplicationProgress> = {}
      entries.forEach((entry) => {
        if (entry) {
          next[entry[0]] = entry[1]
        }
      })
      setReplicationProgress(next)
    }

    loadProgress()
    const timer = setInterval(loadProgress, 2000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [replications])

  useEffect(() => {
    if (replicationOriginNode) {
      loadResourcesFromNode(replicationOriginNode)
    } else {
      setAvailableResources([])
      setReplicationResource("")
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [replicationOriginNode])

  const createCluster = async () => {
    try {
      setError(null)
      setSuccess(null)

      const response = await fetch(getApiUrl("/cluster/create"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ cluster_name: clusterName })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to create cluster")
      }

      const data = await response.json()
      setSuccess(`Cluster created successfully! Token: ${data.token}`)
      setCreateClusterOpen(false)
      setClusterName("")
      loadClusterInfo()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create cluster")
    }
  }

  const joinCluster = async () => {
    try {
      setError(null)
      setSuccess(null)

      const response = await fetch(getApiUrl("/cluster/join"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          master_ip: masterIp,
          token: joinToken,
          port: parseInt(masterPort)
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to join cluster")
      }

      setSuccess("Successfully joined cluster")
      setJoinClusterOpen(false)
      setMasterIp("")
      setMasterPort("9501")
      setJoinToken("")
      loadClusterInfo()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to join cluster")
    }
  }

  const leaveCluster = async () => {
    if (!confirm("Are you sure you want to leave the cluster?")) return

    try {
      setError(null)

      const response = await fetch(getApiUrl("/cluster/leave"), {
        method: "POST",
        credentials: "include"
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to leave cluster")
      }

      setSuccess("Successfully left cluster")
      loadClusterInfo()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to leave cluster")
    }
  }

  const removeNode = async (nodeId: string) => {
    if (!confirm("Are you sure you want to remove this node from the cluster?")) return

    try {
      setError(null)

      const response = await fetch(getApiUrl(`/cluster/nodes/${nodeId}`), {
        method: "DELETE",
        credentials: "include"
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to remove node")
      }

      setSuccess("Node removed successfully")
      loadClusterInfo()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove node")
    }
  }

  const loadDebugInfo = async () => {
    try {
      const response = await fetch(getApiUrl("/cluster/debug"), {
        credentials: "include"
      })

      if (response.ok) {
        const data = await response.json()
        setDebugInfo(data)
        setDebugOpen(true)
      }
    } catch (err) {
      setError("Failed to load debug information")
    }
  }

  const loadReplications = async () => {
    try {
      const response = await fetch(getApiUrl("/cluster/replications"), {
        credentials: "include"
      })

      if (response.ok) {
        const data = await response.json()
        setReplications(data)
      }
    } catch (err) {
      console.error("Failed to load replications:", err)
    }
  }

  const loadResourcesFromNode = async (nodeHostname: string) => {
    try {
      setLoadingResources(true)
      const response = await fetch(getApiUrl(`/cluster/nodes/${nodeHostname}/resources`), {
        credentials: "include"
      })

      if (response.ok) {
        const data = await response.json()
        setAvailableResources(data.resources || [])
      } else {
        console.error(`Failed to load resources: ${response.statusText}`)
        setAvailableResources([])
      }
    } catch (err) {
      console.error("Failed to load resources:", err)
      setAvailableResources([])
    } finally {
      setLoadingResources(false)
    }
  }

  const addReplication = async () => {
    try {
      setError(null)
      setSuccess(null)

      if (!replicationOriginNode || !replicationDestNode || !replicationResource || !replicationCronSchedule) {
        setError("Please fill in all fields")
        return
      }

      const selectedResource = availableResources.find(r => r.name === replicationResource)
      if (!selectedResource) {
        setError("Invalid resource selected")
        return
      }

      const response = await fetch(getApiUrl("/cluster/replications"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          origin_node: replicationOriginNode,
          destination_node: replicationDestNode,
          name: replicationResource,
          type: selectedResource.type,
          sync_schedule: replicationCronSchedule
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to add replication")
      }

      setSuccess("Replication rule added successfully")
      setAddReplicationOpen(false)
      setReplicationOriginNode("")
      setReplicationDestNode("")
      setReplicationResource("")
      setReplicationCronSchedule("0 2 * * *")
      setAvailableResources([])
      loadReplications()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add replication")
    }
  }

  const deleteReplication = async (replicationId: string) => {
    if (!confirm("Are you sure you want to delete this replication rule?")) return

    try {
      setError(null)

      const response = await fetch(getApiUrl(`/cluster/replications/${replicationId}`), {
        method: "DELETE",
        credentials: "include"
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to delete replication")
      }

      setSuccess("Replication rule deleted successfully")
      loadReplications()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete replication")
    }
  }

  const triggerReplication = async (replicationId: string) => {
    try {
      setError(null)
      setSuccess(null)

      const response = await fetch(getApiUrl(`/cluster/replications/${replicationId}/trigger`), {
        method: "POST",
        credentials: "include"
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to trigger replication")
      }

      setReplicationProgress((prev) => ({
        ...prev,
        [replicationId]: {
          replication_id: replicationId,
          status: "running",
          progress: 1,
          message: "Replication started",
        },
      }))

      setSuccess("Replication triggered successfully")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger replication")
    }
  }

  // ── HA helpers ──────────────────────────────────────────────────────────
  const loadHaStatus = async (updateFormFields = false) => {
    try {
      const res = await fetch(getApiUrl("/cluster/ha/status"), { credentials: "include" })
      if (res.ok) {
        const data = await res.json()
        setHaStatus(data)
        // Only overwrite form fields on explicit refresh (initial load / after save),
        // never during background polling – otherwise the dialog gets cleared while typing.
        if (updateFormFields) {
          setHaVip(data.vip || "")
          setHaVipInterface(data.vip_interface || "")
          setHaHeartbeatInterval(String(data.heartbeat_interval ?? 5))
          setHaFailureThreshold(String(data.failure_threshold ?? 3))
          setHaPriority(String(data.priority ?? 100))
        }
      }
    } catch { /* silent */ }
  }

  const toggleHa = async (enabled: boolean) => {
    setHaLoading(true)
    try {
      const endpoint = enabled ? "/cluster/ha/enable" : "/cluster/ha/disable"
      const res = await fetch(getApiUrl(endpoint), { method: "POST", credentials: "include" })
      if (!res.ok) throw new Error("Failed to toggle HA")
      setSuccess(enabled ? "High Availability enabled" : "High Availability disabled")
      await loadHaStatus(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to toggle HA")
    } finally {
      setHaLoading(false)
    }
  }

  const saveHaConfig = async () => {
    setHaLoading(true)
    try {
      const res = await fetch(getApiUrl("/cluster/ha"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          vip: haVip || null,
          vip_interface: haVipInterface || null,
          heartbeat_interval: parseInt(haHeartbeatInterval),
          failure_threshold: parseInt(haFailureThreshold),
          priority: parseInt(haPriority),
        })
      })
      if (!res.ok) throw new Error("Failed to save HA config")
      setSuccess("HA configuration saved")
      setHaConfigOpen(false)
      await loadHaStatus(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save HA config")
    } finally {
      setHaLoading(false)
    }
  }

  const triggerFailover = async () => {
    if (!confirm("Trigger a manual failover? A new master election will be performed immediately.")) return
    setHaLoading(true)
    try {
      const res = await fetch(getApiUrl("/cluster/ha/failover"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ reason: "manual" })
      })
      if (!res.ok) throw new Error("Failover failed")
      const data = await res.json()
      setSuccess(`Failover complete. New master: ${data.new_master}`)
      await loadHaStatus(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failover failed")
    } finally {
      setHaLoading(false)
    }
  }

  const assignVip = async () => {
    setHaLoading(true)
    try {
      const res = await fetch(getApiUrl("/cluster/ha/vip/assign"), { method: "POST", credentials: "include" })
      if (!res.ok) throw new Error("Failed to assign VIP")
      setSuccess("VIP assigned to this node")
      await loadHaStatus(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign VIP")
    } finally {
      setHaLoading(false)
    }
  }

  const releaseVip = async () => {
    setHaLoading(true)
    try {
      const res = await fetch(getApiUrl("/cluster/ha/vip/release"), { method: "POST", credentials: "include" })
      if (!res.ok) throw new Error("Failed to release VIP")
      setSuccess("VIP released from this node")
      await loadHaStatus(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to release VIP")
    } finally {
      setHaLoading(false)
    }
  }

  useEffect(() => {
    if (clusterInfo?.is_member) {
      loadHaStatus(true)  // initial load: populate form fields
      const interval = setInterval(loadHaStatus, 10000)  // polling: never touch form fields
      return () => clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clusterInfo?.is_member])

  const getStatusBadge = (status: string) => {    const variants: Record<string, "success" | "secondary" | "destructive"> = {
      online: "success",
      offline: "destructive",
      syncing: "secondary"
    }
    return <Badge variant={variants[status] || "secondary"}>{status}</Badge>
  }

  const getRoleBadge = (role: string) => {
    return (
      <Badge variant="secondary">
        {role}
      </Badge>
    )
  }

  const totalContainers = clusterInfo?.nodes?.reduce((sum, node) => sum + (node.resources?.total_containers || 0), 0) || 0
  const runningContainers = clusterInfo?.nodes?.reduce((sum, node) => sum + (node.resources?.running_containers || 0), 0) || 0
  const totalVMs = clusterInfo?.nodes?.reduce((sum, node) => sum + (node.resources?.total_vms || 0), 0) || 0
  const runningVMs = clusterInfo?.nodes?.reduce((sum, node) => sum + (node.resources?.running_vms || 0), 0) || 0

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Network className="h-12 w-12 animate-pulse mx-auto mb-4" />
          <p>Loading cluster information...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Network className="h-8 w-8" />
          <div>
            <h1 className="text-3xl font-bold">Cluster Management</h1>
            <p className="text-muted-foreground">Manage your distributed server cluster</p>
          </div>
        </div>
        <div className="flex gap-2">
          {!clusterInfo?.is_member && (
            <>
              <Dialog open={createClusterOpen} onOpenChange={setCreateClusterOpen}>
                <DialogTrigger asChild>
                  <Button>
                    <Database className="h-4 w-4 mr-2" />
                    Create Cluster
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Create New Cluster</DialogTitle>
                    <DialogDescription>
                      Create a new cluster and become the master node
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label htmlFor="cluster-name">Cluster Name</Label>
                      <Input
                        id="cluster-name"
                        placeholder="My Cluster"
                        value={clusterName}
                        onChange={(e) => setClusterName(e.target.value)}
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setCreateClusterOpen(false)}>
                      Cancel
                    </Button>
                    <Button onClick={createCluster} disabled={!clusterName}>
                      Create Cluster
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              <Dialog open={joinClusterOpen} onOpenChange={setJoinClusterOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline">
                    <Plus className="h-4 w-4 mr-2" />
                    Join Cluster
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Join a Cluster</DialogTitle>
                    <DialogDescription>
                      Join an existing cluster as a child node
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label htmlFor="master-ip">Master Node IP Address</Label>
                      <Input
                        id="master-ip"
                        placeholder="192.168.1.100"
                        value={masterIp}
                        onChange={(e) => setMasterIp(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="master-port">Master Node Port</Label>
                      <Input
                        id="master-port"
                        type="number"
                        placeholder="9500"
                        value={masterPort}
                        onChange={(e) => setMasterPort(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="join-token">Cluster Token</Label>
                      <Input
                        id="join-token"
                        placeholder="Token from master node"
                        value={joinToken}
                        onChange={(e) => setJoinToken(e.target.value)}
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setJoinClusterOpen(false)}>
                      Cancel
                    </Button>
                    <Button onClick={joinCluster} disabled={!masterIp || !joinToken || !masterPort}>
                      Join
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </>
          )}
          {clusterInfo?.is_member && (
            <Button variant="destructive" onClick={leaveCluster}>
              Leave Cluster
            </Button>
          )}
        </div>
      </div>

      <NotificationContainer
        error={error}
        success={success}
        onClearError={() => setError(null)}
        onClearSuccess={() => setSuccess(null)}
      />

      {clusterInfo?.is_member ? (
        <Tabs defaultValue="overview" className="w-full space-y-4">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">
              <Server className="h-4 w-4 mr-2" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="health">
              <Activity className="h-4 w-4 mr-2" />
              Health & Monitoring
            </TabsTrigger>
            <TabsTrigger value="workload">
              <GitBranch className="h-4 w-4 mr-2" />
              Workload Distribution
            </TabsTrigger>
            <TabsTrigger value="ha">
              <ShieldCheck className="h-4 w-4 mr-2" />
              High Availability
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            {/* Cluster Status Overview */}
            <div className="grid gap-4 md:grid-cols-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Cluster Status</CardTitle>
                  <Network className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {clusterInfo?.is_member ? "Active" : "Not Connected"}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {clusterInfo?.is_master ? "Master Node" : clusterInfo?.is_member ? "Child Node" : "Standalone"}
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Total Nodes</CardTitle>
                  <Server className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{clusterInfo?.nodes?.length ?? 0}</div>
                  <p className="text-xs text-muted-foreground">
                    Connected Servers
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">All Containers</CardTitle>
                  <Database className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{totalContainers}</div>
                  <p className="text-xs text-muted-foreground">
                    {runningContainers} running
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">All VMs</CardTitle>
                  <Server className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{totalVMs}</div>
                  <p className="text-xs text-muted-foreground">
                    {runningVMs} running
                  </p>
                </CardContent>
              </Card>

            </div>

            {/* Cluster Nodes Table */}
            <Card>
              <CardHeader>
                <CardTitle>Cluster Nodes</CardTitle>
                <CardDescription>
                  Overview of all nodes in the cluster
                </CardDescription>
              </CardHeader>
              <CardContent>
                {clusterInfo.nodes && clusterInfo.nodes.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Hostname</TableHead>
                        <TableHead>IP Address</TableHead>
                        <TableHead>Port</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>CPU</TableHead>
                        <TableHead>Memory</TableHead>
                        <TableHead>Disk</TableHead>
                        <TableHead>Last Seen</TableHead>
                        {clusterInfo.is_master && <TableHead>Actions</TableHead>}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {clusterInfo.nodes.map((node) => (
                        <TableRow key={node.id}>
                          <TableCell className="font-medium">{node.hostname}</TableCell>
                          <TableCell>{node.ip_address}</TableCell>
                          <TableCell>{node.port ?? 9500}</TableCell>
                          <TableCell>{getRoleBadge(node.role)}</TableCell>
                          <TableCell>{getStatusBadge(node.status)}</TableCell>
                          <TableCell>{node.resources?.cpu_usage?.toFixed(1) ?? 0}%</TableCell>
                          <TableCell>{node.resources?.memory_usage?.toFixed(1) ?? 0}%</TableCell>
                          <TableCell>{node.resources?.disk_usage?.toFixed(1) ?? 0}%</TableCell>
                          <TableCell>
                            {node.last_seen ? new Date(node.last_seen).toLocaleString() : "N/A"}
                          </TableCell>
                          {clusterInfo.is_master && node.role !== "master" && (
                            <TableCell>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => removeNode(node.id)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TableCell>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    No nodes found in cluster
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="health">
            {clusterInfo.is_master ? (
              <ClusterHealthDashboard />
            ) : (
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center text-muted-foreground">
                    Health monitoring is only available on the master node
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="workload">
            {clusterInfo.is_master ? (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Replication</CardTitle>
                      <CardDescription>
                        Manage data replication between cluster nodes
                      </CardDescription>
                    </div>
                    <Dialog open={addReplicationOpen} onOpenChange={setAddReplicationOpen}>
                      <DialogTrigger asChild>
                        <Button>
                          <Plus className="h-4 w-4 mr-2" />
                          Add Replication
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Add Replication Rule</DialogTitle>
                          <DialogDescription>
                            Configure automatic replication between cluster nodes
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4">
                          <div>
                            <Label htmlFor="origin-node">Origin Node</Label>
                            <Select value={replicationOriginNode} onValueChange={setReplicationOriginNode}>
                              <SelectTrigger id="origin-node">
                                <SelectValue placeholder="Select origin node" />
                              </SelectTrigger>
                              <SelectContent>
                                {clusterInfo?.nodes?.filter(n => n.status === "online").map((node) => (
                                  <SelectItem key={node.id} value={node.hostname}>
                                    {node.hostname} ({node.ip_address})
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>

                          <div>
                            <Label htmlFor="dest-node">Destination Node</Label>
                            <Select value={replicationDestNode} onValueChange={setReplicationDestNode}>
                              <SelectTrigger id="dest-node">
                                <SelectValue placeholder="Select destination node" />
                              </SelectTrigger>
                              <SelectContent>
                                {clusterInfo?.nodes?.filter(n => n.status === "online" && n.hostname !== replicationOriginNode).map((node) => (
                                  <SelectItem key={node.id} value={node.hostname}>
                                    {node.hostname} ({node.ip_address})
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>

                          <div>
                            <Label htmlFor="resource">Container/VM</Label>
                            <Select 
                              value={replicationResource} 
                              onValueChange={setReplicationResource}
                              disabled={!replicationOriginNode || loadingResources}
                            >
                              <SelectTrigger id="resource">
                                <SelectValue placeholder={
                                  loadingResources 
                                    ? "Loading resources..." 
                                    : replicationOriginNode 
                                      ? "Select container or VM" 
                                      : "Select origin node first"
                                } />
                              </SelectTrigger>
                              <SelectContent>
                                {availableResources
                                  .filter((resource) => resource.name && resource.name.trim() !== "")
                                  .map((resource) => (
                                    <SelectItem key={resource.name} value={resource.name}>
                                      {resource.name} ({resource.type})
                                    </SelectItem>
                                  ))}
                              </SelectContent>
                            </Select>
                            {replicationOriginNode && !loadingResources && availableResources.length === 0 && (
                              <p className="text-sm text-muted-foreground mt-1">No containers or VMs found on selected node</p>
                            )}
                            {loadingResources && (
                              <p className="text-sm text-muted-foreground mt-1">Loading available resources...</p>
                            )}
                          </div>

                          <div>
                            <Label htmlFor="schedule">Sync Schedule (Cron)</Label>
                            <Input
                              id="schedule"
                              value={replicationCronSchedule}
                              onChange={(e) => setReplicationCronSchedule(e.target.value)}
                              placeholder="0 2 * * *"
                            />
                            <p className="text-sm text-muted-foreground mt-1">
                              Example: 0 2 * * * (Daily at 2:00 AM)
                            </p>
                          </div>
                        </div>
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setAddReplicationOpen(false)}>
                            Cancel
                          </Button>
                          <Button onClick={addReplication}>
                            Add Replication
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </div>
                </CardHeader>
                <CardContent>
                  {replications.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Origin Node</TableHead>
                          <TableHead>Destination Node</TableHead>
                          <TableHead>Name</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Progress</TableHead>
                          <TableHead>Sync Schedule</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {replications.map((replication) => (
                          <TableRow key={replication.id}>
                            <TableCell className="font-medium">{replication.origin_node}</TableCell>
                            <TableCell>{replication.destination_node}</TableCell>
                            <TableCell>{replication.name}</TableCell>
                            <TableCell>
                              <Badge variant="outline">{replication.type}</Badge>
                            </TableCell>
                            <TableCell className="min-w-56">
                              {replicationProgress[replication.id] && replicationProgress[replication.id].status !== "idle" ? (
                                <div className="space-y-1">
                                  <Progress value={replicationProgress[replication.id].progress} />
                                  <div className="text-xs text-muted-foreground">
                                    {replicationProgress[replication.id].progress}% - {replicationProgress[replication.id].message}
                                  </div>
                                </div>
                              ) : (
                                <span className="text-xs text-muted-foreground">-</span>
                              )}
                            </TableCell>
                            <TableCell>{replication.sync_schedule}</TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-2">
                                <Button 
                                  variant="ghost" 
                                  size="sm"
                                  className="text-green-600 hover:text-green-700 hover:bg-green-50"
                                  onClick={() => triggerReplication(replication.id)}
                                >
                                  <Play className="h-4 w-4" />
                                </Button>
                                <Button 
                                  variant="ghost" 
                                  size="sm"
                                  onClick={() => deleteReplication(replication.id)}
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      No replication rules configured
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center text-muted-foreground">
                    Workload distribution management is only available on the master node
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ── High Availability Tab ── */}
          <TabsContent value="ha" className="space-y-4">
            {/* Status cards */}
            <div className="grid gap-4 md:grid-cols-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">HA Status</CardTitle>
                  <ShieldCheck className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={haStatus?.enabled ?? false}
                      onCheckedChange={toggleHa}
                      disabled={haLoading}
                    />
                    <span className="text-sm">{haStatus?.enabled ? "Enabled" : "Disabled"}</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Virtual IP</CardTitle>
                  <Zap className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-lg font-bold">{haStatus?.vip || "—"}</div>
                  <p className="text-xs text-muted-foreground">
                    {haStatus?.vip_owner ? "Owned by this node" : haStatus?.vip ? "Not owned" : "Not configured"}
                  </p>
                  {haStatus?.vip_owner_hostname && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Cluster owner: {haStatus.vip_owner_hostname} ({haStatus.vip_owner_ip || "unknown IP"})
                    </p>
                  )}
                  {haStatus?.vip_ha_interface && haStatus?.vip_interface && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Assigned via dedicated HA interface: {haStatus.vip_ha_interface}
                    </p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Active Master</CardTitle>
                  <Server className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-lg font-bold truncate">{haStatus?.active_master || "—"}</div>
                  <p className="text-xs text-muted-foreground">
                    {haStatus?.last_election
                      ? `Last election: ${new Date(haStatus.last_election).toLocaleString()}`
                      : "No election run yet"}
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Node Health</CardTitle>
                  <Radio className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {haStatus?.alive_nodes ?? 0} / {haStatus?.total_nodes_tracked ?? 0}
                  </div>
                  <p className="text-xs text-muted-foreground">nodes responding</p>
                </CardContent>
              </Card>
            </div>

            {/* Config + Actions row */}
            <div className="flex gap-2 flex-wrap">
              <Dialog open={haConfigOpen} onOpenChange={setHaConfigOpen}>
                <Button variant="outline" onClick={() => setHaConfigOpen(true)}>
                  <SettingsIcon className="h-4 w-4 mr-2" />
                  Configure HA
                </Button>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>High Availability Configuration</DialogTitle>
                    <DialogDescription>
                      Configure VIP, heartbeat settings and node priority
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-2">
                    <div className="space-y-2">
                      <Label htmlFor="ha-vip">Virtual IP Address</Label>
                      <Input
                        id="ha-vip"
                        placeholder="192.168.1.200"
                        value={haVip}
                        onChange={(e) => setHaVip(e.target.value)}
                        disabled={haStatus?.enabled}
                      />
                      <p className="text-xs text-muted-foreground">Floating IP that follows the active master. Include prefix length if needed (e.g. 192.168.1.200/24).</p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="ha-iface">Network Interface</Label>
                      <Input
                        id="ha-iface"
                        placeholder="eth0"
                        value={haVipInterface}
                        onChange={(e) => setHaVipInterface(e.target.value)}
                        disabled={haStatus?.enabled}
                      />
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="ha-interval">Heartbeat Interval (s)</Label>
                        <Input
                          id="ha-interval"
                          type="number"
                          min={1}
                          value={haHeartbeatInterval}
                          onChange={(e) => setHaHeartbeatInterval(e.target.value)}
                          disabled={haStatus?.enabled}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="ha-threshold">Failure Threshold</Label>
                        <Input
                          id="ha-threshold"
                          type="number"
                          min={1}
                          value={haFailureThreshold}
                          onChange={(e) => setHaFailureThreshold(e.target.value)}
                          disabled={haStatus?.enabled}
                        />
                        <p className="text-xs text-muted-foreground">Missed heartbeats before failover</p>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="ha-priority">Node Priority</Label>
                        <Input
                          id="ha-priority"
                          type="number"
                          min={1}
                          value={haPriority}
                          onChange={(e) => setHaPriority(e.target.value)}
                          disabled={haStatus?.enabled}
                        />
                        <p className="text-xs text-muted-foreground">Lower = preferred master</p>
                      </div>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setHaConfigOpen(false)}>Cancel</Button>
                    <Button onClick={saveHaConfig} disabled={haLoading || !!haStatus?.enabled}>Save</Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              {haStatus?.is_master && (
                <Button variant="destructive" onClick={triggerFailover} disabled={haLoading}>
                  <Zap className="h-4 w-4 mr-2" />
                  Trigger Failover
                </Button>
              )}

              {haStatus?.vip && haStatus?.vip_interface && (
                <>
                  {!haStatus.vip_owner ? (
                    <Button variant="outline" onClick={assignVip} disabled={haLoading}>
                      <Zap className="h-4 w-4 mr-2" />
                      Assign VIP to this node
                    </Button>
                  ) : (
                    <Button variant="outline" onClick={releaseVip} disabled={haLoading}>
                      Release VIP
                    </Button>
                  )}
                </>
              )}
            </div>

            {/* Heartbeat table */}
            <Card>
              <CardHeader>
                <CardTitle>Node Heartbeats</CardTitle>
                <CardDescription>Live health status of all tracked cluster nodes</CardDescription>
              </CardHeader>
              <CardContent>
                {haStatus && haStatus.heartbeats.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Hostname</TableHead>
                        <TableHead>IP Address</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Last Heartbeat</TableHead>
                        <TableHead>Age (s)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {haStatus.heartbeats.map((hb) => (
                        <TableRow key={hb.hostname}>
                          <TableCell className="font-medium">{hb.hostname}</TableCell>
                          <TableCell>{hb.ip_address}:{hb.port}</TableCell>
                          <TableCell><Badge variant="secondary">{hb.role}</Badge></TableCell>
                          <TableCell>{hb.priority}</TableCell>
                          <TableCell>
                            <Badge variant={hb.alive ? "success" : "destructive"}>
                              {hb.alive ? "alive" : "unresponsive"}
                            </Badge>
                          </TableCell>
                          <TableCell>{new Date(hb.last_seen).toLocaleTimeString()}</TableCell>
                          <TableCell>{hb.age_seconds}s</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {haStatus?.enabled
                      ? "No heartbeat data yet — waiting for nodes to check in"
                      : "Enable HA to start tracking node health"}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Info box */}
            {!haStatus?.enabled && (
              <Card className="bg-muted/30">
                <CardContent className="pt-6">
                  <div className="space-y-2 text-sm text-muted-foreground">
                    <p className="font-medium text-foreground">How High Availability works in UpservX:</p>
                    <ul className="space-y-1 list-disc list-inside">
                      <li>Each node periodically sends a <strong>heartbeat</strong> to the master.</li>
                      <li>If the master misses <strong>N consecutive heartbeats</strong>, child nodes initiate an election.</li>
                      <li>The node with the <strong>lowest priority value</strong> (configurable) becomes the new master.</li>
                      <li>The new master automatically claims the <strong>Virtual IP (VIP)</strong> so clients stay connected.</li>
                      <li>Configure the same VIP and interface on all nodes in the cluster.</li>
                    </ul>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Standalone Mode</CardTitle>
            <CardDescription>
              This server is currently not part of any cluster
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                To use clustering, you can either create a new cluster and become the master node,
                or join an existing cluster as a child node.
              </p>
              <div className="grid gap-4 md:grid-cols-2">
                <Card className="bg-muted/50">
                  <CardHeader>
                    <CardTitle className="text-base">Master Node</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="text-sm space-y-1 text-muted-foreground">
                      <li>• Manages all child nodes</li>
                      <li>• Distributes workloads</li>
                      <li>• Synchronizes configurations</li>
                      <li>• Generates cluster tokens</li>
                    </ul>
                  </CardContent>
                </Card>
                <Card className="bg-muted/50">
                  <CardHeader>
                    <CardTitle className="text-base">Child Node</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="text-sm space-y-1 text-muted-foreground">
                      <li>• Receives workloads from master</li>
                      <li>• Syncs with master</li>
                      <li>• Reports status back</li>
                      <li>• Requires cluster token</li>
                    </ul>
                  </CardContent>
                </Card>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Debug Dialog */}
      <Dialog open={debugOpen} onOpenChange={setDebugOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle>Cluster Debug Information</DialogTitle>
            <DialogDescription>
              Technical information for troubleshooting cluster issues
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {debugInfo && (
              <pre className="bg-muted p-4 rounded-lg text-xs overflow-auto">
                {JSON.stringify(debugInfo, null, 2)}
              </pre>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
