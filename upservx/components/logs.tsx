"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { apiUrl } from "@/lib/api"

interface LogFile {
  name: string
  size: number
}

export function Logs() {
  const [logs, setLogs] = useState<LogFile[]>([])
  const [selected, setSelected] = useState("")
  const [content, setContent] = useState("")

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(apiUrl("/logs"))
        if (res.ok) {
          const data = await res.json()
          setLogs(data.logs || [])
          if (!selected && data.logs?.length) setSelected(data.logs[0].name)
        }
      } catch (e) {
        console.error(e)
      }
    }
    load()
  }, [])

  useEffect(() => {
    if (!selected) return
    const load = async () => {
      try {
        const res = await fetch(apiUrl(`/logs/${encodeURIComponent(selected)}?lines=200`))
        if (res.ok) {
          const text = await res.text()
          setContent(text)
        }
      } catch (e) {
        console.error(e)
      }
    }
    load()
  }, [selected])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Logs</h2>
        <p className="text-muted-foreground">System log files anzeigen</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Log Datei wählen</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Select value={selected} onValueChange={setSelected}>
            <SelectTrigger className="w-64">
              <SelectValue placeholder="Log Datei" />
            </SelectTrigger>
            <SelectContent>
              {logs.map((log) => (
                <SelectItem key={log.name} value={log.name}>
                  {log.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <ScrollArea className="h-96 rounded-md border p-4 bg-muted text-sm whitespace-pre-wrap font-mono">
            {content}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}
