"use client"

import { useEffect, useState } from "react"
import { apiUrl } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Network, RefreshCw } from "lucide-react"

interface LoadBalancingRecommendation {
  source_node: string
  target_node: string
  load_difference: number
  reason: string
}

/**
 * Read-only workload recommendations. Container replication and migration are
 * intentionally not exposed until the backend can transfer volumes, secrets,
 * networks, and images transactionally with rollback.
 */
export default function WorkloadDistribution() {
  const [recommendations, setRecommendations] = useState<LoadBalancingRecommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(apiUrl("/cluster/load/recommendations"), {
        credentials: "include",
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const data = await response.json()
      setRecommendations(data.recommendations || [])
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Failed to load recommendations")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Network className="h-8 w-8" />
          <div>
            <h1 className="text-3xl font-bold">Workload Distribution</h1>
            <p className="text-muted-foreground">Read-only cluster placement recommendations</p>
          </div>
        </div>
        <Button onClick={loadData} variant="outline" disabled={loading}>
          <RefreshCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <Card>
        <CardHeader>
          <CardTitle>Load Balancing Recommendations</CardTitle>
          <CardDescription>Suggested placements based on current node load.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {!loading && recommendations.length === 0 && (
            <p className="text-sm text-muted-foreground">No recommendations available.</p>
          )}
          {recommendations.map((recommendation, index) => (
            <div key={index} className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <div className="font-medium">
                  {recommendation.source_node} → {recommendation.target_node}
                </div>
                <div className="text-sm text-muted-foreground">{recommendation.reason}</div>
              </div>
              <Badge variant="secondary">Δ {recommendation.load_difference.toFixed(1)}%</Badge>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
