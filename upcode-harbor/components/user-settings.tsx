"use client"

import { useState, useEffect, useCallback } from "react"
import QRCode from "qrcode"
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
import {
  User, Shield, KeyRound, Eye, EyeOff, CheckCircle,
  AlertCircle, ShieldCheck, ShieldOff, Smartphone
} from "lucide-react"
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

type TwoFaView = "status" | "setup-qr" | "disable-confirm"

export function UserSettings({ open, onOpenChange }: UserSettingsProps) {
  const { username, groups, permissions } = useAuth()

  // -------------------------------------------------------------------------
  // Password change
  // -------------------------------------------------------------------------
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [pwLoading, setPwLoading] = useState(false)
  const [pwStatus, setPwStatus] = useState<StatusMessage | null>(null)

  // -------------------------------------------------------------------------
  // 2FA
  // -------------------------------------------------------------------------
  const [twoFaEnabled, setTwoFaEnabled] = useState(false)
  const [twoFaLoading, setTwoFaLoading] = useState(false)
  const [twoFaView, setTwoFaView] = useState<TwoFaView>("status")
  const [twoFaStatus, setTwoFaStatus] = useState<StatusMessage | null>(null)

  // Setup flow
  const [setupToken, setSetupToken] = useState("")
  const [setupQr, setSetupQr] = useState("")
  const [setupUri, setSetupUri] = useState("")
  const [setupCode, setSetupCode] = useState("")

  // Disable flow
  const [disablePassword, setDisablePassword] = useState("")
  const [disableCode, setDisableCode] = useState("")
  const [showDisablePassword, setShowDisablePassword] = useState(false)

  // -------------------------------------------------------------------------
  // Fetch 2FA status on open
  // -------------------------------------------------------------------------
  const fetchTwoFaStatus = useCallback(async () => {
    try {
      const res = await fetch(apiUrl("/auth/2fa/status"))
      if (res.ok) {
        const data = await res.json()
        setTwoFaEnabled(data.enabled)
      }
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    if (open) fetchTwoFaStatus()
  }, [open, fetchTwoFaStatus])

  // -------------------------------------------------------------------------
  // Reset on close
  // -------------------------------------------------------------------------
  const resetAll = () => {
    setCurrentPassword(""); setNewPassword(""); setConfirmPassword("")
    setShowCurrent(false); setShowNew(false); setShowConfirm(false)
    setPwStatus(null)
    setTwoFaView("status"); setTwoFaStatus(null)
    setSetupToken(""); setSetupQr(""); setSetupUri(""); setSetupCode("")
    setDisablePassword(""); setDisableCode(""); setShowDisablePassword(false)
  }

  const handleOpenChange = (v: boolean) => {
    if (!v) resetAll()
    onOpenChange(v)
  }

  // -------------------------------------------------------------------------
  // Password change
  // -------------------------------------------------------------------------
  const handleChangePassword = async () => {
    setPwStatus(null)
    if (!currentPassword || !newPassword || !confirmPassword) {
      setPwStatus({ type: "error", text: "Please fill in all fields." }); return
    }
    if (newPassword.length < 8) {
      setPwStatus({ type: "error", text: "New password must be at least 8 characters." }); return
    }
    if (newPassword !== confirmPassword) {
      setPwStatus({ type: "error", text: "New password and confirmation do not match." }); return
    }
    if (currentPassword === newPassword) {
      setPwStatus({ type: "error", text: "New password must differ from the current password." }); return
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
        setCurrentPassword(""); setNewPassword(""); setConfirmPassword("")
      } else {
        const data = await res.json().catch(() => ({}))
        const msg = data?.detail ?? "Failed to change password."
        setPwStatus({ type: "error", text:
          msg === "current password is incorrect" ? "Current password is incorrect." :
          msg === "new password must be at least 8 characters" ? "New password must be at least 8 characters." : msg
        })
      }
    } catch { setPwStatus({ type: "error", text: "Network error. Please try again." }) }
    finally { setPwLoading(false) }
  }

  // -------------------------------------------------------------------------
  // 2FA – begin setup
  // -------------------------------------------------------------------------
  const handleBeginSetup = async () => {
    setTwoFaStatus(null); setTwoFaLoading(true)
    try {
      const res = await fetch(apiUrl("/auth/2fa/setup"), { method: "POST" })
      if (res.ok) {
        const data = await res.json()
        setSetupToken(data.setup_token)
        setSetupUri(data.uri)
        const qr = await QRCode.toDataURL(data.uri, { width: 220, margin: 1 })
        setSetupQr(qr)
        setTwoFaView("setup-qr")
      } else {
        const d = await res.json().catch(() => ({}))
        setTwoFaStatus({ type: "error", text: d?.detail ?? "Failed to start 2FA setup." })
      }
    } catch { setTwoFaStatus({ type: "error", text: "Network error. Please try again." }) }
    finally { setTwoFaLoading(false) }
  }

  // -------------------------------------------------------------------------
  // 2FA – confirm setup
  // -------------------------------------------------------------------------
  const handleConfirmSetup = async () => {
    setTwoFaStatus(null)
    if (setupCode.length !== 6) {
      setTwoFaStatus({ type: "error", text: "Please enter the 6-digit code." }); return
    }
    setTwoFaLoading(true)
    try {
      const res = await fetch(apiUrl("/auth/2fa/verify-setup"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ setup_token: setupToken, code: setupCode }),
      })
      if (res.ok) {
        setTwoFaEnabled(true)
        setTwoFaView("status")
        setSetupCode(""); setSetupToken(""); setSetupQr(""); setSetupUri("")
        setTwoFaStatus({ type: "success", text: "Two-factor authentication is now enabled." })
      } else {
        const d = await res.json().catch(() => ({}))
        setTwoFaStatus({ type: "error", text: d?.detail === "invalid or expired code"
          ? "Invalid code. Check the time on your device and try again."
          : d?.detail ?? "Verification failed." })
        setSetupCode("")
      }
    } catch { setTwoFaStatus({ type: "error", text: "Network error. Please try again." }) }
    finally { setTwoFaLoading(false) }
  }

  // -------------------------------------------------------------------------
  // 2FA – disable
  // -------------------------------------------------------------------------
  const handleDisable = async () => {
    setTwoFaStatus(null)
    if (!disablePassword || disableCode.length !== 6) {
      setTwoFaStatus({ type: "error", text: "Please enter your password and the 6-digit code." }); return
    }
    setTwoFaLoading(true)
    try {
      const res = await fetch(apiUrl("/auth/2fa/disable"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: disablePassword, code: disableCode }),
      })
      if (res.ok) {
        setTwoFaEnabled(false)
        setTwoFaView("status")
        setDisablePassword(""); setDisableCode("")
        setTwoFaStatus({ type: "success", text: "Two-factor authentication has been disabled." })
      } else {
        const d = await res.json().catch(() => ({}))
        setTwoFaStatus({ type: "error", text:
          d?.detail === "password is incorrect" ? "Password is incorrect." :
          d?.detail === "invalid 2FA code" ? "Invalid 2FA code. Please try again." :
          d?.detail ?? "Failed to disable 2FA." })
        setDisableCode("")
      }
    } catch { setTwoFaStatus({ type: "error", text: "Network error. Please try again." }) }
    finally { setTwoFaLoading(false) }
  }

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------
  const permissionLabels: Record<string, string> = {
    admin: "Administrator", containers: "Containers", vms: "Virtual Machines",
    storage: "Storage", shell: "Shell", logs: "Logs",
  }
  const activePermissions = Object.entries(permissions).filter(([, v]) => v).map(([k]) => k)

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

  const StatusAlert = ({ status }: { status: StatusMessage }) => (
    <div className={`flex items-start gap-2 rounded-md px-3 py-2 text-sm ${
      status.type === "success"
        ? "bg-green-500/10 text-green-600 dark:text-green-400"
        : "bg-destructive/10 text-destructive"
    }`}>
      {status.type === "success"
        ? <CheckCircle className="h-4 w-4 mt-0.5 shrink-0" />
        : <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />}
      {status.text}
    </div>
  )

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
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
              <User className="h-3.5 w-3.5" />Profile
            </TabsTrigger>
            <TabsTrigger value="security" className="flex-1 flex items-center gap-1.5">
              <Shield className="h-3.5 w-3.5" />Security
            </TabsTrigger>
          </TabsList>

          {/* ---------------------------------------------------------------- */}
          {/* PROFILE TAB                                                       */}
          {/* ---------------------------------------------------------------- */}
          <TabsContent value="profile" className="mt-4 space-y-5">
            <div className="flex items-center gap-4">
              <div className="flex items-center justify-center w-16 h-16 rounded-full bg-primary/20 shrink-0">
                <User className="h-8 w-8 text-primary" />
              </div>
              <div>
                <p className="text-lg font-semibold">{username}</p>
                <p className="text-sm text-muted-foreground">Linux system user</p>
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Groups</Label>
              <div className="flex flex-wrap gap-1.5">
                {groups.length > 0
                  ? groups.map((g) => <Badge key={g} variant="secondary" className="font-mono text-xs">{g}</Badge>)
                  : <span className="text-sm text-muted-foreground">No groups</span>}
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Permissions</Label>
              <div className="flex flex-wrap gap-1.5">
                {activePermissions.length > 0
                  ? activePermissions.map((p) => (
                    <Badge key={p} className="text-xs bg-primary/20 text-primary hover:bg-primary/30">
                      {permissionLabels[p] ?? p}
                    </Badge>
                  ))
                  : <span className="text-sm text-muted-foreground">Restricted access</span>}
              </div>
            </div>
          </TabsContent>

          {/* ---------------------------------------------------------------- */}
          {/* SECURITY TAB                                                      */}
          {/* ---------------------------------------------------------------- */}
          <TabsContent value="security" className="mt-4 space-y-6">

            {/* ---- Change Password ---- */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-muted-foreground" />
                <h3 className="text-sm font-semibold">Change Password</h3>
              </div>

              <div className="space-y-2">
                <Label htmlFor="current-password">Current Password</Label>
                <div className="relative">
                  <Input id="current-password" type={showCurrent ? "text" : "password"}
                    value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Current password" className="pr-9" autoComplete="current-password" />
                  <button type="button" tabIndex={-1} onClick={() => setShowCurrent(!showCurrent)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="new-password">New Password</Label>
                <div className="relative">
                  <Input id="new-password" type={showNew ? "text" : "password"}
                    value={newPassword} onChange={(e) => { setNewPassword(e.target.value); setPwStatus(null) }}
                    placeholder="New password (min. 8 characters)" className="pr-9" autoComplete="new-password" />
                  <button type="button" tabIndex={-1} onClick={() => setShowNew(!showNew)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
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
                  <Input id="confirm-password" type={showConfirm ? "text" : "password"}
                    value={confirmPassword} onChange={(e) => { setConfirmPassword(e.target.value); setPwStatus(null) }}
                    placeholder="Repeat new password" className="pr-9" autoComplete="new-password" />
                  <button type="button" tabIndex={-1} onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {pwStatus && <StatusAlert status={pwStatus} />}
              <Button onClick={handleChangePassword} disabled={pwLoading} className="w-full">
                {pwLoading ? "Changing..." : "Change Password"}
              </Button>
            </div>

            <div className="h-px bg-border" />

            {/* ---- 2FA Section ---- */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                {twoFaEnabled
                  ? <ShieldCheck className="h-4 w-4 text-green-500" />
                  : <ShieldOff className="h-4 w-4 text-muted-foreground" />}
                <h3 className="text-sm font-semibold">Two-Factor Authentication</h3>
                <Badge
                  className={`ml-auto text-xs ${twoFaEnabled ? "bg-green-500/20 text-green-600 dark:text-green-400 hover:bg-green-500/30 border-green-500/30" : ""}`}
                  variant={twoFaEnabled ? "outline" : "secondary"}
                >
                  {twoFaEnabled ? "Enabled" : "Disabled"}
                </Badge>
              </div>

              {/* -- Status view -- */}
              {twoFaView === "status" && (
                <div className="space-y-3">
                  {twoFaStatus && <StatusAlert status={twoFaStatus} />}
                  {twoFaEnabled ? (
                    <>
                      <p className="text-xs text-muted-foreground">
                        Your account is protected with TOTP two-factor authentication.
                        You will need your authenticator app on every login.
                      </p>
                      <Button variant="destructive" className="w-full"
                        onClick={() => { setTwoFaView("disable-confirm"); setTwoFaStatus(null) }}>
                        <ShieldOff className="h-4 w-4 mr-2" />Disable 2FA
                      </Button>
                    </>
                  ) : (
                    <>
                      <p className="text-xs text-muted-foreground">
                        Add an extra layer of security. You will need an authenticator app
                        such as Google Authenticator, Authy, or Bitwarden.
                      </p>
                      <Button className="w-full" disabled={twoFaLoading} onClick={handleBeginSetup}>
                        <ShieldCheck className="h-4 w-4 mr-2" />
                        {twoFaLoading ? "Setting up..." : "Enable 2FA"}
                      </Button>
                    </>
                  )}
                </div>
              )}

              {/* -- Setup: scan QR and confirm -- */}
              {twoFaView === "setup-qr" && (
                <div className="space-y-4">
                  <div className="space-y-1">
                    <p className="text-xs font-medium">Step 1 – Scan this QR code with your authenticator app</p>
                    <p className="text-xs text-muted-foreground">
                      Compatible with Google Authenticator, Authy, Bitwarden, and any TOTP app.
                    </p>
                  </div>

                  {setupQr && (
                    <div className="flex justify-center">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={setupQr} alt="2FA QR Code"
                        className="rounded-lg border border-border p-2 bg-white"
                        width={220} height={220} />
                    </div>
                  )}

                  <details className="text-xs">
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground select-none">
                      Can&apos;t scan? Enter the key manually
                    </summary>
                    <p className="mt-1 font-mono break-all text-foreground bg-muted rounded px-2 py-1 select-all">
                      {setupUri}
                    </p>
                  </details>

                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5">
                      <Smartphone className="h-3.5 w-3.5 text-muted-foreground" />
                      <Label className="text-xs font-medium">Step 2 – Enter the 6-digit code to confirm</Label>
                    </div>
                    <Input type="text" inputMode="numeric" maxLength={6}
                      value={setupCode}
                      onChange={(e) => { setSetupCode(e.target.value.replace(/\D/g, "").slice(0, 6)); setTwoFaStatus(null) }}
                      placeholder="000000"
                      className="text-center tracking-[0.4em] font-mono text-lg"
                      autoComplete="one-time-code" />
                  </div>

                  {twoFaStatus && <StatusAlert status={twoFaStatus} />}

                  <div className="flex gap-2">
                    <Button variant="outline" className="flex-1"
                      onClick={() => { setTwoFaView("status"); setTwoFaStatus(null); setSetupCode("") }}>
                      Cancel
                    </Button>
                    <Button className="flex-1" disabled={twoFaLoading || setupCode.length !== 6}
                      onClick={handleConfirmSetup}>
                      {twoFaLoading ? "Verifying..." : "Confirm & Enable"}
                    </Button>
                  </div>
                </div>
              )}

              {/* -- Disable confirmation -- */}
              {twoFaView === "disable-confirm" && (
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground">
                    To disable 2FA, confirm your account password and enter a valid
                    code from your authenticator app.
                  </p>

                  <div className="space-y-2">
                    <Label htmlFor="disable-password">Password</Label>
                    <div className="relative">
                      <Input id="disable-password"
                        type={showDisablePassword ? "text" : "password"}
                        value={disablePassword}
                        onChange={(e) => { setDisablePassword(e.target.value); setTwoFaStatus(null) }}
                        placeholder="Your current password" className="pr-9" autoComplete="current-password" />
                      <button type="button" tabIndex={-1} onClick={() => setShowDisablePassword(!showDisablePassword)}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                        {showDisablePassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="disable-code">Authenticator Code</Label>
                    <Input id="disable-code" type="text" inputMode="numeric" maxLength={6}
                      value={disableCode}
                      onChange={(e) => { setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6)); setTwoFaStatus(null) }}
                      placeholder="000000"
                      className="text-center tracking-[0.4em] font-mono text-lg"
                      autoComplete="one-time-code" />
                  </div>

                  {twoFaStatus && <StatusAlert status={twoFaStatus} />}

                  <div className="flex gap-2">
                    <Button variant="outline" className="flex-1"
                      onClick={() => { setTwoFaView("status"); setTwoFaStatus(null); setDisablePassword(""); setDisableCode("") }}>
                      Cancel
                    </Button>
                    <Button variant="destructive" className="flex-1"
                      disabled={twoFaLoading || !disablePassword || disableCode.length !== 6}
                      onClick={handleDisable}>
                      {twoFaLoading ? "Disabling..." : "Disable 2FA"}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
