"use client"

import { useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { X } from "lucide-react"
import { wsUrl } from "@/lib/api"
import { Terminal } from "@xterm/xterm"
import "@xterm/xterm/css/xterm.css"

interface TerminalEmulatorProps {
  containerName: string
  onClose: () => void
}

export function TerminalEmulator({ containerName, onClose }: TerminalEmulatorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<Terminal | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const term = new Terminal()
    termRef.current = term
    if (containerRef.current) {
      term.open(containerRef.current)
      term.focus()
    }

    const ws = new WebSocket(wsUrl(`/containers/${containerName}/terminal`))
    wsRef.current = ws
    ws.onmessage = (ev) => {
      const text = (typeof ev.data === "string" ? ev.data : "").replace(/\n/g, "\r\n")
      term.write(text)
    }
    ws.onclose = () => {
      term.write("\r\n[Verbindung beendet]")
    }

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data)
      }
    })

    return () => {
      ws.close()
      term.dispose()
    }
  }, [containerName])

  return (
    <Card className="w-full max-w-5xl h-[80vh] flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 border-b">
        <CardTitle className="text-sm font-medium">Terminal - {containerName}</CardTitle>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
          <X className="h-3 w-3" />
        </Button>
      </CardHeader>
      <CardContent className="flex-1 p-0 overflow-hidden">
        <div className="h-full w-full bg-black text-white" ref={containerRef}></div>
      </CardContent>
    </Card>
  )
}
