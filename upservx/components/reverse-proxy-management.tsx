"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { apiUrl } from "@/lib/api"
import { Shield, Plus, Trash2, RefreshCw, CheckCircle2, XCircle, AlertCircle } from "lucide-react"

interface ProxyConfig {
  domain: string
  backend_host: string
  backend_port: number
  frontend_port: number
  ssl_enabled: boolean
  force_ssl: boolean
  config_file?: string
}

interface Certificate {
  name: string
  domains: string
  expiry: string
  cert_path?: string
}

interface ProxyStatus {
  nginx: {
    installed: boolean
    active: boolean
    enabled: boolean
  }
  certbot_installed: boolean
}

export default function ReverseProxyManagement() {
  const [proxyStatus, setProxyStatus] = useState<ProxyStatus | null>(null)
  const [proxyConfigs, setProxyConfigs] = useState<ProxyConfig[]>([])
  const [certificates, setCertificates] = useState<Certificate[]>([])
  const [loading, setLoading] = useState(false)
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [showCertDialog, setShowCertDialog] = useState(false)

  // Form states
  const [domain, setDomain] = useState("")
  const [backendHost, setBackendHost] = useState("127.0.0.1")
  const [backendPort, setBackendPort] = useState(8000)
  const [frontendPort, setFrontendPort] = useState(3000)
  const [sslEnabled, setSslEnabled] = useState(false)
  const [forceSsl, setForceSsl] = useState(false)
  
  const [certDomain, setCertDomain] = useState("")
  const [certEmail, setCertEmail] = useState("")

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [statusRes, configsRes, certsRes] = await Promise.all([
        fetch(apiUrl("/proxy/status")),
        fetch(apiUrl("/proxy/configs")),
        fetch(apiUrl("/proxy/certificates"))
      ])

      if (statusRes.ok) setProxyStatus(await statusRes.json())
      if (configsRes.ok) {
        const data = await configsRes.json()
        setProxyConfigs(data.configs || [])
      }
      if (certsRes.ok) {
        const data = await certsRes.json()
        setCertificates(data.certificates || [])
      }
    } catch (error) {
      console.error("Failed to load proxy data:", error)
    }
  }

  const createProxyConfig = async () => {
    if (!domain) {
      alert("Please enter a domain")
      return
    }

    setLoading(true)
    try {
      const res = await fetch(apiUrl("/proxy/configs"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain,
          backend_host: backendHost,
          backend_port: backendPort,
          frontend_port: frontendPort,
          ssl_enabled: sslEnabled,
          force_ssl: forceSsl
        })
      })

      const data = await res.json()
      
      if (data.success) {
        alert("Proxy configuration created successfully!")
        setShowAddDialog(false)
        resetForm()
        await loadData()
      } else {
        alert(`Failed to create config: ${data.message}`)
      }
    } catch (error) {
      alert("Failed to create proxy configuration")
    } finally {
      setLoading(false)
    }
  }

  const deleteProxyConfig = async (domain: string) => {
    if (!confirm(`Delete proxy configuration for ${domain}?`)) return

    setLoading(true)
    try {
      const res = await fetch(apiUrl(`/proxy/configs/${domain}`), { method: "DELETE" })
      const data = await res.json()
      
      if (data.success) {
        alert("Configuration deleted successfully!")
        await loadData()
      } else {
        alert(`Failed to delete: ${data.message}`)
      }
    } catch (error) {
      alert("Failed to delete configuration")
    } finally {
      setLoading(false)
    }
  }

  const obtainCertificate = async () => {
    if (!certDomain || !certEmail) {
      alert("Please enter domain and email")
      return
    }

    setLoading(true)
    try {
      const res = await fetch(apiUrl("/proxy/certificates/obtain"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain: certDomain,
          email: certEmail
        })
      })

      const data = await res.json()
      
      if (data.success) {
        alert("Certificate obtained successfully!")
        setShowCertDialog(false)
        setCertDomain("")
        setCertEmail("")
        await loadData()
      } else {
        alert(`Failed to obtain certificate: ${data.message}`)
      }
    } catch (error) {
      alert("Failed to obtain certificate")
    } finally {
      setLoading(false)
    }
  }

  const renewCertificates = async () => {
    setLoading(true)
    try {
      const res = await fetch(apiUrl("/proxy/certificates/renew"), { method: "POST" })
      const data = await res.json()
      
      if (data.success) {
        alert("Certificates renewed successfully!")
        await loadData()
      } else {
        alert(`Renewal failed: ${data.message}`)
      }
    } catch (error) {
      alert("Failed to renew certificates")
    } finally {
      setLoading(false)
    }
  }

  const revokeCertificate = async (domain: string) => {
    if (!confirm(`Revoke certificate for ${domain}?`)) return

    setLoading(true)
    try {
      const res = await fetch(apiUrl(`/proxy/certificates/${domain}`), { method: "DELETE" })
      const data = await res.json()
      
      if (data.success) {
        alert("Certificate revoked successfully!")
        await loadData()
      } else {
        alert(`Revocation failed: ${data.message}`)
      }
    } catch (error) {
      alert("Failed to revoke certificate")
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setDomain("")
    setBackendHost("127.0.0.1")
    setBackendPort(8000)
    setFrontendPort(3000)
    setSslEnabled(false)
    setForceSsl(false)
  }

  return (
    <div className="space-y-6">
      {/* Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Reverse Proxy Status
          </CardTitle>
          <CardDescription>
            Nginx and Let's Encrypt SSL certificate management
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {proxyStatus && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Nginx Installed</Label>
                <div className="flex items-center gap-2">
                  {proxyStatus.nginx.installed ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-500" />
                  )}
                  <span className="text-sm">{proxyStatus.nginx.installed ? "Yes" : "No"}</span>
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Nginx Active</Label>
                <div className="flex items-center gap-2">
                  {proxyStatus.nginx.active ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-500" />
                  )}
                  <span className="text-sm">{proxyStatus.nginx.active ? "Yes" : "No"}</span>
                </div>
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Certbot Installed</Label>
                <div className="flex items-center gap-2">
                  {proxyStatus.certbot_installed ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-500" />
                  )}
                  <span className="text-sm">{proxyStatus.certbot_installed ? "Yes" : "No"}</span>
                </div>
              </div>
            </div>
          )}

          {proxyStatus && (!proxyStatus.nginx.installed || !proxyStatus.nginx.active || !proxyStatus.certbot_installed) && (
            <div className="p-4 bg-yellow-50 dark:bg-yellow-950 rounded-lg space-y-2">
              <div className="flex gap-2">
                <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
                <div className="space-y-2 text-sm">
                  <p className="font-semibold text-yellow-600 dark:text-yellow-400">Required services missing or not running</p>
                  {!proxyStatus.nginx.installed && (
                    <p>• Nginx not installed: <code className="bg-yellow-100 dark:bg-yellow-900 px-2 py-1 rounded">sudo apt install nginx</code></p>
                  )}
                  {proxyStatus.nginx.installed && !proxyStatus.nginx.active && (
                    <p>• Nginx not running: <code className="bg-yellow-100 dark:bg-yellow-900 px-2 py-1 rounded">sudo systemctl enable --now nginx</code></p>
                  )}
                  {!proxyStatus.certbot_installed && (
                    <p>• Certbot not installed: <code className="bg-yellow-100 dark:bg-yellow-900 px-2 py-1 rounded">sudo apt install certbot python3-certbot-nginx</code></p>
                  )}
                </div>
              </div>
            </div>
          )}
          
          <div className="flex gap-2">
            <Button onClick={loadData} variant="outline" size="icon">
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Proxy Configurations */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Proxy Configurations</CardTitle>
              <CardDescription>Manage reverse proxy configurations for your domains</CardDescription>
            </div>
            <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
              <DialogTrigger asChild>
                <Button disabled={!proxyStatus?.nginx.installed || !proxyStatus?.nginx.active}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Configuration
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create Proxy Configuration</DialogTitle>
                  <DialogDescription>Configure reverse proxy for a domain</DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Domain</Label>
                    <Input
                      placeholder="example.com"
                      value={domain}
                      onChange={(e) => setDomain(e.target.value)}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Backend Host</Label>
                      <Input
                        value={backendHost}
                        onChange={(e) => setBackendHost(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Backend Port</Label>
                      <Input
                        type="number"
                        value={backendPort}
                        onChange={(e) => setBackendPort(parseInt(e.target.value))}
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Frontend Port</Label>
                    <Input
                      type="number"
                      value={frontendPort}
                      onChange={(e) => setFrontendPort(parseInt(e.target.value))}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label>SSL Enabled</Label>
                    <Switch checked={sslEnabled} onCheckedChange={setSslEnabled} />
                  </div>
                  {sslEnabled && (
                    <div className="flex items-center justify-between">
                      <Label>Force HTTPS</Label>
                      <Switch checked={forceSsl} onCheckedChange={setForceSsl} />
                    </div>
                  )}
                  <Button onClick={createProxyConfig} disabled={loading} className="w-full">
                    Create Configuration
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Domain</TableHead>
                <TableHead>Backend</TableHead>
                <TableHead>Frontend Port</TableHead>
                <TableHead>SSL</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {proxyConfigs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground">
                    No proxy configurations
                  </TableCell>
                </TableRow>
              ) : (
                proxyConfigs.map((config) => (
                  <TableRow key={config.domain}>
                    <TableCell className="font-medium">{config.domain}</TableCell>
                    <TableCell>{config.backend_host}:{config.backend_port}</TableCell>
                    <TableCell>{config.frontend_port}</TableCell>
                    <TableCell>
                      {config.ssl_enabled ? (
                        <Badge variant="default">Enabled</Badge>
                      ) : (
                        <Badge variant="secondary">Disabled</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => deleteProxyConfig(config.domain)}
                        disabled={loading}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* SSL Certificates */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>SSL Certificates</CardTitle>
              <CardDescription>Manage Let's Encrypt SSL certificates</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button 
                onClick={renewCertificates} 
                variant="outline" 
                disabled={loading || !proxyStatus?.certbot_installed || !proxyStatus?.nginx.active}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Renew All
              </Button>
              <Dialog open={showCertDialog} onOpenChange={setShowCertDialog}>
                <DialogTrigger asChild>
                  <Button disabled={!proxyStatus?.certbot_installed || !proxyStatus?.nginx.active}>
                    <Plus className="h-4 w-4 mr-2" />
                    Obtain Certificate
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Obtain SSL Certificate</DialogTitle>
                    <DialogDescription>Get a free Let's Encrypt SSL certificate</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>Domain</Label>
                      <Input
                        placeholder="example.com"
                        value={certDomain}
                        onChange={(e) => setCertDomain(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Email</Label>
                      <Input
                        type="email"
                        placeholder="admin@example.com"
                        value={certEmail}
                        onChange={(e) => setCertEmail(e.target.value)}
                      />
                    </div>
                    <div className="p-3 bg-blue-50 dark:bg-blue-950 rounded-lg">
                      <div className="flex gap-2">
                        <AlertCircle className="h-5 w-5 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                        <p className="text-sm text-blue-600 dark:text-blue-400">
                          Make sure the domain points to this server and port 80 is accessible.
                        </p>
                      </div>
                    </div>
                    <Button onClick={obtainCertificate} disabled={loading} className="w-full">
                      Obtain Certificate
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Domains</TableHead>
                <TableHead>Expiry</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {certificates.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No SSL certificates
                  </TableCell>
                </TableRow>
              ) : (
                certificates.map((cert) => (
                  <TableRow key={cert.name}>
                    <TableCell className="font-medium">{cert.name}</TableCell>
                    <TableCell>{cert.domains}</TableCell>
                    <TableCell>{cert.expiry}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => revokeCertificate(cert.name)}
                        disabled={loading}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
