"use client"

import type React from "react"

import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { X, Maximize2, Minimize2 } from "lucide-react"

interface TerminalEmulatorProps {
  containerName: string
  onClose: () => void
}

export function TerminalEmulator({ containerName, onClose }: TerminalEmulatorProps) {
  const [command, setCommand] = useState("")
  const [history, setHistory] = useState<Array<{ type: "command" | "output" | "error"; content: string }>>([
    { type: "output", content: `root@${containerName}:~$ ` },
  ])
  const [isMaximized, setIsMaximized] = useState(false)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    // Auto-scroll to bottom when new content is added
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
    }
  }, [history])

  useEffect(() => {
    // Focus input when component mounts
    if (inputRef.current) {
      inputRef.current.focus()
    }
  }, [])

  const executeCommand = (cmd: string) => {
    if (!cmd.trim()) {
      setHistory((prev) => [...prev, { type: "output", content: `root@${containerName}:~$ ` }])
      setCommand("")
      return
    }

    // Add command to history
    setHistory((prev) => [...prev, { type: "command", content: `root@${containerName}:~$ ${cmd}` }])

    // Simulate command execution
    setTimeout(
      () => {
        let output = ""
        let type: "output" | "error" = "output"

        switch (cmd.toLowerCase().trim()) {
          case "help":
            output = `Available commands:
ls          - List directory contents
pwd         - Print working directory
ps          - Show running processes
top         - Display system processes
df          - Show disk usage
free        - Display memory usage
uname -a    - System information
whoami      - Current user
date        - Current date and time
clear       - Clear terminal
exit        - Close terminal`
            break
          case "ls":
            output = "bin  boot  dev  etc  home  lib  media  mnt  opt  proc  root  run  sbin  srv  sys  tmp  usr  var"
            break
          case "pwd":
            output = "/root"
            break
          case "ps":
            output = `  PID TTY          TIME CMD
    1 ?        00:00:01 systemd
   12 ?        00:00:00 kthreadd
   13 ?        00:00:00 ksoftirqd/0
   14 ?        00:00:00 migration/0
   15 ?        00:00:00 rcu_gp`
            break
          case "whoami":
            output = "root"
            break
          case "date":
            output = new Date().toString()
            break
          case "uname -a":
            output =
              "Linux container 5.15.0-91-generic #101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux"
            break
          case "df":
            output = `Filesystem     1K-blocks    Used Available Use% Mounted on
/dev/sda1       20971520 8388608  12582912  40% /
tmpfs            1048576       0   1048576   0% /dev/shm
tmpfs            1048576    8192   1040384   1% /run`
            break
          case "free":
            output = `              total        used        free      shared  buff/cache   available
Mem:        2097152      524288     1048576       16384      524288     1572864
Swap:             0           0           0`
            break
          case "top":
            output = `top - 14:30:25 up 5 days,  7:42,  1 user,  load average: 0.15, 0.10, 0.05
Tasks:  45 total,   1 running,  44 sleeping,   0 stopped,   0 zombie
%Cpu(s):  2.3 us,  1.2 sy,  0.0 ni, 96.5 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
MiB Mem :   2048.0 total,   1024.0 free,    512.0 used,    512.0 buff/cache
MiB Swap:      0.0 total,      0.0 free,      0.0 used.   1536.0 avail Mem`
            break
          case "clear":
            setHistory([{ type: "output", content: `root@${containerName}:~$ ` }])
            setCommand("")
            return
          case "exit":
            onClose()
            return
          default:
            output = `bash: ${cmd}: command not found`
            type = "error"
        }

        setHistory((prev) => [
          ...prev,
          { type, content: output },
          { type: "output", content: `root@${containerName}:~$ ` },
        ])
      },
      100 + Math.random() * 200,
    ) // Simulate network delay

    setCommand("")
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      executeCommand(command)
    }
  }

  return (
    <Card className={`${isMaximized ? "fixed inset-4 z-50" : "w-full max-w-4xl"} bg-background border`}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 border-b">
        <CardTitle className="text-sm font-medium">Terminal - {containerName}</CardTitle>
        <div className="flex items-center space-x-2">
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setIsMaximized(!isMaximized)}>
            {isMaximized ? <Minimize2 className="h-3 w-3" /> : <Maximize2 className="h-3 w-3" />}
          </Button>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
            <X className="h-3 w-3" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-96 p-4 bg-background" ref={scrollAreaRef}>
          <div className="space-y-1 font-mono text-sm">
            {history.map((entry, index) => {
              if (entry.type === "command") {
                return (
                  <div key={index} className="text-foreground">
                    {entry.content}
                  </div>
                )
              } else if (entry.type === "error") {
                return (
                  <div key={index} className="text-red-500 whitespace-pre-wrap">
                    {entry.content}
                  </div>
                )
              } else {
                // Output type
                if (entry.content.includes("root@")) {
                  // This is a prompt
                  return (
                    <div key={index} className="flex items-center">
                      <span className="text-green-600 font-medium">root@{containerName}</span>
                      <span className="text-foreground">:</span>
                      <span className="text-blue-600 font-medium">~</span>
                      <span className="text-foreground">$ </span>
                      {index === history.length - 1 && (
                        <Input
                          ref={inputRef}
                          value={command}
                          onChange={(e) => setCommand(e.target.value)}
                          onKeyPress={handleKeyPress}
                          className="flex-1 bg-transparent border-none text-foreground focus:ring-0 focus:ring-offset-0 p-0 h-auto font-mono text-sm shadow-none"
                          placeholder=""
                          autoFocus
                        />
                      )}
                    </div>
                  )
                } else {
                  return (
                    <div key={index} className="text-foreground whitespace-pre-wrap">
                      {entry.content}
                    </div>
                  )
                }
              }
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
