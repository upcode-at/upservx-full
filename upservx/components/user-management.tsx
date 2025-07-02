"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Switch } from "@/components/ui/switch"
import { User, Users, Shield, Plus, Settings, Key } from "lucide-react"

export function UserManagement() {
  const [users] = useState([
    {
      username: "root",
      uid: 0,
      gid: 0,
      groups: ["root"],
      shell: "/bin/bash",
      home: "/root",
      status: "active",
      lastLogin: "2024-01-15 14:30",
      permissions: ["sudo", "admin", "docker"],
      description: "System Administrator",
    },
    {
      username: "admin",
      uid: 1000,
      gid: 1000,
      groups: ["admin", "sudo", "docker"],
      shell: "/bin/bash",
      home: "/home/admin",
      status: "active",
      lastLogin: "2024-01-15 16:45",
      permissions: ["sudo", "docker", "lxc"],
      description: "Server Administrator",
    },
    {
      username: "operator",
      uid: 1001,
      gid: 1001,
      groups: ["operator", "docker"],
      shell: "/bin/bash",
      home: "/home/operator",
      status: "active",
      lastLogin: "2024-01-14 09:15",
      permissions: ["docker"],
      description: "System Operator",
    },
    {
      username: "backup",
      uid: 1002,
      gid: 1002,
      groups: ["backup"],
      shell: "/bin/false",
      home: "/var/backups",
      status: "service",
      lastLogin: "Never",
      permissions: ["backup"],
      description: "Backup Service Account",
    },
    {
      username: "www-data",
      uid: 33,
      gid: 33,
      groups: ["www-data"],
      shell: "/usr/sbin/nologin",
      home: "/var/www",
      status: "service",
      lastLogin: "Never",
      permissions: ["web"],
      description: "Web Server Service Account",
    },
  ])

  const [groups] = useState([
    {
      name: "root",
      gid: 0,
      members: ["root"],
      description: "Root group",
      permissions: ["all"],
    },
    {
      name: "admin",
      gid: 1000,
      members: ["admin"],
      description: "System administrators",
      permissions: ["sudo", "admin", "docker", "lxc"],
    },
    {
      name: "sudo",
      gid: 27,
      members: ["admin", "root"],
      description: "Sudo access group",
      permissions: ["sudo"],
    },
    {
      name: "docker",
      gid: 999,
      members: ["admin", "operator"],
      description: "Docker access group",
      permissions: ["docker"],
    },
    {
      name: "operator",
      gid: 1001,
      members: ["operator"],
      description: "System operators",
      permissions: ["monitoring", "logs"],
    },
  ])

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "default"
      case "inactive":
        return "secondary"
      case "service":
        return "outline"
      case "locked":
        return "destructive"
      default:
        return "secondary"
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case "active":
        return "Aktiv"
      case "inactive":
        return "Inaktiv"
      case "service":
        return "Service"
      case "locked":
        return "Gesperrt"
      default:
        return status
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Benutzer Management</h2>
          <p className="text-muted-foreground">Systembenutzer, Gruppen und Berechtigungen verwalten</p>
        </div>
        <Dialog>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Neuen Benutzer erstellen
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Neuen Benutzer erstellen</DialogTitle>
              <DialogDescription>Erstellen Sie einen neuen Systembenutzer</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="username">Benutzername</Label>
                  <Input id="username" placeholder="z.B. newuser" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="fullname">Vollständiger Name</Label>
                  <Input id="fullname" placeholder="z.B. Max Mustermann" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="password">Passwort</Label>
                  <Input id="password" type="password" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm-password">Passwort bestätigen</Label>
                  <Input id="confirm-password" type="password" />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="groups">Gruppen</Label>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="Gruppen auswählen" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="users">users</SelectItem>
                    <SelectItem value="operator">operator</SelectItem>
                    <SelectItem value="docker">docker</SelectItem>
                    <SelectItem value="sudo">sudo</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center space-x-2">
                <Switch id="sudo-access" />
                <Label htmlFor="sudo-access">Sudo-Berechtigung gewähren</Label>
              </div>
              <div className="flex justify-end space-x-2">
                <Button variant="outline">Abbrechen</Button>
                <Button>Benutzer erstellen</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <Tabs defaultValue="users" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="users">Benutzer</TabsTrigger>
          <TabsTrigger value="groups">Gruppen</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Systembenutzer</CardTitle>
              <CardDescription>Alle Benutzerkonten auf dem System</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Benutzer</TableHead>
                    <TableHead>UID</TableHead>
                    <TableHead>Gruppen</TableHead>
                    <TableHead>Shell</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Letzter Login</TableHead>
                    <TableHead>Berechtigungen</TableHead>
                    <TableHead>Aktionen</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow key={user.username}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4" />
                          <div>
                            <div className="font-medium">{user.username}</div>
                            <div className="text-xs text-muted-foreground">{user.description}</div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono">{user.uid}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {user.groups.map((group) => (
                            <Badge key={group} variant="outline" className="text-xs">
                              {group}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{user.shell}</TableCell>
                      <TableCell>
                        <Badge variant={getStatusColor(user.status)}>{getStatusText(user.status)}</Badge>
                      </TableCell>
                      <TableCell className="text-xs">{user.lastLogin}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {user.permissions.map((perm) => (
                            <Badge key={perm} variant="secondary" className="text-xs">
                              {perm}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                            <Settings className="h-3 w-3" />
                          </Button>
                          <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                            <Key className="h-3 w-3" />
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

        <TabsContent value="groups" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Benutzergruppen</CardTitle>
              <CardDescription>Systemgruppen und deren Mitglieder</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Gruppe</TableHead>
                    <TableHead>GID</TableHead>
                    <TableHead>Mitglieder</TableHead>
                    <TableHead>Berechtigungen</TableHead>
                    <TableHead>Beschreibung</TableHead>
                    <TableHead>Aktionen</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {groups.map((group) => (
                    <TableRow key={group.name}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Users className="h-4 w-4" />
                          <span className="font-medium">{group.name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono">{group.gid}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {group.members.map((member) => (
                            <Badge key={member} variant="outline" className="text-xs">
                              {member}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {group.permissions.map((perm) => (
                            <Badge key={perm} variant="secondary" className="text-xs">
                              <Shield className="h-3 w-3 mr-1" />
                              {perm}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">{group.description}</TableCell>
                      <TableCell>
                        <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                          <Settings className="h-3 w-3" />
                        </Button>
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
