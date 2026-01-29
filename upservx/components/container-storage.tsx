"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HardDrive, Database, Trash2 } from "lucide-react"
import { apiUrl } from "@/lib/api"
import { NotificationContainer } from "@/components/ui/notification"

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
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Docker Volumes ({dockerVolumes.length})
              </CardTitle>
              <CardDescription>
                Persistent storage volumes for Docker containers
              </CardDescription>
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
              <CardTitle className="flex items-center gap-2">
                <HardDrive className="h-5 w-5" />
                LXC Storage Pools ({lxcStorages.length})
              </CardTitle>
              <CardDescription>
                Storage pools for LXC containers
              </CardDescription>
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

      <NotificationContainer />
    </div>
  )
}