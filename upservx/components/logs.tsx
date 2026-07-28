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
  }, [selected])

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
    <Card className="h-full min-h-0 gap-0 rounded-none py-0">
      <CardHeader className="shrink-0 flex flex-col gap-3 border-b px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle>Logs</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">View system log files</p>
        </div>
        <div className="w-full sm:w-64">
          <Select value={selected} onValueChange={setSelected}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Log File" />
            </SelectTrigger>
            <SelectContent>
              {logs.map((log) => (
                <SelectItem key={log.name} value={log.name}>
                  {log.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="min-h-0 flex-1 overflow-hidden p-0">
        <ScrollArea className="h-full w-full bg-muted/30">
          <pre className="min-w-full whitespace-pre-wrap break-words p-4 font-mono text-sm">{content}</pre>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
