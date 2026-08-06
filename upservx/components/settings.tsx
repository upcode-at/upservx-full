"use client"

import { useEffect, useState, useRef } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { NotificationContainer } from "@/components/ui/notification"
import { Save, Key, RefreshCw, Bell, Mail, Webhook, Send, Plus, X, Paintbrush, Upload, Trash2 } from "lucide-react"
import { apiUrl, waitForJob } from "@/lib/api"
import { useAuth } from "@/components/auth-provider"

export function Settings() {
  const { permissions } = useAuth()

  interface SettingsData {
    hostname: string
    timezone: string
    auto_updates: boolean
    monitoring: boolean
    ssh_port: number
    deny_root_login: boolean
  }

  interface ApiTokenMetadata {
    id: string
    name: string
    role: "admin" | "operator" | "read-only"
    scopes: string[]
    created_at: string
    expires_at: number | null
    revoked_at: string | null
  }

  const [settings, setSettings] = useState<SettingsData>({
    hostname: "",
    timezone: "utc",
    auto_updates: false,
    monitoring: false,
    ssh_port: 22,
    deny_root_login: false,
  })
  interface NotificationEmailConfig {
    enabled: boolean
    smtp_host: string
    smtp_port: number
    smtp_user: string
    smtp_password: string
    from_address: string
    to_addresses: string[]
    use_tls: boolean
  }

  interface NotificationWebhookConfig {
    enabled: boolean
    url: string
    secret: string
  }

  interface NotificationEvents {
    container_create: boolean
    container_start: boolean
    container_stop: boolean
    container_crash: boolean
    container_delete: boolean
    vm_create: boolean
    vm_start: boolean
    vm_stop: boolean
    vm_delete: boolean
    backup_started: boolean
    backup_success: boolean
    backup_failure: boolean
    replication_started: boolean
    replication_success: boolean
    replication_failure: boolean
    system_alert: boolean
  }

  interface NotificationConfig {
    email: NotificationEmailConfig
    webhook: NotificationWebhookConfig
    events: NotificationEvents
  }

  const defaultNotifications: NotificationConfig = {
    email: {
      enabled: false,
      smtp_host: "",
      smtp_port: 587,
      smtp_user: "",
      smtp_password: "",
      from_address: "",
      to_addresses: [],
      use_tls: true,
    },
    webhook: { enabled: false, url: "", secret: "" },
    events: {
      container_create: true,
      container_start: true,
      container_stop: true,
      container_crash: true,
      container_delete: true,
      vm_create: true,
      vm_start: true,
      vm_stop: true,
      vm_delete: true,
      backup_started: true,
      backup_success: true,
      backup_failure: true,
      replication_started: true,
      replication_success: true,
      replication_failure: true,
      system_alert: true,
    },
  }

  const [notifications, setNotifications] = useState<NotificationConfig>(defaultNotifications)
  const [notifToInput, setNotifToInput] = useState("")
  const [success, setSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isUpdating, setIsUpdating] = useState(false)
  const [showUpdateModal, setShowUpdateModal] = useState(false)
  const [updateOutput, setUpdateOutput] = useState<string>("")
  const [updateStatus, setUpdateStatus] = useState<"running" | "success" | "error">("running")
  const [generatedApiToken, setGeneratedApiToken] = useState("")
  const [apiTokens, setApiTokens] = useState<ApiTokenMetadata[]>([])
  const [apiTokenName, setApiTokenName] = useState("Dashboard token")
  const [apiTokenRole, setApiTokenRole] = useState<ApiTokenMetadata["role"]>("admin")
  const [apiTokenScopes, setApiTokenScopes] = useState("*")
  const [apiTokenExpiryDays, setApiTokenExpiryDays] = useState("")

  // Customization
  const [customBannerTitle, setCustomBannerTitle] = useState("Welcome to Upcode Harbor")
  const [customBannerSubtitle, setCustomBannerSubtitle] = useState("Professional Server Management Platform")
  const [hasCustomLogo, setHasCustomLogo] = useState(false)
  const [hasCustomBanner, setHasCustomBanner] = useState(false)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [bannerPreview, setBannerPreview] = useState<string | null>(null)
  const logoInputRef = useRef<HTMLInputElement>(null)
  const bannerInputRef = useRef<HTMLInputElement>(null)

  const loadSettings = async () => {
    try {
      const res = await fetch(apiUrl("/settings"))
      if (res.ok) {
        const data = await res.json()
        setSettings({
          hostname: data.hostname,
          timezone: data.timezone,
          auto_updates: data.auto_updates,
          monitoring: data.monitoring,
          ssh_port: data.ssh_port,
          deny_root_login: data.deny_root_login ?? false,
        })
      }
    } catch (e) {
      console.error(e)
    }
  }

  const loadNotifications = async () => {
    try {
      const res = await fetch(apiUrl("/settings/notifications"))
      if (res.ok) {
        const data = await res.json()
        setNotifications({ ...defaultNotifications, ...data, email: { ...defaultNotifications.email, ...data.email }, webhook: { ...defaultNotifications.webhook, ...data.webhook }, events: { ...defaultNotifications.events, ...data.events } })
      }
    } catch (e) {
      console.error(e)
    }
  }

  const loadApiTokens = async () => {
    try {
      const res = await fetch(apiUrl("/settings/api-tokens"))
      if (res.ok) {
        const data = await res.json()
        setApiTokens(Array.isArray(data.tokens) ? data.tokens : [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const saveNotifications = async () => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl("/settings/notifications"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(notifications),
      })
      if (res.ok) {
        setSuccess("Notification settings saved successfully")
      } else {
        setError("Failed to save notification settings")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save notification settings")
    }
  }

  const testEmail = async () => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl("/settings/notifications/test/email"), { method: "POST" })
      if (res.ok) {
        setSuccess("Test email sent successfully")
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to send test email")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send test email")
    }
  }

  const testWebhook = async () => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl("/settings/notifications/test/webhook"), { method: "POST" })
      if (res.ok) {
        setSuccess("Test webhook sent successfully")
      } else {
        const data = await res.json()
        setError(data.detail || "Failed to send test webhook")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send test webhook")
    }
  }

  const loadCustomization = async () => {
    try {
      const res = await fetch(apiUrl("/settings/customization"))
      if (res.ok) {
        const data = await res.json()
        setCustomBannerTitle(data.banner_title)
        setCustomBannerSubtitle(data.banner_subtitle)
        setHasCustomLogo(data.has_logo)
        setHasCustomBanner(data.has_banner)
        setLogoPreview(data.has_logo ? apiUrl("/settings/customization/logo/file") : null)
        setBannerPreview(data.has_banner ? apiUrl("/settings/customization/banner/file") : null)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const saveCustomization = async () => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl("/settings/customization"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          banner_title: customBannerTitle,
          banner_subtitle: customBannerSubtitle,
        }),
      })
      if (res.ok) {
        setSuccess("Customization saved successfully")
      } else {
        setError("Failed to save customization")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save customization")
    }
  }

  const uploadLogo = async (file: File) => {
    try {
      setError(null)
      setSuccess(null)
      const fd = new FormData()
      fd.append("file", file)
      const res = await fetch(apiUrl("/settings/customization/logo"), { method: "POST", body: fd })
      if (res.ok) {
        setSuccess("Logo uploaded successfully")
        const url = apiUrl("/settings/customization/logo/file") + "?t=" + Date.now()
        setLogoPreview(url)
        setHasCustomLogo(true)
      } else {
        const d = await res.json()
        setError(d.detail || "Failed to upload logo")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to upload logo")
    }
  }

  const deleteLogo = async () => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl("/settings/customization/logo"), { method: "DELETE" })
      if (res.ok) {
        setSuccess("Custom logo removed")
        setLogoPreview(null)
        setHasCustomLogo(false)
      } else {
        setError("Failed to remove logo")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove logo")
    }
  }

  const uploadBanner = async (file: File) => {
    try {
      setError(null)
      setSuccess(null)
      const fd = new FormData()
      fd.append("file", file)
      const res = await fetch(apiUrl("/settings/customization/banner"), { method: "POST", body: fd })
      if (res.ok) {
        setSuccess("Banner image uploaded successfully")
        const url = apiUrl("/settings/customization/banner/file") + "?t=" + Date.now()
        setBannerPreview(url)
        setHasCustomBanner(true)
      } else {
        const d = await res.json()
        setError(d.detail || "Failed to upload banner")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to upload banner")
    }
  }

  const deleteBanner = async () => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl("/settings/customization/banner"), { method: "DELETE" })
      if (res.ok) {
        setSuccess("Custom banner removed")
        setBannerPreview(null)
        setHasCustomBanner(false)
      } else {
        setError("Failed to remove banner")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove banner")
    }
  }

  useEffect(() => {
    loadSettings()
    loadNotifications()
    loadApiTokens()
    loadCustomization()
  }, [])

  const saveSettings = async () => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl("/settings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      })
      if (res.ok) {
        setSuccess("Settings saved successfully")
      } else {
        setError("Failed to save settings")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save settings")
    }
  }

  const generateApiToken = async () => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl("/settings/api-tokens"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: apiTokenName.trim(),
          role: apiTokenRole,
          scopes: apiTokenScopes.split(",").map((scope) => scope.trim()).filter(Boolean),
          expires_in: apiTokenExpiryDays
            ? Math.round(Number(apiTokenExpiryDays) * 86_400)
            : null,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setGeneratedApiToken(data.token)
        await loadApiTokens()
        setSuccess("API token generated. Copy it now; it will not be shown again.")
      } else {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || "Failed to generate API token")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate API token")
    }
  }

  const revokeApiToken = async (tokenId: string) => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl(`/settings/api-tokens/${encodeURIComponent(tokenId)}`), {
        method: "DELETE",
      })
      if (!res.ok) {
        setError("Failed to revoke API token")
        return
      }
      await loadApiTokens()
      setSuccess("API token revoked")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to revoke API token")
    }
  }

  const handleUpdate = async () => {
    try {
      setError(null)
      setSuccess(null)
      setIsUpdating(true)
      setShowUpdateModal(true)
      setUpdateOutput("Starting update...\n")
      setUpdateStatus("running")
      
      const res = await fetch(apiUrl("/settings/update"), { method: "POST" })
      if (res.ok) {
        const queued = await res.json()
        const completed = await waitForJob<{
          exit_code: number
          stdout: string
          stderr: string
        }>(queued.persistent_job.id, (job) => {
          setUpdateOutput(`${job.message || "Update in progress"} (${job.progress}%)`)
        })
        const data = completed.result || { exit_code: 1, stdout: "", stderr: "No update result" }
        setUpdateOutput(data.stdout || data.stderr || "Update completed")
        
        if (data.exit_code === 0) {
          setSuccess("System update completed successfully")
          setUpdateStatus("success")
        } else {
          setError(`Update failed with exit code ${data.exit_code}`)
          setUpdateStatus("error")
        }
      } else {
        const errorText = await res.text()
        setUpdateOutput(errorText)
        setError("Failed to run update")
        setUpdateStatus("error")
      }
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : "Failed to run update"
      setUpdateOutput(errorMsg)
      setError(errorMsg)
      setUpdateStatus("error")
    } finally {
      setIsUpdating(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
        <p className="text-muted-foreground">Configure your server management system</p>
      </div>

      <NotificationContainer
        success={success}
        error={error}
        onClearSuccess={() => setSuccess(null)}
        onClearError={() => setError(null)}
      />

      <Dialog open={showUpdateModal} onOpenChange={setShowUpdateModal}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <RefreshCw className={`h-5 w-5 ${updateStatus === "running" ? "animate-spin" : ""}`} />
              System Update
            </DialogTitle>
            <DialogDescription>
              {updateStatus === "running" && "Update in progress..."}
              {updateStatus === "success" && "Update completed successfully"}
              {updateStatus === "error" && "Update failed"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="bg-muted rounded-md p-4 max-h-96 overflow-y-auto">
              <pre className="text-xs whitespace-pre-wrap font-mono">{updateOutput}</pre>
            </div>
            {updateStatus !== "running" && (
              <div className="flex justify-end">
                <Button onClick={() => setShowUpdateModal(false)}>Close</Button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Tabs defaultValue="system" className="space-y-6">
        <TabsList className={`grid w-full ${permissions.admin ? "grid-cols-3" : "grid-cols-2"}`}>
          <TabsTrigger value="system">System</TabsTrigger>
          <TabsTrigger value="notifications">
            <Bell className="h-4 w-4 mr-2" />
            Notifications
          </TabsTrigger>
          {permissions.admin && (
            <TabsTrigger value="customization">
              <Paintbrush className="h-4 w-4 mr-2" />
              Customization
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="system" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>System Settings</CardTitle>
              <CardDescription>Basic system configuration</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="hostname">Hostname</Label>
                  <Input
                    id="hostname"
                    value={settings.hostname}
                    onChange={(e) => setSettings({ ...settings, hostname: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="timezone">Timezone</Label>
                  <Select
                    value={settings.timezone}
                    onValueChange={(v) => setSettings({ ...settings, timezone: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="europe/berlin">Europe/Berlin</SelectItem>
                      <SelectItem value="utc">UTC</SelectItem>
                      <SelectItem value="america/new_york">America/New_York</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="ssh-port">SSH Port</Label>
                  <Input
                    id="ssh-port"
                    type="number"
                    value={settings.ssh_port}
                    onChange={(e) =>
                      setSettings({ ...settings, ssh_port: parseInt(e.target.value || "0") })
                    }
                  />
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="auto-updates"
                  checked={settings.auto_updates}
                  onCheckedChange={(v) => setSettings({ ...settings, auto_updates: v })}
                />
                <Label htmlFor="auto-updates">Enable automatic updates</Label>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="monitoring"
                  checked={settings.monitoring}
                  onCheckedChange={(v) => setSettings({ ...settings, monitoring: v })}
                />
                <Label htmlFor="monitoring">Enable system monitoring</Label>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="deny-root-login"
                  checked={settings.deny_root_login}
                  onCheckedChange={(v) => setSettings({ ...settings, deny_root_login: v })}
                />
                <Label htmlFor="deny-root-login">Deny root login</Label>
              </div>
              <div className="space-y-2 pt-4">
                <Label>API Tokens</Label>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <Label htmlFor="api-token-name">Name</Label>
                    <Input
                      id="api-token-name"
                      value={apiTokenName}
                      onChange={(event) => setApiTokenName(event.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="api-token-role">Role</Label>
                    <Select
                      value={apiTokenRole}
                      onValueChange={(value) => setApiTokenRole(value as ApiTokenMetadata["role"])}
                    >
                      <SelectTrigger id="api-token-role"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="admin">Administrator</SelectItem>
                        <SelectItem value="operator">Operator</SelectItem>
                        <SelectItem value="read-only">Read only</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="api-token-scopes">Scopes</Label>
                    <Input
                      id="api-token-scopes"
                      value={apiTokenScopes}
                      onChange={(event) => setApiTokenScopes(event.target.value)}
                      placeholder="containers:read, containers:write"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="api-token-expiry">Expiry in days</Label>
                    <Input
                      id="api-token-expiry"
                      type="number"
                      min="1"
                      max="365"
                      value={apiTokenExpiryDays}
                      onChange={(event) => setApiTokenExpiryDays(event.target.value)}
                      placeholder="No expiry"
                    />
                  </div>
                </div>
                <div className="flex space-x-2">
                  <Input
                    id="api-token"
                    value={generatedApiToken}
                    placeholder="Tokens are shown only once after creation"
                    readOnly
                  />
                  <Button onClick={generateApiToken}>
                    <Key className="h-4 w-4 mr-2" />
                    Generate token
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Separate scopes with commas. Use * only when the token genuinely needs unrestricted access.
                </p>
                <div className="space-y-2 pt-2">
                  {apiTokens.map((token) => (
                    <div key={token.id} className="flex items-center justify-between rounded-md border p-3 text-sm">
                      <div>
                        <p className="font-medium">{token.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {token.role} · {token.scopes.join(", ")}
                          {token.expires_at ? ` · expires ${new Date(token.expires_at * 1000).toLocaleString()}` : ""}
                          {token.revoked_at ? " · revoked" : ""}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={Boolean(token.revoked_at)}
                        onClick={() => revokeApiToken(token.id)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Revoke
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>System Update</CardTitle>
              <CardDescription>Update Upcode Harbor to the latest version</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                This will run the update.sh script to update Upcode Harbor to the latest version from the repository.
              </p>
              <Button onClick={handleUpdate} disabled={isUpdating}>
                <RefreshCw className={`h-4 w-4 mr-2 ${isUpdating ? 'animate-spin' : ''}`} />
                {isUpdating ? "Updating..." : "Run Update"}
              </Button>
            </CardContent>
          </Card>

          <div className="flex justify-end space-x-2">
            <Button variant="outline" onClick={loadSettings}>
              Reset
            </Button>
            <Button onClick={saveSettings}>
              <Save className="h-4 w-4 mr-2" />
              Save Settings
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="notifications" className="space-y-6">
          {/* Email */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5" />
                Email Notifications
              </CardTitle>
              <CardDescription>Send alerts via SMTP email</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-2">
                <Switch
                  id="email-enabled"
                  checked={notifications.email.enabled}
                  onCheckedChange={(v) =>
                    setNotifications({ ...notifications, email: { ...notifications.email, enabled: v } })
                  }
                />
                <Label htmlFor="email-enabled">Enable email notifications</Label>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div className="space-y-2 col-span-2">
                  <Label>SMTP Host</Label>
                  <Input
                    placeholder="smtp.example.com"
                    value={notifications.email.smtp_host}
                    onChange={(e) =>
                      setNotifications({ ...notifications, email: { ...notifications.email, smtp_host: e.target.value } })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>SMTP Port</Label>
                  <Input
                    type="number"
                    placeholder="587"
                    value={notifications.email.smtp_port}
                    onChange={(e) =>
                      setNotifications({ ...notifications, email: { ...notifications.email, smtp_port: parseInt(e.target.value || "587") } })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Username</Label>
                  <Input
                    placeholder="user@example.com"
                    value={notifications.email.smtp_user}
                    onChange={(e) =>
                      setNotifications({ ...notifications, email: { ...notifications.email, smtp_user: e.target.value } })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Password</Label>
                  <Input
                    type="password"
                    placeholder="••••••••"
                    value={notifications.email.smtp_password}
                    onChange={(e) =>
                      setNotifications({ ...notifications, email: { ...notifications.email, smtp_password: e.target.value } })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>From Address</Label>
                  <Input
                    placeholder="upservx@example.com"
                    value={notifications.email.from_address}
                    onChange={(e) =>
                      setNotifications({ ...notifications, email: { ...notifications.email, from_address: e.target.value } })
                    }
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Recipients</Label>
                <div className="flex gap-2">
                  <Input
                    placeholder="admin@example.com"
                    value={notifToInput}
                    onChange={(e) => setNotifToInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && notifToInput.trim()) {
                        setNotifications({ ...notifications, email: { ...notifications.email, to_addresses: [...notifications.email.to_addresses, notifToInput.trim()] } })
                        setNotifToInput("")
                      }
                    }}
                  />
                  <Button
                    variant="outline"
                    onClick={() => {
                      if (notifToInput.trim()) {
                        setNotifications({ ...notifications, email: { ...notifications.email, to_addresses: [...notifications.email.to_addresses, notifToInput.trim()] } })
                        setNotifToInput("")
                      }
                    }}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {notifications.email.to_addresses.map((addr, i) => (
                    <span key={i} className="flex items-center gap-1 bg-muted text-sm rounded px-2 py-1">
                      {addr}
                      <button
                        onClick={() =>
                          setNotifications({ ...notifications, email: { ...notifications.email, to_addresses: notifications.email.to_addresses.filter((_, j) => j !== i) } })
                        }
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <Switch
                  id="use-tls"
                  checked={notifications.email.use_tls}
                  onCheckedChange={(v) =>
                    setNotifications({ ...notifications, email: { ...notifications.email, use_tls: v } })
                  }
                />
                <Label htmlFor="use-tls">Use STARTTLS</Label>
              </div>

              <Button variant="outline" onClick={testEmail} disabled={!notifications.email.enabled}>
                <Send className="h-4 w-4 mr-2" />
                Send Test Email
              </Button>
            </CardContent>
          </Card>

          {/* Webhook */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Webhook className="h-5 w-5" />
                Webhook Notifications
              </CardTitle>
              <CardDescription>POST a JSON payload to a URL (Slack, Discord, custom endpoint)</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-2">
                <Switch
                  id="webhook-enabled"
                  checked={notifications.webhook.enabled}
                  onCheckedChange={(v) =>
                    setNotifications({ ...notifications, webhook: { ...notifications.webhook, enabled: v } })
                  }
                />
                <Label htmlFor="webhook-enabled">Enable webhook notifications</Label>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Webhook URL</Label>
                  <Input
                    placeholder="https://hooks.slack.com/services/..."
                    value={notifications.webhook.url}
                    onChange={(e) =>
                      setNotifications({ ...notifications, webhook: { ...notifications.webhook, url: e.target.value } })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Secret Header (optional)</Label>
                  <Input
                    placeholder="my-secret-token"
                    value={notifications.webhook.secret}
                    onChange={(e) =>
                      setNotifications({ ...notifications, webhook: { ...notifications.webhook, secret: e.target.value } })
                    }
                  />
                </div>
              </div>

              <Button variant="outline" onClick={testWebhook} disabled={!notifications.webhook.enabled}>
                <Send className="h-4 w-4 mr-2" />
                Send Test Webhook
              </Button>
            </CardContent>
          </Card>

          {/* Events */}
          <Card>
            <CardHeader>
              <CardTitle>Notification Events</CardTitle>
              <CardDescription>Choose which events trigger a notification</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {([
                  ["container_create", "Container created"],
                  ["container_start",  "Container started"],
                  ["container_stop",   "Container stopped"],
                  ["container_crash",  "Container crashed"],
                  ["container_delete", "Container deleted"],
                  ["vm_create",        "VM created"],
                  ["vm_start",         "VM started"],
                  ["vm_stop",          "VM stopped"],
                  ["vm_delete",        "VM deleted"],
                  ["backup_started",   "Backup started"],
                  ["backup_success",   "Backup completed"],
                  ["backup_failure",   "Backup failed"],
                  ["replication_started", "Replication started"],
                  ["replication_success", "Replication completed"],
                  ["replication_failure", "Replication failed"],
                  ["system_alert",     "System alert"],
                ] as [keyof typeof notifications.events, string][]).map(([key, label]) => (
                  <div key={key} className="flex items-center space-x-2">
                    <Switch
                      id={`event-${key}`}
                      checked={notifications.events[key]}
                      onCheckedChange={(v) =>
                        setNotifications({ ...notifications, events: { ...notifications.events, [key]: v } })
                      }
                    />
                    <Label htmlFor={`event-${key}`}>{label}</Label>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button onClick={saveNotifications}>
              <Save className="h-4 w-4 mr-2" />
              Save Notification Settings
            </Button>
          </div>
        </TabsContent>

        {permissions.admin && (
          <TabsContent value="customization" className="space-y-6">
            {/* Login Banner Text */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Paintbrush className="h-5 w-5" />
                  Login Screen Text
                </CardTitle>
                <CardDescription>
                  Customize the title and subtitle displayed on the login page
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="banner-title">Banner Title</Label>
                  <Input
                    id="banner-title"
                    value={customBannerTitle}
                    onChange={(e) => setCustomBannerTitle(e.target.value)}
                    placeholder="Welcome to Upcode Harbor"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="banner-subtitle">Banner Subtitle</Label>
                  <Input
                    id="banner-subtitle"
                    value={customBannerSubtitle}
                    onChange={(e) => setCustomBannerSubtitle(e.target.value)}
                    placeholder="Professional Server Management Platform"
                  />
                </div>
                <div className="flex justify-end">
                  <Button onClick={saveCustomization}>
                    <Save className="h-4 w-4 mr-2" />
                    Save Text
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Logo */}
            <Card>
              <CardHeader>
                <CardTitle>Logo</CardTitle>
                <CardDescription>
                  Upload a custom logo shown in the login screen. PNG, JPG, SVG or WebP recommended.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {logoPreview && (
                  <div className="flex items-center gap-4">
                    <img
                      src={logoPreview}
                      alt="Current logo"
                      className="h-20 w-auto object-contain border rounded p-2 bg-muted"
                    />
                    <span className="text-sm text-muted-foreground">Current logo</span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <input
                    ref={logoInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) uploadLogo(file)
                      e.target.value = ""
                    }}
                  />
                  <Button variant="outline" onClick={() => logoInputRef.current?.click()}>
                    <Upload className="h-4 w-4 mr-2" />
                    {hasCustomLogo ? "Replace Logo" : "Upload Logo"}
                  </Button>
                  {hasCustomLogo && (
                    <Button variant="outline" className="text-destructive border-destructive/30 hover:bg-destructive/10" onClick={deleteLogo}>
                      <Trash2 className="h-4 w-4 mr-2" />
                      Remove
                    </Button>
                  )}
                </div>
                {!hasCustomLogo && (
                  <p className="text-sm text-muted-foreground">Using default logo (/public/logo.png)</p>
                )}
              </CardContent>
            </Card>

            {/* Banner Image */}
            <Card>
              <CardHeader>
                <CardTitle>Login Banner Image</CardTitle>
                <CardDescription>
                  Upload a custom background image for the left side of the login page.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {bannerPreview && (
                  <div className="relative w-full max-w-sm h-40 overflow-hidden rounded border">
                    <img
                      src={bannerPreview}
                      alt="Current banner"
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute inset-0 bg-black/30 flex items-center justify-center">
                      <span className="text-white text-xs">Current banner</span>
                    </div>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <input
                    ref={bannerInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) uploadBanner(file)
                      e.target.value = ""
                    }}
                  />
                  <Button variant="outline" onClick={() => bannerInputRef.current?.click()}>
                    <Upload className="h-4 w-4 mr-2" />
                    {hasCustomBanner ? "Replace Banner" : "Upload Banner"}
                  </Button>
                  {hasCustomBanner && (
                    <Button variant="outline" className="text-destructive border-destructive/30 hover:bg-destructive/10" onClick={deleteBanner}>
                      <Trash2 className="h-4 w-4 mr-2" />
                      Remove
                    </Button>
                  )}
                </div>
                {!hasCustomBanner && (
                  <p className="text-sm text-muted-foreground">Using default banner (/public/login.jpg)</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
