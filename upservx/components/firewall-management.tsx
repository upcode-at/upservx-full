"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { NotificationContainer } from "@/components/ui/notification"
import { Shield, Plus, Trash2, Download, Activity } from "lucide-react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

interface FirewallRule {
  family: string
  table: string
  chain: string
  expr: unknown[]
  handle: number
  comment?: string
  formatted: string
}

interface FirewallChain {
  family: string
  table: string
  name: string
  type: string
  hook: string
  policy: string
  handle: number
}

interface FirewallStats {
  total_rules: number
  chains: { [key: string]: number }
  packets_processed: number
  bytes_processed: number
}

export default function FirewallManagement() {
  const [rules, setRules] = useState<FirewallRule[]>([])
  const [chains, setChains] = useState<FirewallChain[]>([])
  const [stats, setStats] = useState<FirewallStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Form states
  const [newRule, setNewRule] = useState({
    chain: "input",
    protocol: "",
    port: "",
    source_ip: "",
    destination_ip: "",
    action: "accept",
    comment: ""
  })

  const [portForward, setPortForward] = useState({
    external_port: "",
    internal_ip: "",
    internal_port: "",
    protocol: "tcp",
    comment: ""
  })

  const [masqueradeIface, setMasqueradeIface] = useState("")
  const [policyChange, setPolicyChange] = useState({ chain: "input", policy: "accept" })

  const getApiUrl = (path: string) => {
    if (typeof window === "undefined") return path
    const { protocol, hostname, port } = window.location
    const apiPort = (port === "" || port === "80" || port === "443") ? "" : ":9500"
    return `${protocol}//${hostname}${apiPort}${path}`
  }

  const loadFirewallData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [rulesRes, statsRes] = await Promise.all([
        fetch(getApiUrl("/firewall/rules"), { credentials: "include" }),
        fetch(getApiUrl("/firewall/statistics"), { credentials: "include" })
      ])

      if (!rulesRes.ok || !statsRes.ok) {
        throw new Error("Failed to fetch firewall data")
      }

      const rulesData = await rulesRes.json()
      const statsData = await statsRes.json()

      setRules(rulesData.rules || [])
      setChains(rulesData.chains || [])
      setStats(statsData)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load firewall data")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadFirewallData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const addRule = async () => {
    try {
      setError(null)
      setSuccess(null)

      const payload: Record<string, string | number> = {
        chain: newRule.chain,
        action: newRule.action,
      }

      if (newRule.protocol) payload.protocol = newRule.protocol
      if (newRule.port) payload.port = parseInt(newRule.port)
      if (newRule.source_ip) payload.source_ip = newRule.source_ip
      if (newRule.destination_ip) payload.destination_ip = newRule.destination_ip
      if (newRule.comment) payload.comment = newRule.comment

      const response = await fetch(getApiUrl("/firewall/rules"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to add rule")
      }

      setSuccess("Rule added successfully")
      setNewRule({
        chain: "input",
        protocol: "",
        port: "",
        source_ip: "",
        destination_ip: "",
        action: "accept",
        comment: ""
      })
      loadFirewallData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add rule")
    }
  }

  const deleteRule = async (chain: string, handle: number) => {
    if (!confirm("Are you sure you want to delete this rule?")) return

    try {
      setError(null)
      const response = await fetch(getApiUrl("/firewall/rules"), {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ chain, handle })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to delete rule")
      }

      setSuccess("Rule deleted successfully")
      loadFirewallData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete rule")
    }
  }

  const flushChain = async (chain: string) => {
    if (!confirm(`Are you sure you want to flush all rules from ${chain} chain?`)) return

    try {
      setError(null)
      const response = await fetch(getApiUrl(`/firewall/chains/${chain}/flush`), {
        method: "POST",
        credentials: "include"
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to flush chain")
      }

      setSuccess(`Chain ${chain} flushed successfully`)
      loadFirewallData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to flush chain")
    }
  }

  const setChainPolicy = async () => {
    if (!confirm(`Set ${policyChange.chain} policy to ${policyChange.policy}?`)) return

    try {
      setError(null)
      const response = await fetch(getApiUrl("/firewall/chains/policy"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(policyChange)
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to set policy")
      }

      setSuccess(`Policy set to ${policyChange.policy} for ${policyChange.chain}`)
      loadFirewallData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set policy")
    }
  }

  const addPortForward = async () => {
    try {
      setError(null)
      const response = await fetch(getApiUrl("/firewall/port-forward"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          external_port: parseInt(portForward.external_port),
          internal_ip: portForward.internal_ip,
          internal_port: parseInt(portForward.internal_port),
          protocol: portForward.protocol,
          comment: portForward.comment
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to add port forward")
      }

      setSuccess("Port forward added successfully")
      setPortForward({
        external_port: "",
        internal_ip: "",
        internal_port: "",
        protocol: "tcp",
        comment: ""
      })
      loadFirewallData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add port forward")
    }
  }

  const enableMasquerade = async () => {
    if (!masqueradeIface) {
      setError("Please enter an interface name")
      return
    }

    try {
      setError(null)
      const response = await fetch(getApiUrl("/firewall/masquerade"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ interface: masqueradeIface })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to enable masquerade")
      }

      setSuccess(`Masquerade enabled for ${masqueradeIface}`)
      setMasqueradeIface("")
      loadFirewallData()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to enable masquerade")
    }
  }

  const saveRules = async () => {
    try {
      setError(null)
      const response = await fetch(getApiUrl("/firewall/save"), {
        method: "POST",
        credentials: "include"
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to save rules")
      }

      setSuccess("Firewall rules saved successfully")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save rules")
    }
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B"
    const k = 1024
    const sizes = ["B", "KB", "MB", "GB", "TB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Shield className="h-12 w-12 animate-pulse mx-auto mb-4" />
          <p>Loading firewall configuration...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="h-8 w-8" />
          <div>
            <h1 className="text-3xl font-bold">Firewall Management</h1>
            <p className="text-muted-foreground">Manage nftables firewall rules and policies</p>
          </div>
        </div>
        <Button onClick={saveRules} variant="outline">
          <Download className="h-4 w-4 mr-2" />
          Save Rules
        </Button>
      </div>

      <NotificationContainer
        error={error}
        success={success}
        onClearError={() => setError(null)}
        onClearSuccess={() => setSuccess(null)}
      />

      {/* Statistics */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Rules</CardTitle>
              <Shield className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_rules}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Chains</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.chains ? Object.keys(stats.chains).length : 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Packets Processed</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{(stats.packets_processed ?? 0).toLocaleString()}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Data Processed</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{formatBytes(stats.bytes_processed ?? 0)}</div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="rules" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="rules">Firewall Rules</TabsTrigger>
          <TabsTrigger value="chains">Chain Policies</TabsTrigger>
          <TabsTrigger value="nat">NAT & Port Forwarding</TabsTrigger>
        </TabsList>

        <TabsContent value="rules" className="space-y-4">
          {/* Add Rule Form */}
          <Card>
            <CardHeader>
              <CardTitle>Add Firewall Rule</CardTitle>
              <CardDescription>Create a new firewall rule for packet filtering</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="chain">Chain</Label>
                  <Select value={newRule.chain} onValueChange={(value) => setNewRule({ ...newRule, chain: value })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="input">Input</SelectItem>
                      <SelectItem value="output">Output</SelectItem>
                      <SelectItem value="forward">Forward</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="protocol">Protocol</Label>
                  <Select value={newRule.protocol || "any"} onValueChange={(value) => setNewRule({ ...newRule, protocol: value === "any" ? "" : value })}>
                    <SelectTrigger>
                      <SelectValue placeholder="Any" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="any">Any</SelectItem>
                      <SelectItem value="tcp">TCP</SelectItem>
                      <SelectItem value="udp">UDP</SelectItem>
                      <SelectItem value="icmp">ICMP</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="port">Port</Label>
                  <Input
                    id="port"
                    placeholder="e.g., 80"
                    value={newRule.port}
                    onChange={(e) => setNewRule({ ...newRule, port: e.target.value })}
                  />
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="source_ip">Source IP (optional)</Label>
                  <Input
                    id="source_ip"
                    placeholder="e.g., 192.168.1.0/24"
                    value={newRule.source_ip}
                    onChange={(e) => setNewRule({ ...newRule, source_ip: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="destination_ip">Destination IP (optional)</Label>
                  <Input
                    id="destination_ip"
                    placeholder="e.g., 10.0.0.1"
                    value={newRule.destination_ip}
                    onChange={(e) => setNewRule({ ...newRule, destination_ip: e.target.value })}
                  />
                </div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="action">Action</Label>
                  <Select value={newRule.action} onValueChange={(value) => setNewRule({ ...newRule, action: value })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="accept">Accept</SelectItem>
                      <SelectItem value="drop">Drop</SelectItem>
                      <SelectItem value="reject">Reject</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="comment">Comment</Label>
                  <Input
                    id="comment"
                    placeholder="Rule description"
                    value={newRule.comment}
                    onChange={(e) => setNewRule({ ...newRule, comment: e.target.value })}
                  />
                </div>
              </div>
              <Button onClick={addRule}>
                <Plus className="h-4 w-4 mr-2" />
                Add Rule
              </Button>
            </CardContent>
          </Card>

          {/* Rules List */}
          <Card>
            <CardHeader>
              <CardTitle>Active Rules</CardTitle>
              <CardDescription>Currently configured firewall rules</CardDescription>
            </CardHeader>
            <CardContent>
              {rules.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">No rules configured</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Chain</TableHead>
                      <TableHead>Rule</TableHead>
                      <TableHead>Comment</TableHead>
                      <TableHead>Handle</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rules.map((rule, idx) => (
                      <TableRow key={idx}>
                        <TableCell>
                          <Badge variant="outline">{rule.chain}</Badge>
                        </TableCell>
                        <TableCell className="font-mono text-sm">{rule.formatted}</TableCell>
                        <TableCell>{rule.comment || "-"}</TableCell>
                        <TableCell>{rule.handle}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => deleteRule(rule.chain, rule.handle)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="chains" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Chain Policies</CardTitle>
              <CardDescription>Set default policies for firewall chains</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-2">
                  <Label>Chain</Label>
                  <Select value={policyChange.chain} onValueChange={(value) => setPolicyChange({ ...policyChange, chain: value })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="input">Input</SelectItem>
                      <SelectItem value="output">Output</SelectItem>
                      <SelectItem value="forward">Forward</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Policy</Label>
                  <Select value={policyChange.policy} onValueChange={(value) => setPolicyChange({ ...policyChange, policy: value })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="accept">Accept</SelectItem>
                      <SelectItem value="drop">Drop</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end">
                  <Button onClick={setChainPolicy}>Set Policy</Button>
                </div>
              </div>

              {/* Current Chains */}
              <div className="mt-6">
                <h3 className="text-lg font-semibold mb-4">Current Chain Configuration</h3>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Chain</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Hook</TableHead>
                      <TableHead>Policy</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {chains.map((chain, idx) => (
                      <TableRow key={idx}>
                        <TableCell><Badge>{chain.name}</Badge></TableCell>
                        <TableCell>{chain.type}</TableCell>
                        <TableCell>{chain.hook}</TableCell>
                        <TableCell>
                          <Badge variant={chain.policy === "accept" ? "default" : "destructive"}>
                            {chain.policy}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => flushChain(chain.name)}
                          >
                            Flush
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="nat" className="space-y-4">
          {/* Port Forwarding */}
          <Card>
            <CardHeader>
              <CardTitle>Port Forwarding (DNAT)</CardTitle>
              <CardDescription>Forward external ports to internal services</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-4">
                <div className="space-y-2">
                  <Label>External Port</Label>
                  <Input
                    type="number"
                    placeholder="e.g., 8080"
                    value={portForward.external_port}
                    onChange={(e) => setPortForward({ ...portForward, external_port: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Internal IP</Label>
                  <Input
                    placeholder="e.g., 192.168.1.100"
                    value={portForward.internal_ip}
                    onChange={(e) => setPortForward({ ...portForward, internal_ip: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Internal Port</Label>
                  <Input
                    type="number"
                    placeholder="e.g., 80"
                    value={portForward.internal_port}
                    onChange={(e) => setPortForward({ ...portForward, internal_port: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Protocol</Label>
                  <Select value={portForward.protocol} onValueChange={(value) => setPortForward({ ...portForward, protocol: value })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="tcp">TCP</SelectItem>
                      <SelectItem value="udp">UDP</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label>Comment</Label>
                <Input
                  placeholder="Port forward description"
                  value={portForward.comment}
                  onChange={(e) => setPortForward({ ...portForward, comment: e.target.value })}
                />
              </div>
              <Button onClick={addPortForward}>
                <Plus className="h-4 w-4 mr-2" />
                Add Port Forward
              </Button>
            </CardContent>
          </Card>

          {/* Masquerading */}
          <Card>
            <CardHeader>
              <CardTitle>Masquerading (SNAT)</CardTitle>
              <CardDescription>Enable NAT masquerading for an interface</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-4">
                <div className="flex-1 space-y-2">
                  <Label>Network Interface</Label>
                  <Input
                    placeholder="e.g., eth0, wlan0"
                    value={masqueradeIface}
                    onChange={(e) => setMasqueradeIface(e.target.value)}
                  />
                </div>
                <div className="flex items-end">
                  <Button onClick={enableMasquerade}>Enable Masquerade</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
