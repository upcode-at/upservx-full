"use client"

import { useCallback, useEffect, useState } from "react"
import { Download, Play, Square } from "lucide-react"

import { apiUrl } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { NotificationContainer } from "@/components/ui/notification"

interface VpnStatus {
  running: boolean
  pid?: number | null
  ovpn_path?: string | null
}

export function VpnManagement() {
  const [vpnStatus, setVpnStatus] = useState<VpnStatus | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadVpnStatus = useCallback(async () => {
    try {
      const response = await fetch(apiUrl("/settings/vpn/status"))
      if (response.ok) {
        setVpnStatus(await response.json())
      } else {
        setError("Failed to load VPN status")
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load VPN status")
    }
  }, [])

  useEffect(() => {
    loadVpnStatus()
  }, [loadVpnStatus])

  const uploadVpn = async (file: File | null) => {
    if (!file) return

    try {
      setError(null)
      setSuccess(null)
      const formData = new FormData()
      formData.append("file", file)
      const response = await fetch(apiUrl("/settings/vpn/upload"), {
        method: "POST",
        body: formData,
      })
      if (!response.ok) {
        const detail = await response.text()
        setError(`Upload failed: ${detail}`)
        return
      }
      setSuccess("VPN configuration uploaded successfully")
      await loadVpnStatus()
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Failed to upload VPN configuration")
    }
  }

  const setVpnRunning = async (running: boolean) => {
    const action = running ? "start" : "stop"
    try {
      setError(null)
      setSuccess(null)
      const response = await fetch(apiUrl(`/settings/vpn/${action}`), { method: "POST" })
      if (!response.ok) {
        setError(`Failed to ${action} VPN`)
        return
      }
      setSuccess(`VPN ${running ? "started" : "stopped"} successfully`)
      await loadVpnStatus()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : `Failed to ${action} VPN`)
    }
  }

  return (
    <div className="space-y-6">
      <NotificationContainer
        success={success}
        error={error}
        onClearSuccess={() => setSuccess(null)}
        onClearError={() => setError(null)}
      />

      <Card>
        <CardHeader>
          <CardTitle>OpenVPN</CardTitle>
          <CardDescription>Upload and control an OpenVPN client profile</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="ovpn-file">OVPN File</Label>
            <div className="flex flex-wrap items-center gap-2">
              <input
                id="ovpn-file"
                type="file"
                accept=".ovpn"
                onChange={(event) => uploadVpn(event.target.files?.[0] ?? null)}
                className="rounded"
              />
              <Button
                variant="outline"
                onClick={() => { window.location.href = apiUrl("/settings/vpn/file") }}
                disabled={!vpnStatus?.ovpn_path}
              >
                <Download className="mr-2 h-4 w-4" />
                Download
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div>Status: {vpnStatus ? (vpnStatus.running ? "Running" : "Stopped") : "Unknown"}</div>
            {vpnStatus?.ovpn_path && (
              <div className="text-muted-foreground">{vpnStatus.ovpn_path.split("/").pop()}</div>
            )}
          </div>

          <div className="flex gap-2">
            <Button onClick={() => setVpnRunning(true)} disabled={vpnStatus?.running === true}>
              <Play className="mr-2 h-4 w-4" />
              Start VPN
            </Button>
            <Button
              variant="destructive"
              onClick={() => setVpnRunning(false)}
              disabled={vpnStatus?.running !== true}
            >
              <Square className="mr-2 h-4 w-4" />
              Stop VPN
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
