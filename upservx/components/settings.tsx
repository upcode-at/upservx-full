import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

export function Settings() {
  return (
    <div className="space-y-6">
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
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="hostname">Hostname</Label>
              <Input id="hostname" defaultValue="server-manager-01" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="timezone">Zeitzone</Label>
              <Select defaultValue="europe/berlin">
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
          </div>
          <div className="flex items-center space-x-2">
            <Switch id="auto-updates" />
            <Label htmlFor="auto-updates">Automatische Updates aktivieren</Label>
          </div>
          <div className="flex items-center space-x-2">
            <Switch id="monitoring" defaultChecked />
            <Label htmlFor="monitoring">System Monitoring aktivieren</Label>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end space-x-2">
        <Button variant="outline">Zurücksetzen</Button>
        <Button>Einstellungen speichern</Button>
      </div>
    </div>
  )
}
