import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export function Settings() {
  interface SettingsData {
    hostname: string
    timezone: string
    auto_updates: boolean
    monitoring: boolean
    ssh_port: number
  }

  const [settings, setSettings] = useState<SettingsData>({
    hostname: "",
    timezone: "utc",
    auto_updates: false,
    monitoring: false,
    ssh_port: 22,
  })
  const [message, setMessage] = useState<string | null>(null)

  const loadSettings = async () => {
    try {
      const res = await fetch("http://localhost:8000/settings")
      if (res.ok) {
        const data = await res.json()
        setSettings({
          hostname: data.hostname,
          timezone: data.timezone,
          auto_updates: data.auto_updates,
          monitoring: data.monitoring,
          ssh_port: data.ssh_port,
        })
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  useEffect(() => {
    if (!message) return
    const t = setTimeout(() => setMessage(null), 3000)
    return () => clearTimeout(t)
  }, [message])

  const handleSave = async () => {
    try {
      const res = await fetch("http://localhost:8000/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      })
      if (res.ok) setMessage("Gespeichert")
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div className="space-y-6">
      {message && (
        <div className="fixed top-4 right-4 z-50 bg-green-600 text-white px-3 py-2 rounded shadow">
          {message}
        </div>
      )}
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Einstellungen</h2>
        <p className="text-muted-foreground">Konfigurieren Sie Ihr Server Management System</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>System Einstellungen</CardTitle>
          <CardDescription>Grundlegende Konfiguration des Systems</CardDescription>
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
              <Label htmlFor="timezone">Zeitzone</Label>
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
            <Label htmlFor="auto-updates">Automatische Updates aktivieren</Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="monitoring"
              checked={settings.monitoring}
              onCheckedChange={(v) => setSettings({ ...settings, monitoring: v })}
            />
            <Label htmlFor="monitoring">System Monitoring aktivieren</Label>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end space-x-2">
        <Button variant="outline" onClick={loadSettings}>
          Zurücksetzen
        </Button>
        <Button onClick={handleSave}>Einstellungen speichern</Button>
      </div>
    </div>
  )
}
