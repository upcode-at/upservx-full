"use client"

import { useState, useEffect } from "react"

interface Drive {
  device: string
  name: string
  type: string
  size: number
  used: number
  available: number
  filesystem: string
  mountpoint: string
  mounted: boolean
  health: string
  temperature?: number | null
}
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { HardDrive, Usb, MemoryStickIcon as SdCard, Settings, AlertTriangle } from "lucide-react"

export function StorageManagement() {
  const [drives, setDrives] = useState<Drive[]>([])
  const loadDrives = async () => {
    try {
      const res = await fetch("http://localhost:8000/drives")
      if (res.ok) {
        const data = await res.json()
        setDrives(data.drives || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    loadDrives()
  }, [])

  const [activeDrive, setActiveDrive] = useState<Drive | null>(null)
  const [formatFs, setFormatFs] = useState("")
  const [formatLabel, setFormatLabel] = useState("")
  const [mountPath, setMountPath] = useState("")

  const handleFormat = async () => {
    if (!activeDrive) return
    try {
      await fetch("http://localhost:8000/drives/format", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device: activeDrive.device,
          filesystem: formatFs,
          label: formatLabel || null,
        }),
      })
      await loadDrives()
    } catch (e) {
      console.error(e)
    }
    setActiveDrive(null)
    setFormatFs("")
    setFormatLabel("")
  }

  const handleMount = async () => {
    if (!activeDrive) return
    try {
      await fetch("http://localhost:8000/drives/mount", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device: activeDrive.device, mountpoint: mountPath }),
      })
      await loadDrives()
    } catch (e) {
      console.error(e)
    }
    setActiveDrive(null)
    setMountPath("")
  }

  const [mountedVolumes] = useState([
    {
      vm: "Ubuntu-Server-01",
      device: "/dev/vda1",
      size: 50,
      used: 18,
      mountpoint: "/",
      filesystem: "ext4",
    },
    {
      vm: "Windows-Dev",
      device: "/dev/vda1",
      size: 100,
      used: 45,
      mountpoint: "C:",
      filesystem: "ntfs",
    },
    {
      container: "mysql-db",
      device: "volume-mysql",
      size: 20,
      used: 8,
      mountpoint: "/var/lib/mysql",
      filesystem: "ext4",
    },
  ])

  const getDriveIcon = (type: string) => {
    switch (type) {
      case "USB":
        return <Usb className="h-5 w-5" />
      case "SD":
        return <SdCard className="h-5 w-5" />
      default:
        return <HardDrive className="h-5 w-5" />
    }
  }

  const getHealthColor = (health: string) => {
    switch (health) {
      case "good":
        return "default"
      case "warning":
        return "outline"
      case "critical":
        return "destructive"
      default:
        return "secondary"
    }
  }

  const getUsagePercentage = (used: number, size: number) => {
    return Math.round((used / size) * 100)
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Speicher Management</h2>
        <p className="text-muted-foreground">Festplatten, Volumes und Speichernutzung verwalten</p>
      </div>

      {/* Physical Drives */}
      <Card>
        <CardHeader>
          <CardTitle>Physische Laufwerke</CardTitle>
          <CardDescription>Alle eingehängten Festplatten und Speichergeräte</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {drives.map((drive) => (
              <div key={drive.device} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    {getDriveIcon(drive.type)}
                    <div>
                      <div className="font-medium">{drive.name}</div>
                      <div className="text-sm text-muted-foreground">{drive.device}</div>
                    </div>
                    <Badge variant="outline">{drive.type}</Badge>
                    <Badge variant={getHealthColor(drive.health)}>
                      {drive.health === "good" ? "Gut" : drive.health === "warning" ? "Warnung" : "Kritisch"}
                    </Badge>
                    {!drive.mounted && <Badge variant="destructive">Nicht eingehängt</Badge>}
                  </div>
                  <div className="flex items-center gap-2">
                    {!drive.mounted && (
                      <Dialog onOpenChange={(o) => !o && setActiveDrive(null)}>
                        <DialogTrigger asChild>
                          <Button variant="outline" size="sm" onClick={() => { setActiveDrive(drive); setMountPath(`/mnt/${drive.name}`) }}>
                            Einhängen
                          </Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Festplatte einhängen</DialogTitle>
                          </DialogHeader>
                          <div className="space-y-4">
                            <div className="space-y-2">
                              <Label htmlFor="mp">Mountpoint</Label>
                              <Input id="mp" value={mountPath} onChange={(e) => setMountPath(e.target.value)} />
                            </div>
                            <div className="flex justify-end space-x-2">
                              <Button variant="outline" onClick={() => setActiveDrive(null)}>Abbrechen</Button>
                              <Button onClick={handleMount}>Einhängen</Button>
                            </div>
                          </div>
                        </DialogContent>
                      </Dialog>
                    )}
                    <Dialog onOpenChange={(o) => !o && setActiveDrive(null)}>
                      <DialogTrigger asChild>
                        <Button variant="outline" size="sm" onClick={() => setActiveDrive(drive)}>
                          <AlertTriangle className="h-4 w-4 mr-2" />
                          Formatieren
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Laufwerk formatieren</DialogTitle>
                          <DialogDescription>
                            Warnung: Alle Daten auf {drive.name} ({drive.device}) werden unwiderruflich gelöscht!
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4">
                          <div className="space-y-2">
                            <Label htmlFor="filesystem">Dateisystem</Label>
                            <Select value={formatFs} onValueChange={setFormatFs}>
                              <SelectTrigger>
                                <SelectValue placeholder="Dateisystem auswählen" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="ext4">ext4 (Linux)</SelectItem>
                                <SelectItem value="ntfs">NTFS (Windows)</SelectItem>
                                <SelectItem value="fat32">FAT32 (Universal)</SelectItem>
                                <SelectItem value="exfat">exFAT (Universal)</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="label">Volume Label</Label>
                            <Input id="label" value={formatLabel} onChange={(e) => setFormatLabel(e.target.value)} placeholder="z.B. Backup Drive" />
                          </div>
                          <div className="flex justify-end space-x-2">
                            <Button variant="outline" onClick={() => setActiveDrive(null)}>Abbrechen</Button>
                            <Button variant="destructive" onClick={handleFormat}>Formatieren</Button>
                          </div>
                        </div>
                      </DialogContent>
                    </Dialog>
                    <Button variant="outline" size="icon">
                      <Settings className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Größe:</span>
                    <div className="font-medium">{drive.size} GB</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Belegt:</span>
                    <div className="font-medium">{drive.used} GB</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Verfügbar:</span>
                    <div className="font-medium">{drive.available} GB</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Dateisystem:</span>
                    <div className="font-medium">{drive.filesystem}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Temperatur:</span>
                    <div className="font-medium">{drive.temperature}°C</div>
                  </div>
                </div>
                <div className="mt-4">
                  <div className="flex justify-between text-sm mb-2">
                    <span>Speichernutzung</span>
                    <span>{getUsagePercentage(drive.used, drive.size)}%</span>
                  </div>
                  <Progress value={getUsagePercentage(drive.used, drive.size)} className="h-2" />
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {drive.mounted ? (
                    <>Eingehängt unter: {drive.mountpoint}</>
                  ) : (
                    <>Nicht eingehängt</>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* VM/Container Volumes */}
      <Card>
        <CardHeader>
          <CardTitle>VM und Container Volumes</CardTitle>
          <CardDescription>Speichernutzung von virtuellen Maschinen und Containern</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>VM/Container</TableHead>
                <TableHead>Device</TableHead>
                <TableHead>Größe</TableHead>
                <TableHead>Belegt</TableHead>
                <TableHead>Verfügbar</TableHead>
                <TableHead>Auslastung</TableHead>
                <TableHead>Dateisystem</TableHead>
                <TableHead>Mountpoint</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mountedVolumes.map((volume, index) => (
                <TableRow key={index}>
                  <TableCell className="font-medium">{volume.vm || volume.container}</TableCell>
                  <TableCell className="font-mono text-xs">{volume.device}</TableCell>
                  <TableCell>{volume.size} GB</TableCell>
                  <TableCell>{volume.used} GB</TableCell>
                  <TableCell>{volume.size - volume.used} GB</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Progress value={getUsagePercentage(volume.used, volume.size)} className="h-2 w-16" />
                      <span className="text-sm">{getUsagePercentage(volume.used, volume.size)}%</span>
                    </div>
                  </TableCell>
                  <TableCell>{volume.filesystem}</TableCell>
                  <TableCell>{volume.mountpoint}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
