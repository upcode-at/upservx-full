"use client"

import { useState, useEffect } from "react"
import { apiUrl } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { NotificationContainer } from "@/components/ui/notification"
import { Server, Plus, Trash2, Network, Database, Settings as SettingsIcon, Activity, GitBranch } from "lucide-react"
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
  cluster_token?: string
  nodes: ClusterNode[]
}

export default function ClusterManagement() {
  const [clusterInfo, setClusterInfo] = useState<ClusterInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Dialog states
  const [createClusterOpen, setCreateClusterOpen] = useState(false)
  const [joinClusterOpen, setJoinClusterOpen] = useState(false)
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugInfo, setDebugInfo] = useState<any>(null)

  // Form states
  const [clusterName, setClusterName] = useState("")
  const [masterIp, setMasterIp] = useState("")
  const [masterPort, setMasterPort] = useState("9500")
  const [joinToken, setJoinToken] = useState("")

  // Use the global apiUrl function
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
      setMasterPort("9500")
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

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "success" | "secondary" | "destructive"> = {
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

  // Calculate total containers and VMs across all nodes
  const totalContainers = clusterInfo?.nodes?.reduce((sum, node) => {
    const count = node.resources?.total_containers || 0
    console.log(`[CLUSTER] Node ${node.hostname}: total_containers=${count}`, node.resources)
    return sum + count
  }, 0) || 0

  const runningContainers = clusterInfo?.nodes?.reduce((sum, node) => {
    const count = node.resources?.running_containers || 0
    console.log(`[CLUSTER] Node ${node.hostname}: running_containers=${count}`)
    return sum + count
  }, 0) || 0

  const totalVMs = clusterInfo?.nodes?.reduce((sum, node) => {
    const count = node.resources?.total_vms || 0
    console.log(`[CLUSTER] Node ${node.hostname}: total_vms=${count}`)
    return sum + count
  }, 0) || 0

  const runningVMs = clusterInfo?.nodes?.reduce((sum, node) => {
    const count = node.resources?.running_vms || 0
    console.log(`[CLUSTER] Node ${node.hostname}: running_vms=${count}`)
    return sum + count
  }, 0) || 0

  console.log(`[CLUSTER] Totals: containers=${totalContainers}/${runningContainers}, vms=${totalVMs}/${runningVMs}`)

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
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList>
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
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            {/* Cluster Status Overview */}
            <div className="grid gap-4 md:grid-cols-5">
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

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Cluster Token</CardTitle>
                  <SettingsIcon className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  {clusterInfo?.is_master && clusterInfo?.cluster_token ? (
                    <>
                      <div className="text-sm font-mono break-all">{clusterInfo.cluster_token}</div>
                      <p className="text-xs text-muted-foreground mt-1">
                        For new nodes
                      </p>
                    </>
                  ) : (
                    <div className="text-sm text-muted-foreground">N/A</div>
                  )}
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
                  <CardTitle>Workload Distribution</CardTitle>
                  <CardDescription>
                    Manage workload distribution across cluster nodes
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-center py-8 text-muted-foreground">
                    Content coming soon
                  </div>
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
