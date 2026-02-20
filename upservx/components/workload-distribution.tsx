"use client"

import { useState, useEffect } from "react"
import { apiUrl } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { NotificationContainer } from "@/components/ui/notification"
import { Network, GitBranch, Settings, RefreshCw } from "lucide-react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface LoadBalancingRecommendation {
  source_node: string
  target_node: string
  load_difference: number
  reason: string
}

interface SyncRule {
  service_name: string
  strategy: string
  target_nodes: string[]
  replica_count: number
}

interface ContainerDistribution {
  [nodeId: string]: string[]
}

export default function WorkloadDistribution() {
  const [recommendations, setRecommendations] = useState<LoadBalancingRecommendation[]>([])
  const [syncRules, setSyncRules] = useState<{ [key: string]: SyncRule }>({})
  const [containerDistribution, setContainerDistribution] = useState<ContainerDistribution>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [addRuleOpen, setAddRuleOpen] = useState(false)

  const [serviceName, setServiceName] = useState("")
  const [strategy, setStrategy] = useState("distribute")
  const [replicaCount, setReplicaCount] = useState("1")

  const getApiUrl = apiUrl

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [recsRes, rulesRes, distRes] = await Promise.all([
        fetch(getApiUrl("/cluster/load/recommendations"), { credentials: "include" }),
        fetch(getApiUrl("/cluster/sync/rules"), { credentials: "include" }),
        fetch(getApiUrl("/cluster/containers/distribution"), { credentials: "include" })
      ])

      if (recsRes.ok) {
        const data = await recsRes.json()
        setRecommendations(data.recommendations || [])
      }

      if (rulesRes.ok) {
        const data = await rulesRes.json()
        setSyncRules(data.rules || {})
      }

      if (distRes.ok) {
        const data = await distRes.json()
        setContainerDistribution(data.distribution || {})
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const addSyncRule = async () => {
    try {
      setError(null)
      setSuccess(null)

      const response = await fetch(getApiUrl("/cluster/sync/rules"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          service_name: serviceName,
          strategy: strategy,
          replica_count: parseInt(replicaCount)
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to add sync rule")
      }

      setSuccess("Sync rule added successfully")
      setAddRuleOpen(false)
      setServiceName("")
      setStrategy("distribute")
      setReplicaCount("1")
      loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add sync rule")
    }
  }

  const removeSyncRule = async (serviceName: string) => {
    if (!confirm(`Remove sync rule for ${serviceName}?`)) return

    try {
      setError(null)

      const response = await fetch(getApiUrl(`/cluster/sync/rules/${serviceName}`), {
        method: "DELETE",
        credentials: "include"
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to remove sync rule")
      }

      setSuccess("Sync rule removed successfully")
      loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove sync rule")
    }
  }

  const executeSync = async () => {
    try {
      setError(null)
      setSuccess(null)

      const response = await fetch(getApiUrl("/cluster/sync/execute"), {
        method: "POST",
        credentials: "include"
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to execute synchronization")
      }

      setSuccess("Container synchronization executed successfully")
      loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to execute synchronization")
    }
  }

  const getStrategyBadge = (strategy: string) => {
    const colors: { [key: string]: string } = {
      replicate: "bg-blue-500",
      distribute: "bg-green-500",
      active_passive: "bg-yellow-500",
      custom: "bg-purple-500"
    }

    return (
      <Badge className={colors[strategy] || "bg-gray-500"}>
        {strategy}
      </Badge>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Network className="h-12 w-12 animate-pulse" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GitBranch className="h-8 w-8" />
          <div>
            <h1 className="text-3xl font-bold">Workload Distribution</h1>
            <p className="text-muted-foreground">Manage container deployment across cluster</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button onClick={loadData} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={executeSync}>
            <Settings className="h-4 w-4 mr-2" />
            Execute Sync
          </Button>
        </div>
      </div>

      <NotificationContainer
        error={error}
        success={success}
        onClearError={() => setError(null)}
        onClearSuccess={() => setSuccess(null)}
      />

      {/* Load Balancing Recommendations */}
      {recommendations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Load Balancing Recommendations</CardTitle>
            <CardDescription>
              Suggested workload rebalancing for optimal cluster performance
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recommendations.map((rec, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <div className="font-medium">
                      Move workload: {rec.source_node} → {rec.target_node}
                    </div>
                    <div className="text-sm text-muted-foreground">{rec.reason}</div>
                  </div>
                  <Badge variant="secondary">
                    Δ {rec.load_difference.toFixed(1)}%
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Synchronization Rules */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Synchronization Rules</CardTitle>
              <CardDescription>
                Define how containers are distributed across the cluster
              </CardDescription>
            </div>
            <Dialog open={addRuleOpen} onOpenChange={setAddRuleOpen}>
              <DialogTrigger asChild>
                <Button>Add Rule</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Synchronization Rule</DialogTitle>
                  <DialogDescription>
                    Define how a service should be distributed
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="service-name">Service Name</Label>
                    <Input
                      id="service-name"
                      placeholder="my-service"
                      value={serviceName}
                      onChange={(e) => setServiceName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="strategy">Strategy</Label>
                    <Select value={strategy} onValueChange={setStrategy}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="distribute">Distribute (Load Balance)</SelectItem>
                        <SelectItem value="replicate">Replicate (All Nodes)</SelectItem>
                        <SelectItem value="active_passive">Active-Passive</SelectItem>
                        <SelectItem value="custom">Custom</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="replica-count">Replica Count</Label>
                    <Input
                      id="replica-count"
                      type="number"
                      min="1"
                      value={replicaCount}
                      onChange={(e) => setReplicaCount(e.target.value)}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setAddRuleOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={addSyncRule} disabled={!serviceName}>
                    Add Rule
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </CardHeader>
        <CardContent>
          {Object.keys(syncRules).length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Service Name</TableHead>
                  <TableHead>Strategy</TableHead>
                  <TableHead>Replica Count</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(syncRules).map(([name, rule]) => (
                  <TableRow key={name}>
                    <TableCell className="font-medium">{rule.service_name}</TableCell>
                    <TableCell>{getStrategyBadge(rule.strategy)}</TableCell>
                    <TableCell>{rule.replica_count}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeSyncRule(rule.service_name)}
                      >
                        Remove
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No synchronization rules configured
            </div>
          )}
        </CardContent>
      </Card>

      {/* Container Distribution */}
      <Card>
        <CardHeader>
          <CardTitle>Container Distribution</CardTitle>
          <CardDescription>
            Current distribution of containers across cluster nodes
          </CardDescription>
        </CardHeader>
        <CardContent>
          {Object.keys(containerDistribution).length > 0 ? (
            <div className="space-y-4">
              {Object.entries(containerDistribution).map(([nodeId, containers]) => (
                <div key={nodeId} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-medium">{nodeId}</h3>
                    <Badge variant="secondary">{containers.length} containers</Badge>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {containers.map((container, idx) => (
                      <Badge key={idx} variant="outline">
                        {container}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No containers distributed yet
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
