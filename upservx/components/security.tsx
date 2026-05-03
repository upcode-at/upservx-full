"use client"

import { useState, useEffect, useCallback } from "react"
import { apiUrl } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { NotificationContainer } from "@/components/ui/notification"
import {
  ShieldAlert,
  RefreshCw,
  Ban,
  PackageOpen,
  Lock,
  Network,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Bug,
  Search,
} from "lucide-react"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Fail2BanJail {
  name: string
  currently_failed: number
  total_failed: number
  currently_banned: number
  total_banned: number
  banned_ips: string[]
  error?: string
}

interface Fail2BanData {
  available: boolean
  error?: string
  jails: Fail2BanJail[]
}

interface PackageInfo {
  name: string
  current_version: string
  new_version: string
  origin: string
  is_security: boolean
}

interface PackagesData {
  available: boolean
  error?: string
  total: number
  security_updates: number
  packages: PackageInfo[]
}

interface CertInfo {
  path: string
  subject?: string
  issuer?: string
  not_before?: string
  not_after?: string
  fingerprint?: string
  days_until_expiry?: number | null
  expired?: boolean | null
}

interface CertsData {
  total: number
  expired: number
  expiring_soon: number
  certificates: CertInfo[]
}

interface PortInfo {
  proto: string
  state: string
  address: string
  port: string
  process: string
}

interface PortsData {
  available: boolean
  error?: string
  total: number
  ports: PortInfo[]
}

interface CveVuln {
  package: string
  version: string
  vuln_id: string
  cve_id: string
  summary: string
  severity: "critical" | "high" | "medium" | "low" | "unknown"
  cvss_score: number | null
  published: string
}

interface CveData {
  available: boolean
  error?: string
  ecosystem?: string
  packages_scanned?: number
  total_vulns?: number
  severity_counts?: {
    critical: number
    high: number
    medium: number
    low: number
    unknown: number
  }
  vulnerabilities?: CveVuln[]
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <Badge
      variant="outline"
      className={ok ? "border-green-500 text-green-400" : "border-red-500 text-red-400"}
    >
      {ok ? <CheckCircle2 className="mr-1 h-3 w-3" /> : <XCircle className="mr-1 h-3 w-3" />}
      {label}
    </Badge>
  )
}

function DaysUntilBadge({ days }: { days: number | null | undefined }) {
  if (days === null || days === undefined) return <span className="text-muted-foreground">—</span>
  if (days < 0)
    return (
      <Badge variant="destructive" className="text-xs">
        Expired
      </Badge>
    )
  if (days <= 7)
    return (
      <Badge className="bg-red-600 text-white text-xs">
        {days}d
      </Badge>
    )
  if (days <= 30)
    return (
      <Badge className="bg-yellow-500 text-black text-xs">
        {days}d
      </Badge>
    )
  return (
    <Badge variant="outline" className="border-green-500 text-green-400 text-xs">
      {days}d
    </Badge>
  )
}

function SeverityBadge({ severity, score }: { severity: string; score?: number | null }) {
  const map: Record<string, string> = {
    critical: "bg-red-700 text-white",
    high: "bg-red-500 text-white",
    medium: "bg-yellow-500 text-black",
    low: "bg-blue-500 text-white",
    unknown: "bg-muted text-muted-foreground",
  }
  return (
    <Badge className={`text-xs ${map[severity] ?? map.unknown}`}>
      {severity.toUpperCase()}{score != null ? ` ${score.toFixed(1)}` : ""}
    </Badge>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SecurityManagement() {
  const [fail2banData, setFail2banData] = useState<Fail2BanData | null>(null)
  const [packagesData, setPackagesData] = useState<PackagesData | null>(null)
  const [certsData, setCertsData] = useState<CertsData | null>(null)
  const [portsData, setPortsData] = useState<PortsData | null>(null)

  const [cveData, setCveData] = useState<CveData | null>(null)
  const [loadingCve, setLoadingCve] = useState(false)
  const [cveFilter, setCveFilter] = useState<"all" | "critical" | "high" | "medium" | "low">("all")

  const [loadingFail2ban, setLoadingFail2ban] = useState(false)
  const [loadingPackages, setLoadingPackages] = useState(false)
  const [loadingCerts, setLoadingCerts] = useState(false)
  const [loadingPorts, setLoadingPorts] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [packageFilter, setPackageFilter] = useState<"all" | "security">("all")

  // -- Fetch helpers --

  const fetchFail2ban = useCallback(async () => {
    setLoadingFail2ban(true)
    try {
      const res = await fetch(apiUrl("/security/fail2ban"), { credentials: "include" })
      const data = await res.json()
      setFail2banData(data)
    } catch {
      setFail2banData({ available: false, error: "Failed to fetch Fail2Ban data", jails: [] })
    } finally {
      setLoadingFail2ban(false)
    }
  }, [])

  const fetchPackages = useCallback(async () => {
    setLoadingPackages(true)
    try {
      const res = await fetch(apiUrl("/security/packages"), { credentials: "include" })
      const data = await res.json()
      setPackagesData(data)
    } catch {
      setPackagesData({ available: false, error: "Failed to fetch package data", total: 0, security_updates: 0, packages: [] })
    } finally {
      setLoadingPackages(false)
    }
  }, [])

  const fetchCerts = useCallback(async () => {
    setLoadingCerts(true)
    try {
      const res = await fetch(apiUrl("/security/certificates"), { credentials: "include" })
      const data = await res.json()
      setCertsData(data)
    } catch {
      setCertsData({ total: 0, expired: 0, expiring_soon: 0, certificates: [] })
    } finally {
      setLoadingCerts(false)
    }
  }, [])

  const fetchPorts = useCallback(async () => {
    setLoadingPorts(true)
    try {
      const res = await fetch(apiUrl("/security/ports"), { credentials: "include" })
      const data = await res.json()
      setPortsData(data)
    } catch {
      setPortsData({ available: false, error: "Failed to fetch port data", total: 0, ports: [] })
    } finally {
      setLoadingPorts(false)
    }
  }, [])

  const fetchCves = useCallback(async () => {
    setLoadingCve(true)
    try {
      const res = await fetch(apiUrl("/security/cve"), { credentials: "include" })
      const data = await res.json()
      setCveData(data)
    } catch {
      setCveData({ available: false, error: "Failed to reach the CVE scanner" })
    } finally {
      setLoadingCve(false)
    }
  }, [])

  useEffect(() => {
    fetchFail2ban()
    fetchCerts()
    fetchPorts()
    // Packages scan may be slow — load separately
    fetchPackages()
  }, [fetchFail2ban, fetchCerts, fetchPorts, fetchPackages])

  // -- Actions --

  const handleUnban = async (jail: string, ip: string) => {
    try {
      const res = await fetch(apiUrl("/security/fail2ban/unban"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ jail, ip }),
      })
      if (!res.ok) {
        const err = await res.json()
        setError(err.detail || "Unban failed")
        return
      }
      setSuccess(`${ip} successfully unbanned from ${jail}`)
      fetchFail2ban()
    } catch {
      setError("Network error while unbanning IP")
    }
  }

  // -- Render --

  const filteredPackages =
    packagesData?.packages?.filter((p) => packageFilter === "all" || p.is_security) ?? []

  return (
    <div className="space-y-6">
      <NotificationContainer
        error={error}
        success={success}
        onClearError={() => setError(null)}
        onClearSuccess={() => setSuccess(null)}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <ShieldAlert className="h-7 w-7 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Security</h1>
            <p className="text-sm text-muted-foreground">
              Fail2Ban · Package Updates · CVE Scan · Certificates · Open Ports
            </p>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Ban className="h-4 w-4" /> Banned IPs
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {fail2banData?.jails?.reduce((acc, j) => acc + (j.currently_banned ?? 0), 0) ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {fail2banData?.available === false
                ? "Fail2Ban not available"
                : `across ${fail2banData?.jails?.length ?? 0} jails`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <PackageOpen className="h-4 w-4" /> Security Updates
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-yellow-400">
              {packagesData?.security_updates ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {packagesData?.total !== undefined
                ? `${packagesData.total} packages total`
                : "Loading…"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Lock className="h-4 w-4" /> Certificates
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {certsData?.total ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {certsData
                ? `${certsData.expired} expired · ${certsData.expiring_soon} expiring soon`
                : "Loading…"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Network className="h-4 w-4" /> Open Ports
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {portsData?.total ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">listening sockets</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Bug className="h-4 w-4" /> CVEs
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-red-400">
              {cveData?.total_vulns ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {cveData?.severity_counts
                ? `${cveData.severity_counts.critical} critical · ${cveData.severity_counts.high} high`
                : cveData === null ? "Not scanned yet" : "Loading…"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="fail2ban">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="fail2ban" className="flex items-center gap-2">
            <Ban className="h-4 w-4" /> Fail2Ban
          </TabsTrigger>
          <TabsTrigger value="packages" className="flex items-center gap-2">
            <PackageOpen className="h-4 w-4" /> Packages
          </TabsTrigger>
          <TabsTrigger value="certificates" className="flex items-center gap-2">
            <Lock className="h-4 w-4" /> Certificates
          </TabsTrigger>
          <TabsTrigger value="ports" className="flex items-center gap-2">
            <Network className="h-4 w-4" /> Open Ports
          </TabsTrigger>
          <TabsTrigger value="cve" className="flex items-center gap-2">
            <Bug className="h-4 w-4" /> CVE Scan
          </TabsTrigger>
        </TabsList>

        {/* ---------------------------------------------------------------- */}
        {/* Fail2Ban Tab                                                       */}
        {/* ---------------------------------------------------------------- */}
        <TabsContent value="fail2ban" className="space-y-4 mt-4">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold">Fail2Ban Jails</h2>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchFail2ban}
              disabled={loadingFail2ban}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loadingFail2ban ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>

          {fail2banData?.available === false ? (
            <Card>
              <CardContent className="pt-6 text-center text-muted-foreground">
                <AlertTriangle className="mx-auto h-8 w-8 mb-2 text-yellow-500" />
                <p>Fail2Ban is not available on this system.</p>
                <p className="text-xs mt-1">{fail2banData.error}</p>
              </CardContent>
            </Card>
          ) : (fail2banData?.jails ?? []).length === 0 && !loadingFail2ban ? (
            <Card>
              <CardContent className="pt-6 text-center text-muted-foreground">
                No jails configured.
              </CardContent>
            </Card>
          ) : (
            (fail2banData?.jails ?? []).map((jail) => (
              <Card key={jail.name}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-medium">{jail.name}</CardTitle>
                    <div className="flex gap-2 text-xs text-muted-foreground">
                      <span>Failed: {jail.currently_failed} / {jail.total_failed}</span>
                      <span className="border-l border-border pl-2">
                        Banned: <span className="text-red-400 font-semibold">{jail.currently_banned}</span> / {jail.total_banned}
                      </span>
                    </div>
                  </div>
                </CardHeader>
                {jail.banned_ips && jail.banned_ips.length > 0 && (
                  <CardContent>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Banned IP</TableHead>
                          <TableHead className="text-right">Action</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {jail.banned_ips.map((ip) => (
                          <TableRow key={ip}>
                            <TableCell className="font-mono text-sm">{ip}</TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-red-400 border-red-400 hover:bg-red-400/10"
                                onClick={() => handleUnban(jail.name, ip)}
                              >
                                <Ban className="h-3 w-3 mr-1" /> Unban
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                )}
              </Card>
            ))
          )}
        </TabsContent>

        {/* ---------------------------------------------------------------- */}
        {/* Packages Tab                                                       */}
        {/* ---------------------------------------------------------------- */}
        <TabsContent value="packages" className="space-y-4 mt-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold">Upgradeable Packages</h2>
              {packagesData && (
                <>
                  <Badge variant="outline">{packagesData.total} total</Badge>
                  {packagesData.security_updates > 0 && (
                    <Badge className="bg-red-600 text-white">
                      {packagesData.security_updates} security
                    </Badge>
                  )}
                </>
              )}
            </div>
            <div className="flex gap-2">
              <Button
                variant={packageFilter === "all" ? "default" : "outline"}
                size="sm"
                onClick={() => setPackageFilter("all")}
              >
                All
              </Button>
              <Button
                variant={packageFilter === "security" ? "default" : "outline"}
                size="sm"
                onClick={() => setPackageFilter("security")}
              >
                Security only
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchPackages}
                disabled={loadingPackages}
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${loadingPackages ? "animate-spin" : ""}`} />
                Refresh
              </Button>
            </div>
          </div>

          {loadingPackages ? (
            <Card>
              <CardContent className="pt-6 text-center text-muted-foreground">
                <RefreshCw className="mx-auto h-6 w-6 animate-spin mb-2" />
                <p>Scanning packages… (this may take a moment)</p>
              </CardContent>
            </Card>
          ) : packagesData?.available === false ? (
            <Card>
              <CardContent className="pt-6 text-center text-muted-foreground">
                <AlertTriangle className="mx-auto h-8 w-8 mb-2 text-yellow-500" />
                <p>Package scanning is not available.</p>
                <p className="text-xs mt-1">{packagesData.error}</p>
              </CardContent>
            </Card>
          ) : filteredPackages.length === 0 ? (
            <Card>
              <CardContent className="pt-6 text-center text-muted-foreground">
                <CheckCircle2 className="mx-auto h-8 w-8 mb-2 text-green-500" />
                <p>System is up to date.</p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Package</TableHead>
                      <TableHead>Current</TableHead>
                      <TableHead>Available</TableHead>
                      <TableHead>Origin</TableHead>
                      <TableHead>Type</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredPackages.map((pkg) => (
                      <TableRow key={pkg.name}>
                        <TableCell className="font-mono text-sm font-medium">{pkg.name}</TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">{pkg.current_version || "—"}</TableCell>
                        <TableCell className="font-mono text-xs">{pkg.new_version}</TableCell>
                        <TableCell className="text-xs text-muted-foreground max-w-48 truncate">{pkg.origin}</TableCell>
                        <TableCell>
                          {pkg.is_security ? (
                            <Badge className="bg-red-600 text-white text-xs">Security</Badge>
                          ) : (
                            <Badge variant="outline" className="text-xs">Regular</Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ---------------------------------------------------------------- */}
        {/* Certificates Tab                                                   */}
        {/* ---------------------------------------------------------------- */}
        <TabsContent value="certificates" className="space-y-4 mt-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold">SSL/TLS Certificates</h2>
              {certsData && (
                <>
                  <Badge variant="outline">{certsData.total} found</Badge>
                  {certsData.expired > 0 && (
                    <Badge variant="destructive">{certsData.expired} expired</Badge>
                  )}
                  {certsData.expiring_soon > 0 && (
                    <Badge className="bg-yellow-500 text-black">{certsData.expiring_soon} expiring &lt;30d</Badge>
                  )}
                </>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchCerts}
              disabled={loadingCerts}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loadingCerts ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>

          {(certsData?.certificates ?? []).length === 0 && !loadingCerts ? (
            <Card>
              <CardContent className="pt-6 text-center text-muted-foreground">
                No certificates found in common directories.
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Subject</TableHead>
                      <TableHead>Issuer</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead>Days left</TableHead>
                      <TableHead>Path</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(certsData?.certificates ?? []).map((cert, i) => (
                      <TableRow key={i}>
                        <TableCell className="text-sm max-w-52 truncate" title={cert.subject}>
                          {cert.subject?.replace(/.*CN\s*=\s*/, "") || "—"}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground max-w-40 truncate" title={cert.issuer}>
                          {cert.issuer?.replace(/.*O\s*=\s*/, "").replace(/,.*/, "") || "—"}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {cert.not_after || "—"}
                        </TableCell>
                        <TableCell>
                          <DaysUntilBadge days={cert.days_until_expiry} />
                        </TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground max-w-56 truncate" title={cert.path}>
                          {cert.path}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ---------------------------------------------------------------- */}
        {/* Open Ports Tab                                                     */}
        {/* ---------------------------------------------------------------- */}
        <TabsContent value="ports" className="space-y-4 mt-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold">Listening Ports</h2>
              {portsData && (
                <Badge variant="outline">{portsData.total} sockets</Badge>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchPorts}
              disabled={loadingPorts}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loadingPorts ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>

          {portsData?.available === false ? (
            <Card>
              <CardContent className="pt-6 text-center text-muted-foreground">
                <AlertTriangle className="mx-auto h-8 w-8 mb-2 text-yellow-500" />
                <p>Port scanning is not available.</p>
                <p className="text-xs mt-1">{portsData.error}</p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Protocol</TableHead>
                      <TableHead>Address</TableHead>
                      <TableHead>Port</TableHead>
                      <TableHead>State</TableHead>
                      <TableHead>Process</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(portsData?.ports ?? []).map((p, i) => (
                      <TableRow key={i}>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={
                              p.proto === "tcp"
                                ? "border-blue-500 text-blue-400"
                                : "border-purple-500 text-purple-400"
                            }
                          >
                            {p.proto.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {p.address === "*" || p.address === "0.0.0.0" || p.address === "::" ? (
                            <span className="text-yellow-400">{p.address}</span>
                          ) : (
                            p.address
                          )}
                        </TableCell>
                        <TableCell className="font-mono font-semibold text-sm">{p.port}</TableCell>
                        <TableCell>
                          <StatusBadge ok={p.state === "listen" || p.state === "LISTEN"} label={p.state} />
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {p.process || "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ---------------------------------------------------------------- */}
        {/* CVE Scanner Tab                                                    */}
        {/* ---------------------------------------------------------------- */}
        <TabsContent value="cve" className="space-y-4 mt-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold">CVE Vulnerability Scan</h2>
              {cveData?.available && (
                <>
                  <Badge variant="outline">{cveData.packages_scanned} packages scanned</Badge>
                  <Badge variant="outline" className="text-muted-foreground">{cveData.ecosystem}</Badge>
                </>
              )}
            </div>
            <div className="flex gap-2">
              {cveData?.available && (
                <>
                  {(["all", "critical", "high", "medium", "low"] as const).map((f) => (
                    <Button
                      key={f}
                      variant={cveFilter === f ? "default" : "outline"}
                      size="sm"
                      onClick={() => setCveFilter(f)}
                    >
                      {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
                      {f !== "all" && cveData.severity_counts?.[f] !== undefined && (
                        <span className="ml-1 opacity-70">({cveData.severity_counts[f]})</span>
                      )}
                    </Button>
                  ))}
                </>
              )}
              <Button
                variant={cveData === null ? "default" : "outline"}
                size="sm"
                onClick={fetchCves}
                disabled={loadingCve}
              >
                {loadingCve ? (
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Search className="h-4 w-4 mr-2" />
                )}
                {cveData === null ? "Start Scan" : "Re-Scan"}
              </Button>
            </div>
          </div>

          {cveData === null && !loadingCve ? (
            <Card>
              <CardContent className="pt-10 pb-10 text-center text-muted-foreground space-y-3">
                <Bug className="mx-auto h-10 w-10 text-muted-foreground/40" />
                <p className="font-medium">CVE Scan not started yet</p>
                <p className="text-xs">
                  Queries installed packages against the <span className="font-mono">osv.dev</span> vulnerability database.
                  Requires a Debian/Ubuntu system and internet access.
                </p>
              </CardContent>
            </Card>
          ) : loadingCve ? (
            <Card>
              <CardContent className="pt-10 pb-10 text-center text-muted-foreground space-y-3">
                <RefreshCw className="mx-auto h-8 w-8 animate-spin" />
                <p>Scanning packages against OSV.dev… this may take 30–60 seconds.</p>
              </CardContent>
            </Card>
          ) : cveData?.available === false ? (
            <Card>
              <CardContent className="pt-6 text-center text-muted-foreground">
                <AlertTriangle className="mx-auto h-8 w-8 mb-2 text-yellow-500" />
                <p>CVE scan is not available on this system.</p>
                <p className="text-xs mt-1">{cveData.error}</p>
              </CardContent>
            </Card>
          ) : (cveData?.vulnerabilities?.length ?? 0) === 0 ? (
            <Card>
              <CardContent className="pt-6 text-center text-muted-foreground">
                <CheckCircle2 className="mx-auto h-8 w-8 mb-2 text-green-500" />
                <p>No known CVEs found in scanned packages.</p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Severity</TableHead>
                      <TableHead>CVE</TableHead>
                      <TableHead>Package</TableHead>
                      <TableHead>Version</TableHead>
                      <TableHead>Summary</TableHead>
                      <TableHead>Published</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(cveData?.vulnerabilities ?? [])
                      .filter((v) => cveFilter === "all" || v.severity === cveFilter)
                      .map((v, i) => (
                        <TableRow key={i}>
                          <TableCell>
                            <SeverityBadge severity={v.severity} score={v.cvss_score} />
                          </TableCell>
                          <TableCell className="font-mono text-xs font-medium">
                            {v.cve_id || v.vuln_id}
                          </TableCell>
                          <TableCell className="font-mono text-sm">{v.package}</TableCell>
                          <TableCell className="font-mono text-xs text-muted-foreground">{v.version}</TableCell>
                          <TableCell className="text-xs text-muted-foreground max-w-80 truncate" title={v.summary}>
                            {v.summary || "—"}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">{v.published || "—"}</TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
