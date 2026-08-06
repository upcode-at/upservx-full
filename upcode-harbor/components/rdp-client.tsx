"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { X, Maximize2, Minimize2, Monitor, Settings } from "lucide-react"

interface RDPClientProps {
  vmName: string
  vmIP: string
  onClose: () => void
}

export function RDPClient({ vmName, vmIP, onClose }: RDPClientProps) {
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [isMaximized, setIsMaximized] = useState(false)
  const [credentials, setCredentials] = useState({
    username: "",
    password: "",
    domain: "",
  })

  const handleConnect = async () => {
    setIsConnecting(true)
    setTimeout(() => {
      setIsConnected(true)
      setIsConnecting(false)
    }, 2000)
  }

  const handleDisconnect = () => {
    setIsConnected(false)
  }

  if (!isConnected) {
    return (
      <Card className="w-full max-w-md mx-auto">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Monitor className="h-5 w-5" />
              RDP Connection - {vmName}
            </CardTitle>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Server</Label>
            <Input value={vmIP} disabled />
          </div>
          <div className="space-y-2">
            <Label htmlFor="username">Benutzername</Label>
            <Input
              id="username"
              value={credentials.username}
              onChange={(e) => setCredentials((prev) => ({ ...prev, username: e.target.value }))}
              placeholder="Administrator"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={credentials.password}
              onChange={(e) => setCredentials((prev) => ({ ...prev, password: e.target.value }))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="domain">Domain (optional)</Label>
            <Input
              id="domain"
              value={credentials.domain}
              onChange={(e) => setCredentials((prev) => ({ ...prev, domain: e.target.value }))}
              placeholder="WORKGROUP"
            />
          </div>
          <div className="flex justify-end space-x-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={handleConnect} disabled={isConnecting || !credentials.username || !credentials.password}>
              {isConnecting ? "Connecting..." : "Connect"}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={`${isMaximized ? "fixed inset-4 z-50" : "w-full max-w-6xl"} bg-gray-900`}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center gap-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Monitor className="h-4 w-4" />
            RDP - {vmName} ({vmIP})
          </CardTitle>
          <Badge variant="default" className="bg-green-600">
            Connected
          </Badge>
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="ghost" size="icon" className="h-6 w-6">
            <Settings className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setIsMaximized(!isMaximized)}>
            {isMaximized ? <Minimize2 className="h-3 w-3" /> : <Maximize2 className="h-3 w-3" />}
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleDisconnect}>
            <X className="h-3 w-3" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="bg-blue-600 h-96 flex items-center justify-center relative overflow-hidden">
          {/* Simulated Windows Desktop */}
          <div className="absolute inset-0 bg-gradient-to-br from-blue-400 to-blue-800">
            {/* Taskbar */}
            <div className="absolute bottom-0 left-0 right-0 h-10 bg-gray-800 border-t border-gray-600 flex items-center px-2">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center">
                  <div className="w-4 h-4 bg-white rounded-sm"></div>
                </div>
                <div className="text-white text-sm">Start</div>
              </div>
              <div className="flex-1"></div>
              <div className="text-white text-sm">
                {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </div>
            </div>

            {/* Desktop Icons */}
            <div className="absolute top-4 left-4 space-y-4">
              <div className="flex flex-col items-center text-white text-xs">
                <div className="w-8 h-8 bg-yellow-500 rounded mb-1"></div>
                <span>This PC</span>
              </div>
              <div className="flex flex-col items-center text-white text-xs">
                <div className="w-8 h-8 bg-blue-500 rounded mb-1"></div>
                <span>Documents</span>
              </div>
              <div className="flex flex-col items-center text-white text-xs">
                <div className="w-8 h-8 bg-red-500 rounded mb-1"></div>
                <span>Recycle Bin</span>
              </div>
            </div>

            {/* Simulated Window */}
            <div className="absolute top-16 left-16 w-80 h-48 bg-white rounded-lg shadow-lg border">
              <div className="h-8 bg-gray-200 rounded-t-lg flex items-center px-3 border-b">
                <span className="text-sm font-medium">Notepad</span>
                <div className="flex-1"></div>
                <div className="flex space-x-1">
                  <div className="w-3 h-3 bg-yellow-400 rounded-full"></div>
                  <div className="w-3 h-3 bg-green-400 rounded-full"></div>
                  <div className="w-3 h-3 bg-red-400 rounded-full"></div>
                </div>
              </div>
              <div className="p-3 text-sm">
                <p>Upcode Harbor</p>
                <p>RDP connection active...</p>
              </div>
            </div>
          </div>

          <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-20">
            <div className="text-white text-center">
              <Monitor className="h-12 w-12 mx-auto mb-4 opacity-80" />
              <p className="text-lg font-medium">RDP connection active</p>
              <p className="text-sm opacity-80">Simulated Windows desktop environment</p>
              <p className="text-xs opacity-60 mt-2">
                In a real implementation, the remote desktop would be displayed here
              </p>
            </div>
          </div>
        </div>

        <div className="p-2 bg-gray-800 text-white text-xs flex justify-between items-center">
          <span>Resolution: 1920x1080 | Color depth: 32-bit</span>
          <div className="flex items-center space-x-4">
            <span>Latency: 15ms</span>
            <span>Bandwidth: 2.1 Mbps</span>
            <Button variant="outline" size="sm" onClick={handleDisconnect} className="h-6 text-xs bg-transparent">
              Disconnect
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
