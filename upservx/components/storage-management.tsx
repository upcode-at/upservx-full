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
import { HardDrive, Usb, MemoryStickIcon as SdCard, Settings, AlertTriangle } from "lucide-react"
import { apiUrl } from "@/lib/api"

export function StorageManagement() {
  const [drives, setDrives] = useState<Drive[]>([])
  const loadDrives = async () => {
    try {
      const res = await fetch(apiUrl("/drives"))
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
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [mountOpen, setMountOpen] = useState(false)
  const [formatOpen, setFormatOpen] = useState(false)

  useEffect(() => {
    if (!error) return
    const t = setTimeout(() => setError(null), 3000)
    return () => clearTimeout(t)
  }, [error])

  useEffect(() => {
    if (!message) return
    const t = setTimeout(() => setMessage(null), 3000)
    return () => clearTimeout(t)
  }, [message])

  const cancelFormat = () => {
    setActiveDrive(null)
    setFormatFs("")
    setFormatLabel("")
    setFormatOpen(false)
    setMessage("Formatting cancelled")
  }

  const cancelMount = () => {
    setActiveDrive(null)
    setMountPath("")
    setMountOpen(false)
    setMessage("Mount cancelled")
  }

  const handleFormat = async () => {
    if (!activeDrive) return
    try {
      const res = await fetch(apiUrl("/drives/format"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device: activeDrive.device,
          filesystem: formatFs,
          label: formatLabel || null,
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      setMessage("Formatting complete")
      await loadDrives()
    } catch (e) {
      console.error(e)
      setError("Formatting failed")
    } finally {
      setActiveDrive(null)
      setFormatFs("")
      setFormatLabel("")
      setFormatOpen(false)
    }
  }

  const handleMount = async () => {
    if (!activeDrive) return
    try {
      await fetch(apiUrl("/drives/mount"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device: activeDrive.device, mountpoint: mountPath }),
      })
      await loadDrives()
      setMessage("Drive mounted")
    } catch (e) {
      console.error(e)
      setError("Mount failed")
    }
    setActiveDrive(null)
    setMountPath("")
    setMountOpen(false)
  }


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
        <h2 className="text-3xl font-bold tracking-tight">Storage Management</h2>
        <p className="text-muted-foreground">Manage disks, volumes and usage</p>
      </div>

      {/* Physical Drives */}
      <Card>
        <CardHeader>
          <CardTitle>Physical Drives</CardTitle>
          <CardDescription>All mounted disks and storage devices</CardDescription>
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
                      {drive.health === "good" ? "Good" : drive.health === "warning" ? "Warning" : "Critical"}
                    </Badge>
                    {!drive.mounted && <Badge variant="destructive">Not mounted</Badge>}
                  </div>
                  <div className="flex items-center gap-2">
                    {!drive.mounted && (
                      <Dialog
                        open={mountOpen && activeDrive?.device === drive.device}
                        onOpenChange={(o) => {
                          setMountOpen(o)
                          if (!o) setActiveDrive(null)
                        }}
                      >
                        <DialogTrigger asChild>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setActiveDrive(drive)
                              setMountPath(`/mnt/${drive.name}`)
                              setMountOpen(true)
                            }}
                          >
                            Mount
                          </Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Mount Drive</DialogTitle>
                          </DialogHeader>
                          <div className="space-y-4">
                            <div className="space-y-2">
                              <Label htmlFor="mp">Mountpoint</Label>
                              <Input id="mp" value={mountPath} onChange={(e) => setMountPath(e.target.value)} />
                            </div>
                            <div className="flex justify-end space-x-2">
                              <Button variant="outline" onClick={cancelMount}>Cancel</Button>
                              <Button onClick={handleMount}>Mount</Button>
                            </div>
                          </div>
                        </DialogContent>
                      </Dialog>
                    )}
                    <Dialog
                      open={formatOpen && activeDrive?.device === drive.device}
                      onOpenChange={(o) => {
                        setFormatOpen(o)
                        if (!o) setActiveDrive(null)
                      }}
                    >
                      <DialogTrigger asChild>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setActiveDrive(drive)
                            setFormatFs("")
                            setFormatLabel("")
                            setFormatOpen(true)
                          }}
                        >
                          <AlertTriangle className="h-4 w-4 mr-2" />
                          Format
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Format Drive</DialogTitle>
                          <DialogDescription>
                            Warning: All data on {drive.name} ({drive.device}) will be permanently erased!
                          </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4">
                          <div className="space-y-2">
                            <Label htmlFor="filesystem">Filesystem</Label>
                            <Select value={formatFs} onValueChange={setFormatFs}>
                              <SelectTrigger>
                                <SelectValue placeholder="Select filesystem" />
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
                            <Button variant="outline" onClick={cancelFormat}>Cancel</Button>
                            <Button variant="destructive" onClick={handleFormat}>Format</Button>
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
                    <span className="text-muted-foreground">Size:</span>
                    <div className="font-medium">{drive.size} GB</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Used:</span>
                    <div className="font-medium">{drive.used} GB</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Available:</span>
                    <div className="font-medium">{drive.available} GB</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Filesystem:</span>
                    <div className="font-medium">{drive.filesystem}</div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Temperature:</span>
                    <div className="font-medium">{drive.temperature}°C</div>
                  </div>
                </div>
                <div className="mt-4">
                  <div className="flex justify-between text-sm mb-2">
                    <span>Storage usage</span>
                    <span>{getUsagePercentage(drive.used, drive.size)}%</span>
                  </div>
                  <Progress value={getUsagePercentage(drive.used, drive.size)} className="h-2" />
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {drive.mounted ? (
                    <>Mounted at: {drive.mountpoint}</>
                  ) : (
                    <>Not mounted</>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="fixed top-4 right-4 z-50 bg-red-600 text-white px-3 py-2 rounded shadow">
          {error}
        </div>
      )}
      {message && (
        <div className="fixed top-4 right-4 z-50 bg-green-600 text-white px-3 py-2 rounded shadow">
          {message}
        </div>
      )}
    </div>
  )
}
