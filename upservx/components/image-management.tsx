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
import { apiUrl } from "@/lib/api"

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
      pulls: number
    }[]
  >([])

  const [lxcImages, setLxcImages] = useState<
    {
      id: number
      repository: string
      tag: string
      imageId: string
      size: number
      created: string
      pulls: number
    }[]
  >([])

  useEffect(() => {
    const loadIsos = async () => {
      try {
        const res = await fetch(apiUrl("/isos"))
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
        const res = await fetch(apiUrl("/images?type=docker&full=1"))
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

  useEffect(() => {
    const loadLxcImages = async () => {
      try {
        const res = await fetch(apiUrl("/images?type=lxc&full=1"))
        if (res.ok) {
          const data = await res.json()
          setLxcImages(data.images || [])
        }
      } catch (e) {
        console.error(e)
      }
    }
    loadLxcImages()
  }, [])

  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadedBytes, setUploadedBytes] = useState(0)
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

  const [pullProgressLxc, setPullProgressLxc] = useState(0)
  const [isPullingLxc, setIsPullingLxc] = useState(false)
  const [lxcImageName, setLxcImageName] = useState("")
  const [lxcRemote, setLxcRemote] = useState("")

  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openUpload, setOpenUpload] = useState(false)
  const [openPull, setOpenPull] = useState(false)
  const [openPullLxc, setOpenPullLxc] = useState(false)
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
    setUploadedBytes(0)
    setError(null)
    setMessage(null)

    const data = new FormData()
    data.append("file", isoFile)

    const xhr = new XMLHttpRequest()
    xhr.open("POST", apiUrl("/isos"))
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setUploadedBytes(e.loaded)
        setUploadProgress((e.loaded / isoFile.size) * 100)
      }
    }
    xhr.onload = () => {
      setIsUploading(false)
      setUploadProgress(100)
      setUploadedBytes(isoFile.size)
      setIsoFile(null)
      setOpenUpload(false)
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const info = JSON.parse(xhr.responseText)
          setIsoFiles((prev) => [...prev, info])
          setMessage("ISO uploaded")
        } catch {
          setError("Upload error")
        }
      } else {
        let msg = "Upload error"
        try {
          const d = JSON.parse(xhr.responseText)
          msg = d.detail || msg
        } catch {
          // ignore
        }
        setError(msg)
      }
    }
    xhr.onerror = () => {
      setIsUploading(false)
      setError("Upload failed")
    }
    xhr.send(data)
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
      const res = await fetch(apiUrl("/isos/download"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: isoUrl, name: isoDownloadName || null }),
      })
      if (res.ok) {
        const info = await res.json()
        setIsoFiles((prev) => [...prev, info])
        setMessage("ISO downloaded")
      } else {
        let msg = "Download error"
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
      const res = await fetch(apiUrl(`/isos/${name}`), { method: "DELETE" })
      if (res.ok) {
        setIsoFiles((prev) => prev.filter((i) => i.name !== name))
      }
    } catch (e) {
      console.error(e)
    }
  }

  const handleDeleteImage = async (
    id: string,
    name: string,
  ) => {
    try {
      const res = await fetch(
        apiUrl(`/images/${id}?type=docker`),
        { method: "DELETE" },
      )
      if (res.ok) {
        setContainerImages((prev) => prev.filter((i) => i.imageId !== id))
        setMessage(`${name} deleted`)
      } else {
        let msg = "Error deleting"
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
      const res = await fetch(apiUrl("/images/pull"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imageName, registry: registry || null }),
      })
      if (res.ok) {
        const list = await fetch(apiUrl("/images?type=docker&full=1"))
        if (list.ok) {
          const data = await list.json()
          setContainerImages(data.images || [])
        }
        setMessage("Image pulled")
      } else {
        let msg = "Error pulling"
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

  const handleDeleteLxcImage = async (id: string, name: string) => {
    try {
      const res = await fetch(apiUrl(`/images/${id}?type=lxc`), {
        method: "DELETE",
      })
      if (res.ok) {
        setLxcImages((prev) => prev.filter((i) => i.imageId !== id))
        setMessage(`${name} deleted`)
      } else {
        let msg = "Error deleting"
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
  }

  const handlePullLxcImage = async () => {
    if (!lxcImageName) return
    setIsPullingLxc(true)
    setPullProgressLxc(0)
    setError(null)
    setMessage(null)

    const interval = setInterval(() => {
      setPullProgressLxc((p) => Math.min(p + 5, 95))
    }, 200)

    try {
      const res = await fetch(apiUrl("/images/pull"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image: lxcImageName,
          registry: lxcRemote || null,
          type: "lxc",
        }),
      })
      if (res.ok) {
        const list = await fetch(apiUrl("/images?type=lxc&full=1"))
        if (list.ok) {
          const data = await list.json()
          setLxcImages(data.images || [])
        }
        setMessage("Image pulled")
      } else {
        let msg = "Error pulling"
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
    setPullProgressLxc(100)
    setIsPullingLxc(false)
    setLxcImageName("")
    setLxcRemote("")
    setOpenPullLxc(false)
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
          <p className="text-muted-foreground">Manage ISO files and container images</p>
        </div>
      </div>

      <Tabs defaultValue="isos" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="isos">ISO Files</TabsTrigger>
          <TabsTrigger value="containers">Container Images</TabsTrigger>
          <TabsTrigger value="lxc">LXC Images</TabsTrigger>
        </TabsList>

        <TabsContent value="isos" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>ISO Files</CardTitle>
                  <CardDescription>Available ISO images for VM installation</CardDescription>
                </div>
                <div className="flex gap-2">
                  <Dialog open={openDownload} onOpenChange={setOpenDownload}>
                    <DialogTrigger asChild>
                      <Button variant="outline" onClick={() => setOpenDownload(true)}>
                        <Download className="mr-2 h-4 w-4" />
                        Download ISO
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Download ISO File</DialogTitle>
                        <DialogDescription>Download a new ISO file from a URL</DialogDescription>
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
                          <Label htmlFor="iso-name">File name</Label>
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
                              <span>Downloading...</span>
                              <span>{Math.round(downloadProgress)}%</span>
                            </div>
                            <Progress value={downloadProgress} />
                          </div>
                        )}
                        <div className="flex justify-end space-x-2">
                          <Button variant="outline" onClick={() => setOpenDownload(false)}>Cancel</Button>
                          <Button onClick={handleDownload} disabled={isDownloading}>
                            {isDownloading ? "Downloading..." : "Download"}
                          </Button>
                        </div>
                      </div>
                    </DialogContent>
                  </Dialog>
                  <Dialog open={openUpload} onOpenChange={setOpenUpload}>
                    <DialogTrigger asChild>
                      <Button onClick={() => setOpenUpload(true)}>
                        <Upload className="mr-2 h-4 w-4" />
                        Upload ISO
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Upload ISO File</DialogTitle>
                        <DialogDescription>Upload an ISO file from your computer</DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4">
                        <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center">
                          <Disc className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                            Drag an ISO file here or click to select
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
                              <span>Uploading...</span>
                              <span>
                                {Math.round(uploadedBytes / 1024)} KB / {isoFile ? Math.round(isoFile.size / 1024) : 0} KB
                              </span>
                            </div>
                            <Progress value={uploadProgress} />
                          </div>
                        )}
                        <div className="flex justify-end space-x-2">
                          <Button variant="outline" onClick={() => setOpenUpload(false)}>Cancel</Button>
                          <Button onClick={handleUpload} disabled={isUploading}>
                            {isUploading ? "Uploading..." : "Upload"}
                          </Button>
                        </div>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Typ</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Architektur</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isoFiles.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center">
                        No isos found
                      </TableCell>
                    </TableRow>
                  ) : (
                    isoFiles.map((iso) => (
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
                            {iso.used ? "In use" : "Available"}
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
                              <a href={apiUrl(`/isos/${iso.name}/file`)}>
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
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="lxc" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>LXC Images</CardTitle>
                  <CardDescription>Available LXC container images</CardDescription>
                </div>
                <Dialog open={openPullLxc} onOpenChange={setOpenPullLxc}>
                  <DialogTrigger asChild>
                    <Button onClick={() => setOpenPullLxc(true)}>
                      <Plus className="mr-2 h-4 w-4" />
                      Pull Image
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Pull LXC Image</DialogTitle>
                      <DialogDescription>Download a new LXC image</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="lxc-image-name">Image Name</Label>
                        <Input
                          id="lxc-image-name"
                          placeholder="ubuntu:22.04"
                          value={lxcImageName}
                          onChange={(e) => setLxcImageName(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="lxc-remote">Remote (optional)</Label>
                        <Input
                          id="lxc-remote"
                          placeholder="images"
                          value={lxcRemote}
                          onChange={(e) => setLxcRemote(e.target.value)}
                        />
                      </div>
                      {isPullingLxc && (
                        <div className="space-y-2">
                          <div className="flex justify-between text-sm">
                            <span>Downloading...</span>
                            <span>{Math.round(pullProgressLxc)}%</span>
                          </div>
                          <Progress value={pullProgressLxc} />
                        </div>
                      )}
                      <div className="flex justify-end space-x-2">
                        <Button variant="outline" onClick={() => setOpenPullLxc(false)}>Cancel</Button>
                        <Button onClick={handlePullLxcImage} disabled={isPullingLxc}>
                          {isPullingLxc ? "Pulling..." : "Pull Image"}
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
                    <TableHead>Size</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Pulls</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {lxcImages.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center">
                        No images found
                      </TableCell>
                    </TableRow>
                  ) : (
                    lxcImages.map((image) => (
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
                          <div className="flex gap-1">
                            <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                              <Download className="h-3 w-3" />
                            </Button>
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-8 w-8 bg-transparent"
                              onClick={() => handleDeleteLxcImage(image.imageId, `${image.repository}:${image.tag}`)}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
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
                  <CardDescription>Available Docker container images</CardDescription>
                </div>
                <Dialog open={openPull} onOpenChange={setOpenPull}>
                  <DialogTrigger asChild>
                    <Button onClick={() => setOpenPull(true)}>
                      <Plus className="mr-2 h-4 w-4" />
                      Pull Image
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Pull Container Image</DialogTitle>
                      <DialogDescription>Download a new container image</DialogDescription>
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
                            <span>Downloading...</span>
                            <span>{Math.round(pullProgress)}%</span>
                          </div>
                          <Progress value={pullProgress} />
                        </div>
                      )}
                      <div className="flex justify-end space-x-2">
                        <Button variant="outline" onClick={() => setOpenPull(false)}>Cancel</Button>
                        <Button onClick={handlePullImage} disabled={isPulling}>
                          {isPulling ? "Pulling..." : "Pull Image"}
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
                    <TableHead>Size</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Pulls</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {containerImages.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center">
                        No images found
                      </TableCell>
                    </TableRow>
                  ) : (
                    containerImages.map((image) => (
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
                          <div className="flex gap-1">
                            <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                              <Download className="h-3 w-3" />
                            </Button>
                            <Button
                              variant="outline"
                              size="icon"
                              className="h-8 w-8 bg-transparent"
                              onClick={() => handleDeleteImage(image.imageId, `${image.repository}:${image.tag}`)}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
