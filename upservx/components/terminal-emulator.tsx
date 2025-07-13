"use client"

import { useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { X } from "lucide-react"
import { wsUrl } from "@/lib/api"

interface TerminalEmulatorProps {
  containerName: string
  onClose: () => void
}

export function TerminalEmulator({ containerName, onClose }: TerminalEmulatorProps) {
  const [command, setCommand] = useState("")
  const [history, setHistory] = useState<string[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const [closed, setClosed] = useState(false)

  useEffect(() => {
    setClosed(false)
    const ws = new WebSocket(wsUrl(`/containers/${containerName}/terminal`))
    wsRef.current = ws
    ws.onmessage = (ev) => {
      setHistory((prev) => [...prev, ev.data])
    }
    ws.onclose = () => setClosed(true)
    return () => {
      ws.close()
    }
  }, [containerName])

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }
  }, [history])

  const sendCommand = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    wsRef.current.send(command)
    setHistory((prev) => [...prev, `$ ${command}`])
    setCommand("")
  }

  return (
    <Card className="w-full max-w-3xl">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 border-b">
        <CardTitle className="text-sm font-medium">Terminal - {containerName}</CardTitle>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
          <X className="h-3 w-3" />
        </Button>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-96 p-4 bg-background" ref={scrollAreaRef}>
          <div className="space-y-1 font-mono text-sm whitespace-pre-wrap">
            {history.map((line, idx) => (
              <div key={idx}>{line}</div>
            ))}
          </div>
        </ScrollArea>
        {!closed ? (
          <div className="flex border-t p-2 space-x-2">
            <Input
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  sendCommand()
                }
              }}
            />
            <Button onClick={sendCommand}>Senden</Button>
          </div>
        ) : (
          <div className="flex border-t p-2 text-sm text-muted-foreground">
            Verbindung beendet
          </div>
        )}
      </CardContent>
    </Card>
  )
}
