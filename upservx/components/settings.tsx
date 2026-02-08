"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { NotificationContainer } from "@/components/ui/notification"
import { Save, Key, Play, Square, Download, RefreshCw } from "lucide-react"
import { apiUrl } from "@/lib/api"
import ReverseProxyManagement from "./reverse-proxy-management"

export function Settings() {
  interface SettingsData {
    hostname: string
    timezone: string
    auto_updates: boolean
    monitoring: boolean
    ssh_port: number
    api_key?: string
  }

  const [settings, setSettings] = useState<SettingsData>({
    hostname: "",
    timezone: "utc",
    auto_updates: false,
    monitoring: false,
    ssh_port: 22,
    api_key: "",
  })
  const [success, setSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [vpnStatus, setVpnStatus] = useState<{ running: boolean; pid?: number | null; ovpn_path?: string | null } | null>(null)
  const [isUpdating, setIsUpdating] = useState(false)
  const [showUpdateModal, setShowUpdateModal] = useState(false)
  const [updateOutput, setUpdateOutput] = useState<string>("")
  const [updateStatus, setUpdateStatus] = useState<"running" | "success" | "error">("running")

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
          api_key: data.api_key || "",
        })
      }
    } catch (e) {
      console.error(e)
    }
  }

  const loadVpnStatus = async () => {
    try {
      const res = await fetch(apiUrl("/settings/vpn/status"))
      if (res.ok) {
        const data = await res.json()
        setVpnStatus(data)
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    loadSettings()
    loadVpnStatus()
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

  const generateApiKey = async () => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl("/settings/generate-api-key"), { method: "POST" })
      if (res.ok) {
        const data = await res.json()
        setSettings({ ...settings, api_key: data.api_key })
        setSuccess("API key generated successfully")
      } else {
        setError("Failed to generate API key")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate API key")
    }
  }

  const handleUploadVpn = async (file: File | null) => {
    if (!file) return
    try {
      setError(null)
      setSuccess(null)
      const fd = new FormData()
      fd.append("file", file)
      const res = await fetch(apiUrl("/settings/vpn/upload"), {
        method: "POST",
        body: fd,
      })
      if (res.ok) {
        setSuccess("VPN configuration uploaded successfully")
        await loadVpnStatus()
      } else {
        const txt = await res.text()
        setError("Upload failed: " + txt)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to upload VPN configuration")
    }
  }

  const handleStartVpn = async () => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl("/settings/vpn/start"), { method: "POST" })
      if (res.ok) {
        setSuccess("VPN started successfully")
        await loadVpnStatus()
      } else {
        setError("Failed to start VPN")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start VPN")
    }
  }

  const handleStopVpn = async () => {
    try {
      setError(null)
      setSuccess(null)
      const res = await fetch(apiUrl("/settings/vpn/stop"), { method: "POST" })
      if (res.ok) {
        setSuccess("VPN stopped successfully")
        await loadVpnStatus()
      } else {
        setError("Failed to stop VPN")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to stop VPN")
    }
  }

  const handleDownloadVpn = () => {
    window.location.href = apiUrl("/settings/vpn/file")
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
        const data = await res.json()
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
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="system">System</TabsTrigger>
          <TabsTrigger value="vpn">VPN</TabsTrigger>
          <TabsTrigger value="proxy">Reverse Proxy & SSL</TabsTrigger>
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
              <div className="space-y-2 pt-4">
                <Label htmlFor="api-key">API Key</Label>
                <div className="flex space-x-2">
                  <Input id="api-key" value={settings.api_key} readOnly />
                  <Button onClick={generateApiKey}>
                    <Key className="h-4 w-4 mr-2" />
                    Generate
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>System Update</CardTitle>
              <CardDescription>Update UpservX to the latest version</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                This will run the update.sh script to update UpservX to the latest version from the repository.
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

        <TabsContent value="vpn" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>OpenVPN</CardTitle>
              <CardDescription>Upload and control an OpenVPN client profile</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>OVPN File</Label>
                <div className="flex items-center space-x-2">
                  <input
                    id="ovpn-file"
                    type="file"
                    accept=".ovpn"
                    onChange={(e) => handleUploadVpn(e.target.files ? e.target.files[0] : null)}
                    className="rounded"
                  />
                  <Button 
                    variant="outline" 
                    onClick={handleDownloadVpn} 
                    disabled={!vpnStatus || !vpnStatus.ovpn_path}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Download
                  </Button>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <div>Status: {vpnStatus ? (vpnStatus.running ? "Running" : "Stopped") : "Unknown"}</div>
                {vpnStatus && vpnStatus.ovpn_path && <div className="text-muted-foreground">{vpnStatus.ovpn_path.split('/').pop()}</div>}
              </div>

              <div className="flex space-x-2">
                <Button onClick={handleStartVpn} disabled={vpnStatus?.running}>
                  <Play className="h-4 w-4 mr-2" />
                  Start VPN
                </Button>
                <Button variant="destructive" onClick={handleStopVpn} disabled={!vpnStatus?.running}>
                  <Square className="h-4 w-4 mr-2" />
                  Stop VPN
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="proxy" className="space-y-6">
          <ReverseProxyManagement />
        </TabsContent>
      </Tabs>
    </div>
  )
}
