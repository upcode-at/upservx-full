"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Disc, Download, Upload, Trash2, Plus, Container } from "lucide-react"

export function ImageManagement() {
  const [isoFiles] = useState([
    {
      id: 1,
      name: "ubuntu-22.04.3-desktop-amd64.iso",
      size: 4.7,
      type: "Linux",
      version: "Ubuntu 22.04.3 LTS",
      architecture: "x86_64",
      created: "2024-01-10",
      used: true,
      path: "/var/lib/images/ubuntu-22.04.3-desktop-amd64.iso",
    },
    {
      id: 2,
      name: "Windows_Server_2022.iso",
      size: 5.2,
      type: "Windows",
      version: "Windows Server 2022",
      architecture: "x86_64",
      created: "2024-01-08",
      used: true,
      path: "/var/lib/images/Windows_Server_2022.iso",
    },
    {
      id: 3,
      name: "debian-12.2.0-amd64-netinst.iso",
      size: 0.4,
      type: "Linux",
      version: "Debian 12.2.0",
      architecture: "x86_64",
      created: "2024-01-05",
      used: false,
      path: "/var/lib/images/debian-12.2.0-amd64-netinst.iso",
    },
  ])

  const [containerImages] = useState([
    {
      id: 1,
      repository: "nginx",
      tag: "latest",
      imageId: "sha256:a72860cb95fd",
      size: 187,
      created: "2024-01-14",
      used: true,
      pulls: 1250000000,
    },
    {
      id: 2,
      repository: "mysql",
      tag: "8.0",
      imageId: "sha256:b4a536f7c3b1",
      size: 564,
      created: "2024-01-12",
      used: true,
      pulls: 850000000,
    },
    {
      id: 3,
      repository: "redis",
      tag: "7-alpine",
      imageId: "sha256:c5355f8853e4",
      size: 32,
      created: "2024-01-10",
      used: false,
      pulls: 450000000,
    },
    {
      id: 4,
      repository: "ubuntu",
      tag: "22.04",
      imageId: "sha256:2b7cc08dcdbb",
      size: 77,
      created: "2024-01-09",
      used: true,
      pulls: 2100000000,
    },
    {
      id: 5,
      repository: "node",
      tag: "18-alpine",
      imageId: "sha256:f77a1aef2cec",
      size: 174,
      created: "2024-01-07",
      used: false,
      pulls: 680000000,
    },
  ])

  const [uploadProgress, setUploadProgress] = useState(0)
  const [isUploading, setIsUploading] = useState(false)

  const handleUpload = () => {
    setIsUploading(true)
    setUploadProgress(0)

    const interval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval)
          setIsUploading(false)
          return 100
        }
        return prev + Math.random() * 15
      })
    }, 200)
  }

  const formatSize = (sizeInGB: number) => {
    if (sizeInGB < 1) {
      return `${Math.round(sizeInGB * 1024)} MB`
    }
    return `${sizeInGB.toFixed(1)} GB`
  }

  const formatPulls = (pulls: number) => {
    if (pulls >= 1000000000) {
      return `${(pulls / 1000000000).toFixed(1)}B`
    } else if (pulls >= 1000000) {
      return `${(pulls / 1000000).toFixed(0)}M`
    } else if (pulls >= 1000) {
      return `${(pulls / 1000).toFixed(0)}K`
    }
    return pulls.toString()
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Images & ISOs</h2>
          <p className="text-muted-foreground">ISO-Dateien und Container Images verwalten</p>
        </div>
        <div className="flex gap-2">
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline">
                <Download className="mr-2 h-4 w-4" />
                ISO herunterladen
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>ISO-Datei herunterladen</DialogTitle>
                <DialogDescription>Laden Sie eine neue ISO-Datei von einer URL herunter</DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="iso-url">Download URL</Label>
                  <Input
                    id="iso-url"
                    placeholder="https://releases.ubuntu.com/22.04/ubuntu-22.04.3-desktop-amd64.iso"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="iso-name">Dateiname</Label>
                  <Input id="iso-name" placeholder="ubuntu-22.04.3-desktop-amd64.iso" />
                </div>
                <div className="flex justify-end space-x-2">
                  <Button variant="outline">Abbrechen</Button>
                  <Button onClick={handleUpload}>Herunterladen</Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
          <Dialog>
            <DialogTrigger asChild>
              <Button>
                <Upload className="mr-2 h-4 w-4" />
                ISO hochladen
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>ISO-Datei hochladen</DialogTitle>
                <DialogDescription>Laden Sie eine ISO-Datei von Ihrem Computer hoch</DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center">
                  <Disc className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                    Ziehen Sie eine ISO-Datei hierher oder klicken Sie zum Auswählen
                  </p>
                  <Button variant="outline" size="sm">
                    Datei auswählen
                  </Button>
                </div>
                {isUploading && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Upload läuft...</span>
                      <span>{Math.round(uploadProgress)}%</span>
                    </div>
                    <Progress value={uploadProgress} />
                  </div>
                )}
                <div className="flex justify-end space-x-2">
                  <Button variant="outline">Abbrechen</Button>
                  <Button onClick={handleUpload} disabled={isUploading}>
                    {isUploading ? "Uploading..." : "Hochladen"}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Tabs defaultValue="isos" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="isos">ISO-Dateien</TabsTrigger>
          <TabsTrigger value="containers">Container Images</TabsTrigger>
        </TabsList>

        <TabsContent value="isos" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>ISO-Dateien</CardTitle>
              <CardDescription>Verfügbare ISO-Images für VM-Installation</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Typ</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Architektur</TableHead>
                    <TableHead>Größe</TableHead>
                    <TableHead>Erstellt</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Aktionen</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isoFiles.map((iso) => (
                    <TableRow key={iso.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Disc className="h-4 w-4" />
                          <div>
                            <div className="font-medium">{iso.name}</div>
                            <div className="text-xs text-muted-foreground">{iso.path}</div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{iso.type}</Badge>
                      </TableCell>
                      <TableCell>{iso.version}</TableCell>
                      <TableCell>{iso.architecture}</TableCell>
                      <TableCell>{formatSize(iso.size)}</TableCell>
                      <TableCell>{iso.created}</TableCell>
                      <TableCell>
                        <Badge variant={iso.used ? "default" : "secondary"}>
                          {iso.used ? "In Verwendung" : "Verfügbar"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                            <Download className="h-3 w-3" />
                          </Button>
                          <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent" disabled={iso.used}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="containers" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>Container Images</CardTitle>
                  <CardDescription>Verfügbare Docker Container Images</CardDescription>
                </div>
                <Dialog>
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="mr-2 h-4 w-4" />
                      Image pullen
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Container Image pullen</DialogTitle>
                      <DialogDescription>Laden Sie ein neues Container Image herunter</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="image-name">Image Name</Label>
                        <Input id="image-name" placeholder="nginx:latest" />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="registry">Registry (optional)</Label>
                        <Input id="registry" placeholder="docker.io" />
                      </div>
                      <div className="flex justify-end space-x-2">
                        <Button variant="outline">Abbrechen</Button>
                        <Button>Image pullen</Button>
                      </div>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Repository</TableHead>
                    <TableHead>Tag</TableHead>
                    <TableHead>Image ID</TableHead>
                    <TableHead>Größe</TableHead>
                    <TableHead>Erstellt</TableHead>
                    <TableHead>Pulls</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Aktionen</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {containerImages.map((image) => (
                    <TableRow key={image.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Container className="h-4 w-4" />
                          <span className="font-medium">{image.repository}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{image.tag}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{image.imageId}</TableCell>
                      <TableCell>{formatSize(image.size / 1000)}</TableCell>
                      <TableCell>{image.created}</TableCell>
                      <TableCell>{formatPulls(image.pulls)}</TableCell>
                      <TableCell>
                        <Badge variant={image.used ? "default" : "secondary"}>
                          {image.used ? "In Verwendung" : "Verfügbar"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                            <Download className="h-3 w-3" />
                          </Button>
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-8 w-8 bg-transparent"
                            disabled={image.used}
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
