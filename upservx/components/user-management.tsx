"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { User, Users, Plus, Settings, Key } from "lucide-react"

interface SysUser {
  username: string
  uid: number
  gid: number
  groups: string[]
  shell: string
  home: string
  description?: string
}

interface SysGroup {
  name: string
  gid: number
  members: string[]
  description?: string
}

export function UserManagement() {
  const [users, setUsers] = useState<SysUser[]>([])
  const [groups, setGroups] = useState<SysGroup[]>([])
  const [userTotal, setUserTotal] = useState(0)
  const [groupTotal, setGroupTotal] = useState(0)
  const [userPageSize, setUserPageSize] = useState(10)
  const [groupPageSize, setGroupPageSize] = useState(10)
  const [userPage, setUserPage] = useState(1)
  const [groupPage, setGroupPage] = useState(1)
  const loadUsers = async (page = userPage, size = userPageSize) => {
    try {
      const params = new URLSearchParams({
        limit: size.toString(),
        offset: ((page - 1) * size).toString(),
      })
      const res = await fetch(`http://localhost:8000/users?${params}`)
      if (res.ok) {
        const data = await res.json()
        setUsers(data.users || [])
        setUserTotal(data.total || 0)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const loadGroups = async (page = groupPage, size = groupPageSize) => {
    try {
      const params = new URLSearchParams({
        limit: size.toString(),
        offset: ((page - 1) * size).toString(),
      })
      const res = await fetch(`http://localhost:8000/groups?${params}`)
      if (res.ok) {
        const data = await res.json()
        setGroups(data.groups || [])
        setGroupTotal(data.total || 0)
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    loadUsers()
  }, [userPage, userPageSize])

  useEffect(() => {
    loadGroups()
  }, [groupPage, groupPageSize])

  const [newUser, setNewUser] = useState({
    username: "",
    password: "",
    shell: "/bin/bash",
    groups: "",
  })

  const handleCreateUser = async () => {
    try {
      const res = await fetch("http://localhost:8000/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: newUser.username,
          password: newUser.password,
          shell: newUser.shell,
          groups: newUser.groups.split(",").map((g) => g.trim()).filter(Boolean),
        }),
      })
      if (res.ok) {
        const data = await res.json()
        console.log(data)
        setNewUser({ username: "", password: "", shell: "/bin/bash", groups: "" })
        loadUsers()
      }
    } catch (e) {
      console.error(e)
    }
  }

  const [newGroup, setNewGroup] = useState({ name: "", members: "" })

  const handleCreateGroup = async () => {
    try {
      const res = await fetch("http://localhost:8000/groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newGroup.name,
          members: newGroup.members.split(",").map((m) => m.trim()).filter(Boolean),
        }),
      })
      if (res.ok) {
        setNewGroup({ name: "", members: "" })
        loadGroups()
      }
    } catch (e) {
      console.error(e)
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
                  <Input
                    id="username"
                    value={newUser.username}
                    onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Passwort</Label>
                  <Input
                    id="password"
                    type="password"
                    value={newUser.password}
                    onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="shell">Shell</Label>
                <Input
                  id="shell"
                  value={newUser.shell}
                  onChange={(e) => setNewUser({ ...newUser, shell: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="groups">Gruppen (kommagetrennt)</Label>
                <Input
                  id="groups"
                  value={newUser.groups}
                  onChange={(e) => setNewUser({ ...newUser, groups: e.target.value })}
                />
              </div>
              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => setNewUser({ username: "", password: "", shell: "/bin/bash", groups: "" })}>
                  Abbrechen
                </Button>
                <Button onClick={handleCreateUser}>Benutzer erstellen</Button>
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
              <div className="flex items-center justify-between mt-2">
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={userPage === 1}
                    onClick={() => setUserPage(userPage - 1)}
                  >
                    Zurück
                  </Button>
                  <span className="text-sm">
                    Seite {userPage} / {Math.max(1, Math.ceil(userTotal / userPageSize))}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={userPage >= Math.ceil(userTotal / userPageSize)}
                    onClick={() => setUserPage(userPage + 1)}
                  >
                    Weiter
                  </Button>
                </div>
                <Select
                  value={String(userPageSize)}
                  onValueChange={(v) => {
                    setUserPageSize(Number(v))
                    setUserPage(1)
                  }}
                >
                  <SelectTrigger className="w-20 h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="10">10</SelectItem>
                    <SelectItem value="20">20</SelectItem>
                    <SelectItem value="50">50</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="groups" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Benutzergruppen</CardTitle>
                <CardDescription>Systemgruppen und deren Mitglieder</CardDescription>
              </div>
              <Dialog>
                <DialogTrigger asChild>
                  <Button size="sm" variant="outline">
                    <Plus className="h-4 w-4 mr-1" /> Gruppe erstellen
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-sm">
                  <DialogHeader>
                    <DialogTitle>Neue Gruppe erstellen</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="group-name">Name</Label>
                      <Input
                        id="group-name"
                        value={newGroup.name}
                        onChange={(e) => setNewGroup({ ...newGroup, name: e.target.value })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="group-members">Mitglieder (kommagetrennt)</Label>
                      <Input
                        id="group-members"
                        value={newGroup.members}
                        onChange={(e) => setNewGroup({ ...newGroup, members: e.target.value })}
                      />
                    </div>
                    <div className="flex justify-end space-x-2">
                      <Button variant="outline" onClick={() => setNewGroup({ name: "", members: "" })}>
                        Abbrechen
                      </Button>
                      <Button onClick={handleCreateGroup}>Gruppe erstellen</Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Gruppe</TableHead>
                    <TableHead>GID</TableHead>
                    <TableHead>Mitglieder</TableHead>
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
                        <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                          <Settings className="h-3 w-3" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="flex items-center justify-between mt-2">
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={groupPage === 1}
                    onClick={() => setGroupPage(groupPage - 1)}
                  >
                    Zurück
                  </Button>
                  <span className="text-sm">
                    Seite {groupPage} / {Math.max(1, Math.ceil(groupTotal / groupPageSize))}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={groupPage >= Math.ceil(groupTotal / groupPageSize)}
                    onClick={() => setGroupPage(groupPage + 1)}
                  >
                    Weiter
                  </Button>
                </div>
                <Select
                  value={String(groupPageSize)}
                  onValueChange={(v) => {
                    setGroupPageSize(Number(v))
                    setGroupPage(1)
                  }}
                >
                  <SelectTrigger className="w-20 h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="10">10</SelectItem>
                    <SelectItem value="20">20</SelectItem>
                    <SelectItem value="50">50</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
