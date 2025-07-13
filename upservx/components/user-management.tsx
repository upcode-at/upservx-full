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
import { apiUrl } from "@/lib/api"

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
  const [allGroups, setAllGroups] = useState<SysGroup[]>([])
  const [allUsers, setAllUsers] = useState<SysUser[]>([])
  const [newUserGroups, setNewUserGroups] = useState<string[]>([])
  const [newGroupMembers, setNewGroupMembers] = useState<string[]>([])
  const [editUser, setEditUser] = useState<SysUser | null>(null)
  const [editGroup, setEditGroup] = useState<SysGroup | null>(null)
  const [keyUser, setKeyUser] = useState<SysUser | null>(null)
  const [userKeys, setUserKeys] = useState<string[]>([])
  const [createUserOpen, setCreateUserOpen] = useState(false)
  const [createGroupOpen, setCreateGroupOpen] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const loadUsers = async (page = userPage, size = userPageSize) => {
    try {
      const params = new URLSearchParams({
        limit: size.toString(),
        offset: ((page - 1) * size).toString(),
      })
      const res = await fetch(apiUrl(`/users?${params}`))
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
      const res = await fetch(apiUrl(`/groups?${params}`))
      if (res.ok) {
        const data = await res.json()
        setGroups(data.groups || [])
        setGroupTotal(data.total || 0)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const loadAllGroups = async () => {
    try {
      const res = await fetch(apiUrl("/groups?limit=1000"))
      if (res.ok) {
        const data = await res.json()
        setAllGroups(data.groups || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const loadAllUsers = async () => {
    try {
      const res = await fetch(apiUrl("/users?limit=1000"))
      if (res.ok) {
        const data = await res.json()
        setAllUsers(data.users || [])
      }
    } catch (e) {
      console.error(e)
    }
  }

  const loadUserKeys = async (user: SysUser) => {
    try {
      const res = await fetch(apiUrl(`/users/${user.username}/keys`))
      if (res.ok) {
        const data = await res.json()
        setUserKeys(data.keys || [])
      } else {
        setUserKeys([])
      }
    } catch (e) {
      console.error(e)
      setUserKeys([])
    }
  }

  useEffect(() => {
    loadUsers()
  }, [userPage, userPageSize])

  useEffect(() => {
    loadGroups()
  }, [groupPage, groupPageSize])

  useEffect(() => {
    loadAllGroups()
    loadAllUsers()
  }, [])

  useEffect(() => {
    if (!message && !error) return
    const t = setTimeout(() => {
      setMessage(null)
      setError(null)
    }, 3000)
    return () => clearTimeout(t)
  }, [message, error])

  const [newUser, setNewUser] = useState({
    username: "",
    password: "",
    shell: "/bin/bash",
  })

  const handleCreateUser = async () => {
    try {
      const res = await fetch(apiUrl("/users"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: newUser.username,
          password: newUser.password,
          shell: newUser.shell,
          groups: newUserGroups.filter(Boolean),
        }),
      })
      if (res.ok) {
        setMessage("User created")
        setNewUser({ username: "", password: "", shell: "/bin/bash" })
        setNewUserGroups([])
        setCreateUserOpen(false)
        loadUsers()
        loadAllUsers()
      } else {
        let msg = "Error creating"
        try {
          const data = await res.json()
          msg = data.detail || msg
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

  const [newGroup, setNewGroup] = useState({ name: "" })

  const handleCreateGroup = async () => {
    try {
      const res = await fetch(apiUrl("/groups"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newGroup.name,
          members: newGroupMembers.filter(Boolean),
        }),
      })
      if (res.ok) {
        setMessage("Group created")
        setNewGroup({ name: "" })
        setNewGroupMembers([])
        setCreateGroupOpen(false)
        loadGroups()
        loadAllGroups()
        loadAllUsers()
      } else {
        let msg = "Error creating"
        try {
          const data = await res.json()
          msg = data.detail || msg
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

  const handleSaveKeys = async () => {
    if (!keyUser) return
    try {
      const res = await fetch(apiUrl(`/users/${keyUser.username}/keys`), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keys: userKeys.filter((k) => k.trim() !== "") }),
      })
      if (res.ok) {
        setMessage("SSH keys saved")
        setKeyUser(null)
      } else {
        let msg = "Error saving"
        try {
          const data = await res.json()
          msg = data.detail || msg
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
          <h2 className="text-3xl font-bold tracking-tight">User Management</h2>
          <p className="text-muted-foreground">Manage system users, groups and permissions</p>
        </div>
        <Dialog open={createUserOpen} onOpenChange={setCreateUserOpen}>
          <DialogTrigger asChild>
            <Button onClick={() => setCreateUserOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create New User
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Create New User</DialogTitle>
              <DialogDescription>Create a new system user</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    value={newUser.username}
                    onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
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
                <Label>Groups</Label>
                {newUserGroups.map((g, idx) => (
                  <div key={idx} className="flex space-x-2">
                    <select
                      className="border rounded-md px-2 py-1 flex-1 bg-transparent"
                      value={g}
                      onChange={(e) => {
                        const arr = [...newUserGroups]
                        arr[idx] = e.target.value
                        setNewUserGroups(arr)
                      }}
                    >
                      <option value="">--</option>
                      {allGroups.map((gr) => (
                        <option key={gr.name} value={gr.name}>
                          {gr.name}
                        </option>
                      ))}
                    </select>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setNewUserGroups(newUserGroups.filter((_, i) => i !== idx))}
                    >
                      -
                    </Button>
                  </div>
                ))}
                <Button variant="outline" size="sm" onClick={() => setNewUserGroups([...newUserGroups, ""]) }>
                  Add group
                </Button>
              </div>
              <div className="flex justify-end space-x-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setNewUser({ username: "", password: "", shell: "/bin/bash" })
                    setNewUserGroups([])
                    setCreateUserOpen(false)
                  }}
                >
                  Cancel
                </Button>
              <Button onClick={handleCreateUser}>Create User</Button>
              </div>
            </div>
        </DialogContent>
      </Dialog>

      <Dialog open={!!editUser} onOpenChange={(o) => !o && setEditUser(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
          </DialogHeader>
          {editUser && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Shell</Label>
                <Input
                  value={editUser.shell}
                  onChange={(e) => setEditUser({ ...editUser, shell: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Groups</Label>
                {editUser.groups.map((g, idx) => (
                  <div key={idx} className="flex space-x-2">
                    <select
                      className="border rounded-md px-2 py-1 flex-1 bg-transparent"
                      value={g}
                      onChange={(e) => {
                        const arr = [...editUser.groups]
                        arr[idx] = e.target.value
                        setEditUser({ ...editUser, groups: arr })
                      }}
                    >
                      <option value="">--</option>
                      {allGroups.map((gr) => (
                        <option key={gr.name} value={gr.name}>
                          {gr.name}
                        </option>
                      ))}
                    </select>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() =>
                        setEditUser({ ...editUser, groups: editUser.groups.filter((_, i) => i !== idx) })
                      }
                    >
                      -
                    </Button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditUser({ ...editUser, groups: [...editUser.groups, ""] })}
                >
                  Add group
                </Button>
              </div>
              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => setEditUser(null)}>
                  Cancel
                </Button>
                <Button
                  onClick={async () => {
                    const res = await fetch(apiUrl(`/users/${editUser.username}`), {
                      method: "PUT",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ shell: editUser.shell, groups: editUser.groups.filter(Boolean) }),
                    })
                    if (res.ok) {
                      setMessage("User saved")
                      setEditUser(null)
                      loadUsers()
                      loadAllGroups()
                    } else {
                      let msg = "Error saving"
                      try {
                        const data = await res.json()
                        msg = data.detail || msg
                      } catch {
                        msg = await res.text()
                      }
                      setError(msg)
                    }
                  }}
                >
                  Speichern
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!keyUser} onOpenChange={(o) => !o && setKeyUser(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>SSH Keys verwalten</DialogTitle>
          </DialogHeader>
          {keyUser && (
            <div className="space-y-4">
              <div className="space-y-2">
                {userKeys.map((k, idx) => (
                  <div key={idx} className="flex space-x-2 items-start">
                    <textarea
                      className="border rounded-md p-2 flex-1 bg-transparent text-sm"
                      rows={2}
                      value={k}
                      onChange={(e) => {
                        const arr = [...userKeys]
                        arr[idx] = e.target.value
                        setUserKeys(arr)
                      }}
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setUserKeys(userKeys.filter((_, i) => i !== idx))}
                    >
                      -
                    </Button>
                  </div>
                ))}
                {userKeys.length < 3 && (
                  <Button variant="outline" size="sm" onClick={() => setUserKeys([...userKeys, ""]) }>
                    Add key
                  </Button>
                )}
              </div>
              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => setKeyUser(null)}>
                  Cancel
                </Button>
                <Button onClick={handleSaveKeys}>Save</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
      </div>

      <Tabs defaultValue="users" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="groups">Groups</TabsTrigger>
        </TabsList>

        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>System Users</CardTitle>
              <CardDescription>All user accounts on the system</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>UID</TableHead>
                    <TableHead>Groups</TableHead>
                    <TableHead>Shell</TableHead>
                    <TableHead>Actions</TableHead>
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
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-8 w-8 bg-transparent"
                            onClick={() => setEditUser(user)}
                          >
                            <Settings className="h-3 w-3" />
                          </Button>
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-8 w-8 bg-transparent"
                            onClick={() => {
                              setKeyUser(user)
                              loadUserKeys(user)
                            }}
                          >
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
                    Back
                  </Button>
                  <span className="text-sm">
                    Page {userPage} / {Math.max(1, Math.ceil(userTotal / userPageSize))}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={userPage >= Math.ceil(userTotal / userPageSize)}
                    onClick={() => setUserPage(userPage + 1)}
                  >
                    Next
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
                <CardTitle>User Groups</CardTitle>
                <CardDescription>System groups and their members</CardDescription>
              </div>
              <Dialog open={createGroupOpen} onOpenChange={setCreateGroupOpen}>
                <DialogTrigger asChild>
                  <Button size="sm" variant="outline" onClick={() => setCreateGroupOpen(true)}>
                    <Plus className="h-4 w-4 mr-1" /> Create Group
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-sm">
                  <DialogHeader>
                    <DialogTitle>Create New Group</DialogTitle>
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
                      <Label>Members</Label>
                      {newGroupMembers.map((m, idx) => (
                        <div key={idx} className="flex space-x-2">
                          <select
                            className="border rounded-md px-2 py-1 flex-1 bg-transparent"
                            value={m}
                            onChange={(e) => {
                              const arr = [...newGroupMembers]
                              arr[idx] = e.target.value
                              setNewGroupMembers(arr)
                            }}
                          >
                            <option value="">--</option>
                            {allUsers.map((u) => (
                              <option key={u.username} value={u.username}>
                                {u.username}
                              </option>
                            ))}
                          </select>
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => setNewGroupMembers(newGroupMembers.filter((_, i) => i !== idx))}
                          >
                            -
                          </Button>
                        </div>
                      ))}
                      <Button variant="outline" size="sm" onClick={() => setNewGroupMembers([...newGroupMembers, ""]) }>
                        Add member
                      </Button>
                    </div>
                    <div className="flex justify-end space-x-2">
                      <Button
                        variant="outline"
                        onClick={() => {
                          setNewGroup({ name: "" })
                          setNewGroupMembers([])
                          setCreateGroupOpen(false)
                        }}
                      >
                        Cancel
                      </Button>
                      <Button onClick={handleCreateGroup}>Create Group</Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>

              <Dialog open={!!editGroup} onOpenChange={(o) => !o && setEditGroup(null)}>
                <DialogContent className="max-w-sm">
                  <DialogHeader>
                    <DialogTitle>Edit Group</DialogTitle>
                  </DialogHeader>
                  {editGroup && (
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <Label>Members</Label>
                        {editGroup.members.map((m, idx) => (
                          <div key={idx} className="flex space-x-2">
                            <select
                              className="border rounded-md px-2 py-1 flex-1 bg-transparent"
                              value={m}
                              onChange={(e) => {
                                const arr = [...editGroup.members]
                                arr[idx] = e.target.value
                                setEditGroup({ ...editGroup, members: arr })
                              }}
                            >
                              <option value="">--</option>
                              {allUsers.map((u) => (
                                <option key={u.username} value={u.username}>
                                  {u.username}
                                </option>
                              ))}
                            </select>
                            <Button
                              variant="outline"
                              size="icon"
                              onClick={() =>
                                setEditGroup({
                                  ...editGroup,
                                  members: editGroup.members.filter((_, i) => i !== idx),
                                })
                              }
                            >
                              -
                            </Button>
                          </div>
                        ))}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setEditGroup({ ...editGroup, members: [...editGroup.members, ""] })}
                        >
                          Add member
                        </Button>
                      </div>
                      <div className="flex justify-end space-x-2">
                        <Button variant="outline" onClick={() => setEditGroup(null)}>
                          Cancel
                        </Button>
                        <Button
                          onClick={async () => {
                            const res = await fetch(apiUrl(`/groups/${editGroup.name}`), {
                              method: "PUT",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ members: editGroup.members.filter(Boolean) }),
                            })
                            if (res.ok) {
                              setMessage("Group saved")
                              setEditGroup(null)
                              loadGroups()
                              loadAllUsers()
                            } else {
                              let msg = "Error saving"
                              try {
                                const data = await res.json()
                                msg = data.detail || msg
                              } catch {
                                msg = await res.text()
                              }
                              setError(msg)
                            }
                          }}
                        >
                          Save
                        </Button>
                      </div>
                    </div>
                  )}
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Group</TableHead>
                    <TableHead>GID</TableHead>
                    <TableHead>Members</TableHead>
                    <TableHead>Actions</TableHead>
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
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-8 w-8 bg-transparent"
                          onClick={() => setEditGroup(group)}
                        >
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
                    Back
                  </Button>
                  <span className="text-sm">
                    Page {groupPage} / {Math.max(1, Math.ceil(groupTotal / groupPageSize))}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={groupPage >= Math.ceil(groupTotal / groupPageSize)}
                    onClick={() => setGroupPage(groupPage + 1)}
                  >
                    Next
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
