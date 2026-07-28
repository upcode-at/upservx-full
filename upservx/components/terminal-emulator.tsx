"use client"

import { useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { X } from "lucide-react"
import { apiUrl, wsUrl } from "@/lib/api"
import { Terminal } from "@xterm/xterm"
import { FitAddon } from "@xterm/addon-fit"
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
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: "#1e1e1e",
        foreground: "#d4d4d4",
        cursor: "#d4d4d4",
        cursorAccent: "#1e1e1e",
        selectionBackground: "rgba(255, 255, 255, 0.3)",
      },
    })
    const fitAddon = new FitAddon()

    term.loadAddon(fitAddon)
    termRef.current = term

    if (containerRef.current) {
      term.open(containerRef.current)
      fitAddon.fit()
      term.focus()
    }

    const sendTerminalSize = () => {
      const ws = wsRef.current
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "resize",
          cols: term.cols,
          rows: term.rows,
        }))
      }
    }

    const resizeObserver = new ResizeObserver(() => {
      fitAddon.fit()
    })

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current)
    }

    const resizeDisposable = term.onResize(sendTerminalSize)

    fetch(apiUrl("/auth/ws-ticket"), { credentials: "include" })
      .then(r => r.json())
      .then(({ ticket }) => {
        const ws = new WebSocket(wsUrl(`/containers/${containerName}/terminal`) + `?token=${encodeURIComponent(ticket)}`)
        wsRef.current = ws
        ws.onopen = () => {
          fitAddon.fit()
          sendTerminalSize()
        }
        ws.onmessage = (ev) => {
          const text = (typeof ev.data === "string" ? ev.data : "").replace(/\n/g, "\r\n")
          term.write(text)
        }
        ws.onclose = () => {
          term.write("\r\n[Connection closed]")
        }
        ws.onerror = () => {
          term.write("\r\n[Connection failed]")
        }
        term.onData((data) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(data)
          }
        })
      })
      .catch(() => {
        term.write("[Authentication failed - please sign in again]")
      })

    return () => {
      const ws = wsRef.current
      if (ws && ws.readyState === WebSocket.OPEN) ws.close()
      resizeObserver.disconnect()
      resizeDisposable.dispose()
      term.dispose()
    }
  }, [containerName])

  return (
    <Card className="h-[98vh] min-h-0 w-[98vw] max-w-[98vw] gap-0 py-0">
      <CardHeader className="shrink-0 flex flex-row items-center justify-between space-y-0 border-b px-4 py-3">
        <CardTitle className="text-sm font-medium">Terminal - {containerName}</CardTitle>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
          <X className="h-3 w-3" />
        </Button>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-hidden p-0">
        <div className="h-full w-full bg-[#1e1e1e] p-4" ref={containerRef}></div>
      </CardContent>
    </Card>
  )
}
