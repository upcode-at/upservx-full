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
  const inputRef = useRef<string>("")

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

    term.onKey(({ key, domEvent }) => {
      domEvent.preventDefault()
      if (domEvent.key === "Enter") {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(inputRef.current)
        }
        inputRef.current = ""
        term.write("\r\n")
      } else if (domEvent.key === "Backspace") {
        if (inputRef.current.length > 0) {
          inputRef.current = inputRef.current.slice(0, -1)
          term.write("\b \b")
        }
      } else if (domEvent.key.length === 1) {
        inputRef.current += key
        term.write(key)
      }
    })

    return () => {
      ws.close()
      term.dispose()
    }
  }, [containerName])

  return (
    <Card className="w-full max-w-3xl">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 border-b">
        <CardTitle className="text-sm font-medium">Terminal - {containerName}</CardTitle>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
          <X className="h-3 w-3" />
        </Button>
      </CardHeader>
      <CardContent className="p-0">
        <div className="h-96 bg-black text-white" ref={containerRef}></div>
      </CardContent>
    </Card>
  )
}
