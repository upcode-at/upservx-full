"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { User, Shield, KeyRound, Eye, EyeOff, CheckCircle, AlertCircle } from "lucide-react"
import { apiUrl } from "@/lib/api"
import { useAuth } from "@/components/auth-provider"

interface UserSettingsProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface StatusMessage {
  type: "success" | "error"
  text: string
}

export function UserSettings({ open, onOpenChange }: UserSettingsProps) {
  const { username, groups, permissions } = useAuth()

  // Password change state
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [pwLoading, setPwLoading] = useState(false)
  const [pwStatus, setPwStatus] = useState<StatusMessage | null>(null)

  const resetPasswordForm = () => {
    setCurrentPassword("")
    setNewPassword("")
    setConfirmPassword("")
    setShowCurrent(false)
    setShowNew(false)
    setShowConfirm(false)
    setPwStatus(null)
  }

  const handleOpenChange = (v: boolean) => {
    if (!v) resetPasswordForm()
    onOpenChange(v)
  }

  const handleChangePassword = async () => {
    setPwStatus(null)

    if (!currentPassword || !newPassword || !confirmPassword) {
      setPwStatus({ type: "error", text: "Please fill in all fields." })
      return
    }
    if (newPassword.length < 8) {
      setPwStatus({ type: "error", text: "New password must be at least 8 characters." })
      return
    }
    if (newPassword !== confirmPassword) {
      setPwStatus({ type: "error", text: "New password and confirmation do not match." })
      return
    }
    if (currentPassword === newPassword) {
      setPwStatus({ type: "error", text: "New password must differ from the current password." })
      return
    }

    setPwLoading(true)
    try {
      const res = await fetch(apiUrl("/auth/change-password"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      })
      if (res.ok) {
        setPwStatus({ type: "success", text: "Password changed successfully." })
        setCurrentPassword("")
        setNewPassword("")
        setConfirmPassword("")
      } else {
        const data = await res.json().catch(() => ({}))
        const msg = data?.detail ?? "Failed to change password."
        const friendly =
          msg === "current password is incorrect"
            ? "Current password is incorrect."
            : msg === "new password must be at least 8 characters"
            ? "New password must be at least 8 characters."
            : msg
        setPwStatus({ type: "error", text: friendly })
      }
    } catch {
      setPwStatus({ type: "error", text: "Network error. Please try again." })
    } finally {
      setPwLoading(false)
    }
  }

  const permissionLabels: Record<string, string> = {
    admin: "Administrator",
    containers: "Container",
    vms: "Virtual Machines",
    storage: "Storage",
    shell: "Shell",
    logs: "Logs",
  }

  const activePermissions = Object.entries(permissions)
    .filter(([, v]) => v)
    .map(([k]) => k)

  const passwordStrength = (() => {
    if (!newPassword) return null
    let score = 0
    if (newPassword.length >= 8) score++
    if (newPassword.length >= 12) score++
    if (/[A-Z]/.test(newPassword)) score++
    if (/[0-9]/.test(newPassword)) score++
    if (/[^a-zA-Z0-9]/.test(newPassword)) score++
    if (score <= 1) return { label: "Weak", color: "bg-red-500", width: "w-1/5" }
    if (score === 2) return { label: "Fair", color: "bg-orange-500", width: "w-2/5" }
    if (score === 3) return { label: "Good", color: "bg-yellow-500", width: "w-3/5" }
    if (score === 4) return { label: "Strong", color: "bg-green-400", width: "w-4/5" }
    return { label: "Very strong", color: "bg-green-500", width: "w-full" }
  })()

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            User Settings
          </DialogTitle>
          <DialogDescription>
            Account settings for <span className="font-semibold text-foreground">{username}</span>
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="profile" className="mt-2">
          <TabsList className="w-full">
            <TabsTrigger value="profile" className="flex-1 flex items-center gap-1.5">
              <User className="h-3.5 w-3.5" />
              Profile
            </TabsTrigger>
            <TabsTrigger value="security" className="flex-1 flex items-center gap-1.5">
              <Shield className="h-3.5 w-3.5" />
              Security
            </TabsTrigger>
          </TabsList>

          {/* ---- PROFILE TAB ---- */}
          <TabsContent value="profile" className="mt-4 space-y-5">
            {/* Avatar */}
            <div className="flex items-center gap-4">
              <div className="flex items-center justify-center w-16 h-16 rounded-full bg-primary/20 shrink-0">
                <User className="h-8 w-8 text-primary" />
              </div>
              <div>
                <p className="text-lg font-semibold">{username}</p>
                <p className="text-sm text-muted-foreground">Linux system user</p>
              </div>
            </div>

            {/* Groups */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Groups</Label>
              <div className="flex flex-wrap gap-1.5">
                {groups.length > 0 ? (
                  groups.map((g) => (
                    <Badge key={g} variant="secondary" className="font-mono text-xs">
                      {g}
                    </Badge>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">No groups</span>
                )}
              </div>
            </div>

            {/* Permissions */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Permissions</Label>
              <div className="flex flex-wrap gap-1.5">
                {activePermissions.length > 0 ? (
                  activePermissions.map((p) => (
                    <Badge key={p} className="text-xs bg-primary/20 text-primary hover:bg-primary/30">
                      {permissionLabels[p] ?? p}
                    </Badge>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">Restricted access</span>
                )}
              </div>
            </div>
          </TabsContent>

          {/* ---- SECURITY TAB ---- */}
          <TabsContent value="security" className="mt-4 space-y-5">
            {/* Password Change */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-muted-foreground" />
                <h3 className="text-sm font-semibold">Change Password</h3>
              </div>

              <div className="space-y-2">
                <Label htmlFor="current-password">Current Password</Label>
                <div className="relative">
                  <Input
                    id="current-password"
                    type={showCurrent ? "text" : "password"}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Current password"
                    className="pr-9"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrent(!showCurrent)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    tabIndex={-1}
                  >
                    {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="new-password">New Password</Label>
                <div className="relative">
                  <Input
                    id="new-password"
                    type={showNew ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => { setNewPassword(e.target.value); setPwStatus(null) }}
                    placeholder="New password (min. 8 characters)"
                    className="pr-9"
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNew(!showNew)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    tabIndex={-1}
                  >
                    {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {/* Password strength bar */}
                {passwordStrength && (
                  <div className="space-y-0.5">
                    <div className="h-1 w-full rounded-full bg-muted overflow-hidden">
                      <div className={`h-full rounded-full transition-all duration-300 ${passwordStrength.color} ${passwordStrength.width}`} />
                    </div>
                    <p className="text-xs text-muted-foreground">{passwordStrength.label}</p>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirm-password">Confirm Password</Label>
                <div className="relative">
                  <Input
                    id="confirm-password"
                    type={showConfirm ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => { setConfirmPassword(e.target.value); setPwStatus(null) }}
                    placeholder="Repeat new password"
                    className="pr-9"
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    tabIndex={-1}
                  >
                    {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* Status message */}
              {pwStatus && (
                <div
                  className={`flex items-start gap-2 rounded-md px-3 py-2 text-sm ${
                    pwStatus.type === "success"
                      ? "bg-green-500/10 text-green-600 dark:text-green-400"
                      : "bg-destructive/10 text-destructive"
                  }`}
                >
                  {pwStatus.type === "success" ? (
                    <CheckCircle className="h-4 w-4 mt-0.5 shrink-0" />
                  ) : (
                    <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                  )}
                  {pwStatus.text}
                </div>
              )}

              <Button
                onClick={handleChangePassword}
                disabled={pwLoading}
                className="w-full"
              >
                {pwLoading ? "Changing..." : "Change Password"}
              </Button>
            </div>

            {/* 2FA Placeholder */}
            <div className="border border-dashed border-muted-foreground/30 rounded-lg p-4 space-y-2 opacity-60">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-muted-foreground" />
                <h3 className="text-sm font-semibold text-muted-foreground">Two-Factor Authentication</h3>
                <Badge variant="secondary" className="text-xs ml-auto">Coming soon</Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                TOTP-based 2FA with authenticator app support is coming soon.
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
