"use client"

import { useState, useEffect, useCallback } from "react"
import { apiUrl } from "@/lib/api"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Search, Download, CheckCircle, ChevronLeft, ChevronRight } from "lucide-react"
import { NotificationContainer } from "@/components/ui/notification"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface App {
  id: string
  name: string
  description: string
  version: string
  category: string
  icon: string
  author: string
  ports: string[]
  volumes: string[]
  installed: boolean
}

interface AppDetails extends App {
  environment: Record<string, string>
  compose_content: string
  readme: string
}

export function AppStore() {
  const [apps, setApps] = useState<App[]>([])
  const [filteredApps, setFilteredApps] = useState<App[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedApp, setSelectedApp] = useState<AppDetails | null>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [installDialogOpen, setInstallDialogOpen] = useState(false)
  const [customName, setCustomName] = useState("")
  const [success, setSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [pageSize, setPageSize] = useState(20)
  const [currentPage, setCurrentPage] = useState(1)

  const getApiUrl = apiUrl

  const filterApps = () => {
    let filtered = apps

    if (selectedCategory !== "all") {
      filtered = filtered.filter((app) => app.category === selectedCategory)
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(
        (app) =>
          app.name.toLowerCase().includes(query) ||
          app.description.toLowerCase().includes(query) ||
          app.category.toLowerCase().includes(query)
      )
    }

    setFilteredApps(filtered)
    setCurrentPage(1)
  }

  useEffect(() => {
    filterApps()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apps, selectedCategory, searchQuery])

  const totalPages = Math.max(1, Math.ceil(filteredApps.length / pageSize))
  const paginatedApps = filteredApps.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  const loadApps = useCallback(async () => {
    try {
      // Ensure we're in the browser before calling apiUrl
      if (typeof window === "undefined") return
      
      const url = getApiUrl("/containers/app-store/apps")
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setApps(data)
      }
    } catch (e) {
      console.error("Failed to load apps:", e)
    }
  }, [])

  const loadCategories = useCallback(async () => {
    try {
      // Ensure we're in the browser before calling apiUrl
      if (typeof window === "undefined") return
      
      const url = getApiUrl("/containers/app-store/categories")
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setCategories(["all", ...data])
      }
    } catch (e) {
      console.error("Failed to load categories:", e)
    }
  }, [])

  useEffect(() => {
    loadApps()
    loadCategories()
  }, [loadApps, loadCategories])

  const handleShowDetails = async (appId: string) => {
    try {
      const res = await fetch(getApiUrl(`/containers/app-store/apps/${appId}`))
      if (res.ok) {
        const data = await res.json()
        setSelectedApp(data)
        setDetailsOpen(true)
      }
    } catch {
      setError("Failed to load app details")
    }
  }

  const handleInstallClick = (app: App) => {
    setSelectedApp(app as AppDetails)
    setCustomName("")
    setInstallDialogOpen(true)
  }

  const handleInstall = async () => {
    if (!selectedApp) return

    setLoading(true)
    setError(null)
    setSuccess(null)

    try {
      const res = await fetch(
        getApiUrl(`/containers/app-store/apps/${selectedApp.id}/install`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ custom_name: customName || null }),
        }
      )

      const data = await res.json()

      if (res.ok) {
        setSuccess(data.message)
        setInstallDialogOpen(false)
        loadApps()
      } else {
        setError(data.detail || "Failed to install app")
      }
    } catch {
      setError("Failed to install app")
    } finally {
      setLoading(false)
    }
  }

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      media: "bg-red-500/10 text-white",
      productivity: "bg-blue-500/10 text-blue-500",
      management: "bg-green-500/10 text-green-500",
      security: "bg-red-500/10 text-red-500",
      networking: "bg-yellow-500/10 text-yellow-500",
      other: "bg-gray-500/10 text-gray-500",
    }
    return colors[category] || colors.other
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">App Store</h1>
        <p className="text-muted-foreground">
          Install pre-configured applications with one click
        </p>
      </div>

      <NotificationContainer success={success} error={error} onClearSuccess={() => setSuccess(null)} onClearError={() => setError(null)} />

      <div className="flex flex-col gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search apps..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        {/* Category buttons that wrap on smaller screens */}
        <div className="flex gap-2 flex-wrap">
          {categories.map((category) => (
            <Button
              key={category}
              variant={selectedCategory === category ? "default" : "outline"}
              size="sm"
              onClick={() => setSelectedCategory(category)}
              className="capitalize"
            >
              {category}
            </Button>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {filteredApps.length} App{filteredApps.length !== 1 ? "s" : ""} gefunden
        </p>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Apps pro Seite:</span>
          <Select
            value={String(pageSize)}
            onValueChange={(val) => {
              setPageSize(Number(val))
              setCurrentPage(1)
            }}
          >
            <SelectTrigger className="w-20 h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[10, 20, 30, 50].map((size) => (
                <SelectItem key={size} value={String(size)}>{size}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.isArray(paginatedApps) && paginatedApps.map((app) => (
          <Card key={app.id} className="flex flex-col">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="text-4xl">
                    {app.icon.startsWith('/') ? (
                      <img 
                        src={getApiUrl(app.icon)} 
                        alt={app.name}
                        className="w-12 h-12 object-contain rounded"
                      />
                    ) : (
                      app.icon
                    )}
                  </div>
                  <div>
                    <CardTitle className="text-lg">{app.name}</CardTitle>
                    <CardDescription className="text-xs">
                      v{app.version}
                    </CardDescription>
                  </div>
                </div>
                {app.installed && (
                  <Badge variant="secondary" className="gap-1">
                    <CheckCircle className="h-3 w-3" />
                    Installed
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="flex-1">
              <p className="text-sm text-muted-foreground line-clamp-3">
                {app.description}
              </p>
              <div className="mt-3 flex gap-2">
                <Badge className={getCategoryColor(app.category)}>
                  {app.category}
                </Badge>
              </div>
            </CardContent>
            <CardFooter className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => handleShowDetails(app.id)}
              >
                Details
              </Button>
              {!app.installed ? (
                <Button
                  size="sm"
                  className="flex-1 gap-1"
                  onClick={() => handleInstallClick(app)}
                >
                  <Download className="h-4 w-4" />
                  Install
                </Button>
              ) : (
                <Button size="sm" variant="secondary" className="flex-1" disabled>
                  Installed
                </Button>
              )}
            </CardFooter>
          </Card>
        ))}
      </div>

      {filteredApps.length === 0 && (
        <div className="text-center py-12">
          <p className="text-muted-foreground">No apps found</p>
        </div>
      )}

      {filteredApps.length > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Seite {currentPage} von {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter((page) =>
                page === 1 ||
                page === totalPages ||
                Math.abs(page - currentPage) <= 2
              )
              .reduce<(number | "...")[]>((acc, page, idx, arr) => {
                if (idx > 0 && typeof arr[idx - 1] === "number" && (page as number) - (arr[idx - 1] as number) > 1) {
                  acc.push("...")
                }
                acc.push(page)
                return acc
              }, [])
              .map((item, idx) =>
                item === "..." ? (
                  <span key={`ellipsis-${idx}`} className="text-sm text-muted-foreground px-1">...</span>
                ) : (
                  <Button
                    key={item}
                    variant={currentPage === item ? "default" : "outline"}
                    size="sm"
                    className="w-8 h-8 p-0"
                    onClick={() => setCurrentPage(item as number)}
                  >
                    {item}
                  </Button>
                )
              )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* App Details Dialog */}
      <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <div className="flex items-center gap-3">
              {selectedApp?.icon.startsWith('/') ? (
                <img 
                  src={getApiUrl(selectedApp.icon)} 
                  alt={selectedApp.name}
                  className="w-16 h-16 object-contain rounded"
                />
              ) : (
                <span className="text-4xl">{selectedApp?.icon}</span>
              )}
              <div>
                <DialogTitle>{selectedApp?.name}</DialogTitle>
                <DialogDescription>
                  Version {selectedApp?.version} • {selectedApp?.author}
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>
          <Tabs defaultValue="overview" className="flex-1 overflow-hidden flex flex-col">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="compose">Docker Compose</TabsTrigger>
              <TabsTrigger value="readme">Description</TabsTrigger>
            </TabsList>
            <ScrollArea className="flex-1 pr-4">
              <TabsContent value="overview" className="space-y-4">
                <div>
                  <h3 className="font-semibold mb-2">Description</h3>
                  <p className="text-sm text-muted-foreground">
                    {selectedApp?.description}
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Ports</h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedApp?.ports.map((port, idx) => (
                      <Badge key={idx} variant="outline">
                        {port}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Volumes</h3>
                  <div className="space-y-1">
                    {selectedApp?.volumes.map((volume, idx) => (
                      <code
                        key={idx}
                        className="block text-xs bg-muted p-2 rounded"
                      >
                        {volume}
                      </code>
                    ))}
                  </div>
                </div>
                {selectedApp?.environment &&
                  Object.keys(selectedApp.environment).length > 0 && (
                    <div>
                      <h3 className="font-semibold mb-2">
                        Environment Variables
                      </h3>
                      <div className="space-y-1">
                        {Object.entries(selectedApp.environment).map(
                          ([key, value]) => (
                            <code
                              key={key}
                              className="block text-xs bg-muted p-2 rounded"
                            >
                              {key}={value}
                            </code>
                          )
                        )}
                      </div>
                    </div>
                  )}
              </TabsContent>
              <TabsContent value="compose">
                <pre className="text-xs bg-muted p-4 rounded overflow-x-auto">
                  {selectedApp?.compose_content}
                </pre>
              </TabsContent>
              <TabsContent value="readme">
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <pre className="whitespace-pre-wrap text-sm">
                    {selectedApp?.readme || "No description available."}
                  </pre>
                </div>
              </TabsContent>
            </ScrollArea>
          </Tabs>
          <DialogFooter>
            {!selectedApp?.installed ? (
              <Button onClick={() => {
                setDetailsOpen(false)
                handleInstallClick(selectedApp!)
              }}>
                <Download className="h-4 w-4 mr-2" />
                Install
              </Button>
            ) : (
              <Badge variant="secondary" className="gap-1">
                <CheckCircle className="h-3 w-3" />
                Already Installed
              </Badge>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Install Dialog */}
      <Dialog open={installDialogOpen} onOpenChange={setInstallDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Install {selectedApp?.name}</DialogTitle>
            <DialogDescription>
              Choose a name for this installation or leave empty to use the
              default name.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="custom-name">Project Name (optional)</Label>
              <Input
                id="custom-name"
                placeholder={selectedApp?.id}
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Will be normalized to lowercase with hyphens
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setInstallDialogOpen(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button onClick={handleInstall} disabled={loading}>
              {loading ? "Installing..." : "Install"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
