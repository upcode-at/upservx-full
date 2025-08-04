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
  temperature?: number | null
}

interface ZFSPool {
  name: string
  type: string
  devices: string[]
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
  const [pools, setPools] = useState<ZFSPool[]>([])
  const loadDrives = async () => {
    try {
      const [dRes, pRes] = await Promise.all([
        fetch(apiUrl("/drives")),
        fetch(apiUrl("/drives/zfs")),
      ])
      if (dRes.ok) {
        const data = await dRes.json()
        setDrives(data.drives || [])
      }
      if (pRes.ok) {
        const pData = await pRes.json()
        setPools(pData.pools || [])
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
  const [poolOpen, setPoolOpen] = useState(false)
  const [poolName, setPoolName] = useState("")
  const [raidLevel, setRaidLevel] = useState("mirror")
  const [poolDevices, setPoolDevices] = useState<string[]>([])

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

  const handleCreatePool = async () => {
    try {
      const res = await fetch(apiUrl("/drives/zfs"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: poolName, devices: poolDevices, raid: raidLevel }),
      })
      if (!res.ok) throw new Error(await res.text())
      setMessage("Pool created")
      setPoolOpen(false)
      setPoolName("")
      setPoolDevices([])
      await loadDrives()
    } catch (e) {
      console.error(e)
      setError("Pool creation failed")
    }
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

  const getUsagePercentage = (used: number, size: number) => {
    return Math.round((used / size) * 100)
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Storage Management</h2>
          <p className="text-muted-foreground">Manage disks, volumes and usage</p>
        </div>
        <Dialog open={poolOpen} onOpenChange={setPoolOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => { setPoolDevices([]); setPoolName(""); setRaidLevel("mirror"); setPoolOpen(true) }}>
              Create ZFS Pool
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create ZFS Pool</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="pool-name">Pool Name</Label>
                <Input id="pool-name" value={poolName} onChange={e => setPoolName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="raid">RAID Level</Label>
                <Select value={raidLevel} onValueChange={setRaidLevel}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select RAID" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="stripe">stripe</SelectItem>
                    <SelectItem value="mirror">mirror</SelectItem>
                    <SelectItem value="raidz">raidz</SelectItem>
                    <SelectItem value="raidz2">raidz2</SelectItem>
                    <SelectItem value="raidz3">raidz3</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Devices</Label>
                <div className="grid gap-2">
                  {drives.map(d => (
                    <label key={d.device} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={poolDevices.includes(d.device)}
                        onChange={e => {
                          if (e.target.checked) {
                            setPoolDevices(prev => [...prev, d.device])
                          } else {
                            setPoolDevices(prev => prev.filter(x => x !== d.device))
                          }
                        }}
                      />
                      {d.device} ({d.size} GB)
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => setPoolOpen(false)}>Cancel</Button>
                <Button onClick={handleCreatePool}>Create</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* ZFS Pools */}
      {pools.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>ZFS Pools</CardTitle>
            <CardDescription>Configured ZFS pools</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {pools.map(p => (
                <div key={p.name} className="border rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="font-medium">{p.name}</div>
                    <Badge variant="outline">{p.type}</Badge>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Devices: {p.devices.join(', ')}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

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
