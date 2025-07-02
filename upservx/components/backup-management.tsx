"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Progress } from "@/components/ui/progress"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Server, Calendar, Play, Settings, Plus } from "lucide-react"

export function BackupManagement() {
  const [backupServers] = useState([
    {
      id: 1,
      name: "Primary Backup Server",
      type: "NFS",
      address: "192.168.1.200",
      port: 2049,
      path: "/backups",
      status: "connected",
      capacity: 5000,
      used: 2100,
      lastSync: "2024-01-15 02:00",
    },
    {
      id: 2,
      name: "Cloud Backup",
      type: "S3",
      address: "s3.amazonaws.com",
      port: 443,
      path: "my-backup-bucket",
      status: "connected",
      capacity: 10000,
      used: 850,
      lastSync: "2024-01-15 03:30",
    },
    {
      id: 3,
      name: "Local Backup Drive",
      type: "Local",
      address: "/mnt/backup",
      port: null,
      path: "/mnt/backup",
      status: "connected",
      capacity: 1000,
      used: 450,
      lastSync: "2024-01-15 01:15",
    },
  ])

  const [backupJobs] = useState([
    {
      id: 1,
      name: "VM Full Backup",
      type: "VM",
      targets: ["Ubuntu-Server-01", "Windows-Dev"],
      schedule: "Daily 02:00",
      destination: "Primary Backup Server",
      status: "completed",
      lastRun: "2024-01-15 02:00",
      nextRun: "2024-01-16 02:00",
      size: "45 GB",
      retention: "30 days",
    },
    {
      id: 2,
      name: "Container Data Backup",
      type: "Container",
      targets: ["mysql-db", "nginx-web"],
      schedule: "Every 6 hours",
      destination: "Cloud Backup",
      status: "running",
      lastRun: "2024-01-15 12:00",
      nextRun: "2024-01-15 18:00",
      size: "2.1 GB",
      retention: "14 days",
    },
    {
      id: 3,
      name: "System Configuration",
      type: "System",
      targets: ["/etc", "/var/lib"],
      schedule: "Weekly",
      destination: "Local Backup Drive",
      status: "scheduled",
      lastRun: "2024-01-08 03:00",
      nextRun: "2024-01-15 03:00",
      size: "850 MB",
      retention: "90 days",
    },
  ])

  const getStatusColor = (status: string) => {
    switch (status) {
      case "connected":
      case "completed":
        return "default"
      case "running":
        return "outline"
      case "scheduled":
        return "secondary"
      case "failed":
      case "disconnected":
        return "destructive"
      default:
        return "secondary"
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case "connected":
        return "Verbunden"
      case "disconnected":
        return "Getrennt"
      case "completed":
        return "Abgeschlossen"
      case "running":
        return "Läuft"
      case "scheduled":
        return "Geplant"
      case "failed":
        return "Fehlgeschlagen"
      default:
        return status
    }
  }

  const getUsagePercentage = (used: number, capacity: number) => {
    return Math.round((used / capacity) * 100)
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Backup Management</h2>
          <p className="text-muted-foreground">Backup-Server und automatische Sicherungen verwalten</p>
        </div>
        <div className="flex gap-2">
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline">
                <Server className="mr-2 h-4 w-4" />
                Backup Server hinzufügen
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Neuen Backup Server hinzufügen</DialogTitle>
                <DialogDescription>Konfigurieren Sie einen neuen Backup-Server</DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="server-name">Server Name</Label>
                  <Input id="server-name" placeholder="z.B. Backup Server 2" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="server-type">Typ</Label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="Typ auswählen" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="nfs">NFS</SelectItem>
                        <SelectItem value="smb">SMB/CIFS</SelectItem>
                        <SelectItem value="s3">S3 Compatible</SelectItem>
                        <SelectItem value="ftp">FTP/SFTP</SelectItem>
                        <SelectItem value="local">Local</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="server-port">Port</Label>
                    <Input id="server-port" placeholder="z.B. 2049" />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="server-address">IP-Adresse/URL</Label>
                  <Input id="server-address" placeholder="z.B. 192.168.1.200 oder backup.example.com" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="server-path">Pfad</Label>
                  <Input id="server-path" placeholder="z.B. /backups" />
                </div>
                <div className="flex justify-end space-x-2">
                  <Button variant="outline">Abbrechen</Button>
                  <Button>Server hinzufügen</Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
          <Dialog>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Backup Job erstellen
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Neuen Backup Job erstellen</DialogTitle>
                <DialogDescription>Konfigurieren Sie einen automatischen Backup-Job</DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="job-name">Job Name</Label>
                    <Input id="job-name" placeholder="z.B. Daily VM Backup" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="job-type">Backup Typ</Label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="Typ auswählen" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="vm">Virtual Machine</SelectItem>
                        <SelectItem value="container">Container</SelectItem>
                        <SelectItem value="system">System Files</SelectItem>
                        <SelectItem value="database">Database</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="job-schedule">Zeitplan</Label>
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Zeitplan auswählen" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="hourly">Stündlich</SelectItem>
                      <SelectItem value="daily">Täglich</SelectItem>
                      <SelectItem value="weekly">Wöchentlich</SelectItem>
                      <SelectItem value="monthly">Monatlich</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="job-destination">Ziel Server</Label>
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Server auswählen" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="primary">Primary Backup Server</SelectItem>
                      <SelectItem value="cloud">Cloud Backup</SelectItem>
                      <SelectItem value="local">Local Backup Drive</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex justify-end space-x-2">
                  <Button variant="outline">Abbrechen</Button>
                  <Button>Job erstellen</Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Tabs defaultValue="servers" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="servers">Backup Server</TabsTrigger>
          <TabsTrigger value="jobs">Backup Jobs</TabsTrigger>
          <TabsTrigger value="history">Backup Verlauf</TabsTrigger>
        </TabsList>

        <TabsContent value="servers" className="space-y-4">
          <div className="grid gap-4">
            {backupServers.map((server) => (
              <Card key={server.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Server className="h-5 w-5" />
                        {server.name}
                        <Badge variant={getStatusColor(server.status)}>{getStatusText(server.status)}</Badge>
                        <Badge variant="outline">{server.type}</Badge>
                      </CardTitle>
                      <CardDescription>
                        {server.address}
                        {server.port && `:${server.port}`}
                      </CardDescription>
                    </div>
                    <Button variant="outline" size="icon">
                      <Settings className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-4">
                    <div>
                      <span className="text-muted-foreground">Kapazität:</span>
                      <div className="font-medium">{server.capacity} GB</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Belegt:</span>
                      <div className="font-medium">{server.used} GB</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Verfügbar:</span>
                      <div className="font-medium">{server.capacity - server.used} GB</div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Letzte Sync:</span>
                      <div className="font-medium">{server.lastSync}</div>
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-sm mb-2">
                      <span>Speichernutzung</span>
                      <span>{getUsagePercentage(server.used, server.capacity)}%</span>
                    </div>
                    <Progress value={getUsagePercentage(server.used, server.capacity)} className="h-2" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="jobs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Backup Jobs</CardTitle>
              <CardDescription>Automatische Backup-Aufträge und deren Status</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job Name</TableHead>
                    <TableHead>Typ</TableHead>
                    <TableHead>Ziele</TableHead>
                    <TableHead>Zeitplan</TableHead>
                    <TableHead>Ziel</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Größe</TableHead>
                    <TableHead>Nächster Lauf</TableHead>
                    <TableHead>Aktionen</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {backupJobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell className="font-medium">{job.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{job.type}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="text-xs">
                          {job.targets.slice(0, 2).join(", ")}
                          {job.targets.length > 2 && ` +${job.targets.length - 2}`}
                        </div>
                      </TableCell>
                      <TableCell className="text-xs">{job.schedule}</TableCell>
                      <TableCell className="text-xs">{job.destination}</TableCell>
                      <TableCell>
                        <Badge variant={getStatusColor(job.status)}>{getStatusText(job.status)}</Badge>
                      </TableCell>
                      <TableCell>{job.size}</TableCell>
                      <TableCell className="text-xs">{job.nextRun}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                            <Play className="h-3 w-3" />
                          </Button>
                          <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                            <Settings className="h-3 w-3" />
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

        <TabsContent value="history" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Backup Verlauf</CardTitle>
              <CardDescription>Historie der durchgeführten Backups</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-muted-foreground">
                <Calendar className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Backup-Verlauf wird hier angezeigt</p>
                <p className="text-sm">Detaillierte Logs und Statistiken vergangener Backup-Läufe</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
