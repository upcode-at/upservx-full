"use client"

import { useState, useEffect } from "react"
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
  const [isoFiles, setIsoFiles] = useState<
    {
      id: number
      name: string
      size: number
      type: string
      version: string
      architecture: string
      created: string
      used: boolean
      path: string
    }[]
  >([])

  const [containerImages, setContainerImages] = useState<
    {
      id: number
      repository: string
      tag: string
      imageId: string
      size: number
      created: string
      used: boolean
      pulls: number
    }[]
  >([])

  useEffect(() => {
    const loadIsos = async () => {
      try {
        const res = await fetch("http://localhost:8000/isos")
        if (res.ok) {
          const data = await res.json()
          setIsoFiles(data.isos || [])
        }
      } catch (e) {
        console.error(e)
      }
    }
    loadIsos()
  }, [])

  useEffect(() => {
    const loadImages = async () => {
      try {
        const res = await fetch("http://localhost:8000/images?type=docker&full=1")
        if (res.ok) {
          const data = await res.json()
          setContainerImages(data.images || [])
        }
      } catch (e) {
        console.error(e)
      }
    }
    loadImages()
  }, [])

  const [uploadProgress, setUploadProgress] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const [isoFile, setIsoFile] = useState<File | null>(null)

  const [downloadProgress, setDownloadProgress] = useState(0)
  const [isDownloading, setIsDownloading] = useState(false)
  const [isoUrl, setIsoUrl] = useState("")
  const [isoDownloadName, setIsoDownloadName] = useState("")

  const [pullProgress, setPullProgress] = useState(0)
  const [isPulling, setIsPulling] = useState(false)
  const [imageName, setImageName] = useState("")
  const [registry, setRegistry] = useState("")

  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openUpload, setOpenUpload] = useState(false)
  const [openPull, setOpenPull] = useState(false)
  const [openDownload, setOpenDownload] = useState(false)

  useEffect(() => {
    if (!message && !error) return
    const t = setTimeout(() => {
      setMessage(null)
      setError(null)
    }, 3000)
    return () => clearTimeout(t)
  }, [message, error])

  const handleUpload = async () => {
    if (!isoFile) return
    setIsUploading(true)
    setUploadProgress(0)
    setError(null)
    setMessage(null)

    const data = new FormData()
    data.append("file", isoFile)

    const interval = setInterval(() => {
      setUploadProgress((p) => Math.min(p + 5, 95))
    }, 200)

    try {
      const res = await fetch("http://localhost:8000/isos", {
        method: "POST",
        body: data,
      })
      if (res.ok) {
        const info = await res.json()
        setIsoFiles((prev) => [...prev, info])
        setMessage("ISO hochgeladen")
      } else {
        let msg = "Fehler beim Upload"
        try {
          const d = await res.json()
          msg = d.detail || msg
        } catch {
          msg = await res.text()
        }
        setError(msg)
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
    }
    clearInterval(interval)
    setUploadProgress(100)
    setIsUploading(false)
    setIsoFile(null)
    setOpenUpload(false)
  }

  const handleDownload = async () => {
    if (!isoUrl) return
    setIsDownloading(true)
    setDownloadProgress(0)
    setError(null)
    setMessage(null)

    const interval = setInterval(() => {
      setDownloadProgress((p) => Math.min(p + 5, 95))
    }, 200)

    try {
      const res = await fetch("http://localhost:8000/isos/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: isoUrl, name: isoDownloadName || null }),
      })
      if (res.ok) {
        const info = await res.json()
        setIsoFiles((prev) => [...prev, info])
        setMessage("ISO heruntergeladen")
      } else {
        let msg = "Fehler beim Download"
        try {
          const d = await res.json()
          msg = d.detail || msg
        } catch {
          msg = await res.text()
        }
        setError(msg)
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
    }
    clearInterval(interval)
    setDownloadProgress(100)
    setIsDownloading(false)
    setIsoUrl("")
    setIsoDownloadName("")
    setOpenDownload(false)
  }

  const handleDeleteIso = async (name: string) => {
    try {
      const res = await fetch(`http://localhost:8000/isos/${name}`, { method: "DELETE" })
      if (res.ok) {
        setIsoFiles((prev) => prev.filter((i) => i.name !== name))
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleDeleteImage = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8000/images/${id}?type=docker`, { method: "DELETE" })
      if (res.ok) {
        setContainerImages((prev) => prev.filter((i) => i.imageId !== id))
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handlePullImage = async () => {
    if (!imageName) return
    setIsPulling(true)
    setPullProgress(0)
    setError(null)
    setMessage(null)

    const interval = setInterval(() => {
      setPullProgress((p) => Math.min(p + 5, 95))
    }, 200)

    try {
      const res = await fetch("http://localhost:8000/images/pull", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imageName, registry: registry || null }),
      })
      if (res.ok) {
        const list = await fetch("http://localhost:8000/images?type=docker&full=1")
        if (list.ok) {
          const data = await list.json()
          setContainerImages(data.images || [])
        }
        setMessage("Image gepullt")
      } else {
        let msg = "Fehler beim Pullen"
        try {
          const d = await res.json()
          msg = d.detail || msg
        } catch {
          msg = await res.text()
        }
        setError(msg)
      }
    } catch (e) {
      console.error(e)
      if (e instanceof Error) setError(e.message)
    }
    clearInterval(interval)
    setPullProgress(100)
    setIsPulling(false)
    setImageName("")
    setRegistry("")
    setOpenPull(false)
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
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Images & ISOs</h2>
          <p className="text-muted-foreground">ISO-Dateien und Container Images verwalten</p>
        </div>
        <div className="flex gap-2">
          <Dialog open={openDownload} onOpenChange={setOpenDownload}>
            <DialogTrigger asChild>
              <Button variant="outline" onClick={() => setOpenDownload(true)}>
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
                    value={isoUrl}
                    onChange={(e) => setIsoUrl(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="iso-name">Dateiname</Label>
                  <Input
                    id="iso-name"
                    placeholder="ubuntu-22.04.3-desktop-amd64.iso"
                    value={isoDownloadName}
                    onChange={(e) => setIsoDownloadName(e.target.value)}
                  />
                </div>
                {isDownloading && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Download läuft...</span>
                      <span>{Math.round(downloadProgress)}%</span>
                    </div>
                    <Progress value={downloadProgress} />
                  </div>
                )}
                <div className="flex justify-end space-x-2">
                  <Button variant="outline" onClick={() => setOpenDownload(false)}>Abbrechen</Button>
                  <Button onClick={handleDownload} disabled={isDownloading}>
                    {isDownloading ? "Downloading..." : "Herunterladen"}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
          <Dialog open={openUpload} onOpenChange={setOpenUpload}>
            <DialogTrigger asChild>
              <Button onClick={() => setOpenUpload(true)}>
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
                  <Input
                    type="file"
                    accept=".iso"
                    onChange={(e) => setIsoFile(e.target.files?.[0] || null)}
                  />
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
                  <Button variant="outline" onClick={() => setOpenUpload(false)}>Abbrechen</Button>
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
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-8 w-8 bg-transparent"
                            asChild
                          >
                            <a href={`http://localhost:8000/isos/${iso.name}/file`}>
                              <Download className="h-3 w-3" />
                            </a>
                          </Button>
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-8 w-8 bg-transparent"
                            disabled={iso.used}
                            onClick={() => handleDeleteIso(iso.name)}
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

        <TabsContent value="containers" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>Container Images</CardTitle>
                  <CardDescription>Verfügbare Docker Container Images</CardDescription>
                </div>
                <Dialog open={openPull} onOpenChange={setOpenPull}>
                  <DialogTrigger asChild>
                    <Button onClick={() => setOpenPull(true)}>
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
                        <Input
                          id="image-name"
                          placeholder="nginx:latest"
                          value={imageName}
                          onChange={(e) => setImageName(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="registry">Registry (optional)</Label>
                        <Input
                          id="registry"
                          placeholder="docker.io"
                          value={registry}
                          onChange={(e) => setRegistry(e.target.value)}
                        />
                      </div>
                      {isPulling && (
                        <div className="space-y-2">
                          <div className="flex justify-between text-sm">
                            <span>Download läuft...</span>
                            <span>{Math.round(pullProgress)}%</span>
                          </div>
                          <Progress value={pullProgress} />
                        </div>
                      )}
                      <div className="flex justify-end space-x-2">
                        <Button variant="outline" onClick={() => setOpenPull(false)}>Abbrechen</Button>
                        <Button onClick={handlePullImage} disabled={isPulling}>
                          {isPulling ? "Pulling..." : "Image pullen"}
                        </Button>
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
                            onClick={() => handleDeleteImage(image.imageId)}
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
