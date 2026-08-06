"use client"

import { useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Terminal as TerminalIcon } from "lucide-react"
import { apiUrl, wsUrl } from "@/lib/api"
import { Terminal } from "@xterm/xterm"
import { FitAddon } from "@xterm/addon-fit"
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

    // Fetch a one-time WS ticket via the normal HTTP session (cookie is sent
    // reliably on HTTP requests), then pass it as ?token= in the WS URL
    // because browsers don't include cross-origin cookies on WS upgrades.
    fetch(apiUrl("/auth/ws-ticket"), { credentials: "include" })
      .then(r => r.json())
      .then(({ ticket }) => {
        const ws = new WebSocket(wsUrl(`/system/shell`) + `?token=${encodeURIComponent(ticket)}`)
        wsRef.current = ws

        ws.onopen = () => {
          fitAddon.fit()
          sendTerminalSize()
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
      })
      .catch(() => {
        term.write("\r\n[Failed to obtain session token — are you logged in?]")
      })

    return () => {
      const ws = wsRef.current
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
      resizeObserver.disconnect()
      resizeDisposable.dispose()
      term.dispose()
    }
  }, [])

  return (
    <Card className="h-full min-h-0 gap-0 rounded-none py-0">
      <CardHeader className="shrink-0 border-b px-4 py-3">
        <CardTitle className="flex items-center gap-2">
          <TerminalIcon className="h-5 w-5" />
          System Shell
        </CardTitle>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-hidden p-0">
        <div
          ref={containerRef}
          className="h-full w-full bg-[#1e1e1e] p-4"
        />
      </CardContent>
    </Card>
  )
}
