"use client"

import { useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Terminal as TerminalIcon } from "lucide-react"
import { wsUrl } from "@/lib/api"
import { Terminal } from "@xterm/xterm"
import "@xterm/xterm/css/xterm.css"

export function SystemShell() {
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<Terminal | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#d4d4d4',
        cursorAccent: '#1e1e1e',
        selectionBackground: 'rgba(255, 255, 255, 0.3)',
      },
    })
    
    termRef.current = term
    
    if (containerRef.current) {
      term.open(containerRef.current)
      term.focus()
    }

    const ws = new WebSocket(wsUrl(`/system/shell`))
    wsRef.current = ws
    
    ws.onopen = () => {
      term.write('Connected to system shell\r\n')
    }
    
    ws.onmessage = (ev) => {
      const text = (typeof ev.data === "string" ? ev.data : "").replace(/\n/g, "\r\n")
      term.write(text)
    }
    
    ws.onclose = () => {
      term.write("\r\n[Connection closed]")
    }
    
    ws.onerror = () => {
      term.write("\r\n[Connection error]")
    }

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data)
      }
    })

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
      term.dispose()
    }
  }, [])

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TerminalIcon className="h-5 w-5" />
          System Shell
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div 
          ref={containerRef} 
          className="h-[calc(100vh-12rem)] w-full"
          style={{ padding: '1rem' }}
        />
      </CardContent>
    </Card>
  )
}
