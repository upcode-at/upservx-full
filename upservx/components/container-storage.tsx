"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { HardDrive, Database, Trash2, Plus } from "lucide-react"
import { apiUrl } from "@/lib/api"
import { NotificationContainer } from "@/components/ui/notification"
import { useToast } from "@/hooks/use-toast"

interface DockerVolume {
  name: string
  driver: string
  mountpoint: string
  size?: number
  used?: number
  created?: string
}

interface LXCStorage {
  name: string
  type: string
  source: string
  size?: number
  used?: number
  available?: number
  description?: string
}

export function ContainerStorage() {
  const [dockerVolumes, setDockerVolumes] = useState<DockerVolume[]>([])
  const [lxcStorages, setLxcStorages] = useState<LXCStorage[]>([])
  const [loading, setLoading] = useState(true)
  const [createVolumeOpen, setCreateVolumeOpen] = useState(false)
  const [createStorageOpen, setCreateStorageOpen] = useState(false)
  const [newVolumeName, setNewVolumeName] = useState("")
  const [newStorageName, setNewStorageName] = useState("")
  const [newStorageDriver, setNewStorageDriver] = useState("dir")
  const [newStorageSource, setNewStorageSource] = useState("")

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [volumesRes, storagesRes] = await Promise.all([
        fetch(apiUrl("/containers/volumes")),
        fetch(apiUrl("/containers/storages"))
      ])

      if (volumesRes.ok) {
        setDockerVolumes(await volumesRes.json())
      }
      if (storagesRes.ok) {
        setLxcStorages(await storagesRes.json())
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const createDockerVolume = async () => {
    if (!newVolumeName.trim()) return

    try {
      const response = await fetch(apiUrl("/containers/volumes"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: newVolumeName }),
      })

      if (response.ok) {
        setNewVolumeName("")
        setCreateVolumeOpen(false)
        loadData()
        alert("Docker volume created successfully")
      } else {
        alert("Failed to create Docker volume")
      }
    } catch (err) {
      console.error(err)
      alert("Error creating Docker volume")
    }
  }

  const createLXCStorage = async () => {
    if (!newStorageName.trim()) return

    try {
      const response = await fetch(apiUrl("/containers/storages"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: newStorageName,
          driver: newStorageDriver,
          source: newStorageSource
        }),
      })

      if (response.ok) {
        setNewStorageName("")
        setNewStorageDriver("dir")
        setNewStorageSource("")
        setCreateStorageOpen(false)
        loadData()
        alert("LXC storage pool created successfully")
      } else {
        alert("Failed to create LXC storage pool")
      }
    } catch (err) {
      console.error(err)
      alert("Error creating LXC storage pool")
    }
  }

  const formatSize = (bytes?: number) => {
    if (!bytes) return "Unknown"
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let size = bytes
    let unitIndex = 0
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024
      unitIndex++
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Container Storage</h1>
          <p className="text-muted-foreground">Manage Docker volumes and LXC storage pools</p>
        </div>
      </div>

      <Tabs defaultValue="docker" className="space-y-4">
        <TabsList>
          <TabsTrigger value="docker">Docker Volumes</TabsTrigger>
          <TabsTrigger value="lxc">LXC Storages</TabsTrigger>
        </TabsList>

        <TabsContent value="docker" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Database className="h-5 w-5" />
                    Docker Volumes ({dockerVolumes.length})
                  </CardTitle>
                  <CardDescription>
                    Persistent storage volumes for Docker containers
                  </CardDescription>
                </div>
                <Button onClick={() => setCreateVolumeOpen(true)} size="sm">
                  <Plus className="h-4 w-4 mr-2" />
                  Create Volume
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {dockerVolumes.length === 0 ? (
                <p className="text-muted-foreground">No Docker volumes found</p>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {dockerVolumes.map((volume) => (
                    <Card key={volume.name} className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold">{volume.name}</h3>
                        <Badge variant="outline">{volume.driver}</Badge>
                      </div>
                      <div className="space-y-1 text-sm text-muted-foreground">
                        <p>Mountpoint: {volume.mountpoint}</p>
                        {volume.size && <p>Size: {formatSize(volume.size)}</p>}
                        {volume.used && <p>Used: {formatSize(volume.used)}</p>}
                      </div>
                      <div className="flex gap-2 mt-4">
                        <Button variant="outline" size="sm">
                          <Trash2 className="h-4 w-4 mr-1" />
                          Remove
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="lxc" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <HardDrive className="h-5 w-5" />
                    LXC Storage Pools ({lxcStorages.length})
                  </CardTitle>
                  <CardDescription>
                    Storage pools for LXC containers
                  </CardDescription>
                </div>
                <Button onClick={() => setCreateStorageOpen(true)} size="sm">
                  <Plus className="h-4 w-4 mr-2" />
                  Create Storage Pool
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {lxcStorages.length === 0 ? (
                <p className="text-muted-foreground">No LXC storage pools found</p>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {lxcStorages.map((storage) => (
                    <Card key={storage.name} className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold">{storage.name}</h3>
                        <Badge variant="outline">{storage.type}</Badge>
                      </div>
                      <div className="space-y-1 text-sm text-muted-foreground">
                        <p>Source: {storage.source}</p>
                        {storage.size && <p>Size: {formatSize(storage.size)}</p>}
                        {storage.used && <p>Used: {formatSize(storage.used)}</p>}
                        {storage.available && <p>Available: {formatSize(storage.available)}</p>}
                        {storage.description && <p>Description: {storage.description}</p>}
                      </div>
                      <div className="flex gap-2 mt-4">
                        <Button variant="outline" size="sm">
                          <Trash2 className="h-4 w-4 mr-1" />
                          Remove
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Create Docker Volume Dialog */}
      <Dialog open={createVolumeOpen} onOpenChange={setCreateVolumeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Docker Volume</DialogTitle>
            <DialogDescription>
              Create a new persistent storage volume for Docker containers.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="volume-name">Volume Name</Label>
              <Input
                id="volume-name"
                value={newVolumeName}
                onChange={(e) => setNewVolumeName(e.target.value)}
                placeholder="Enter volume name"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setCreateVolumeOpen(false)}>
              Cancel
            </Button>
            <Button onClick={createDockerVolume}>
              Create Volume
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Create LXC Storage Dialog */}
      <Dialog open={createStorageOpen} onOpenChange={setCreateStorageOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create LXC Storage Pool</DialogTitle>
            <DialogDescription>
              Create a new storage pool for LXC containers.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="storage-name">Storage Pool Name</Label>
              <Input
                id="storage-name"
                value={newStorageName}
                onChange={(e) => setNewStorageName(e.target.value)}
                placeholder="Enter storage pool name"
              />
            </div>
            <div>
              <Label htmlFor="storage-driver">Driver</Label>
              <Select value={newStorageDriver} onValueChange={setNewStorageDriver}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="dir">Directory</SelectItem>
                  <SelectItem value="zfs">ZFS</SelectItem>
                  <SelectItem value="btrfs">Btrfs</SelectItem>
                  <SelectItem value="lvm">LVM</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="storage-source">Source (optional)</Label>
              <Input
                id="storage-source"
                value={newStorageSource}
                onChange={(e) => setNewStorageSource(e.target.value)}
                placeholder="Path or device for storage"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setCreateStorageOpen(false)}>
              Cancel
            </Button>
            <Button onClick={createLXCStorage}>
              Create Storage Pool
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <NotificationContainer />
    </div>
  )
}