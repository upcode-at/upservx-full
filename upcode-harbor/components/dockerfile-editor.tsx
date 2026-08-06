"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiUrl } from "@/lib/api"

export function DockerfileEditor() {
  const [image, setImage] = useState("")
  const [tag, setTag] = useState("latest")
  const [dockerfile, setDockerfile] = useState<string>("FROM alpine:3.18\nCMD [\"/bin/sh\"]")
  const [contextFile, setContextFile] = useState<File | null>(null)
  const [building, setBuilding] = useState(false)
  const [logs, setLogs] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleBuild = async () => {
    setError(null)
    setLogs(null)

    if (!image) {
      setError("Image name is required")
      return
    }

      setBuilding(true);
      try {
        const fd = new FormData();
        if (dockerfile) {
          const blob = new Blob([dockerfile], { type: "text/plain" });
          fd.append("dockerfile", blob, "Dockerfile");
        }
        if (contextFile) {
          fd.append("context", contextFile);
        }

        const url = apiUrl(`/containers/build/stream?image=${encodeURIComponent(image)}&tag=${encodeURIComponent(tag)}`);

        const res = await fetch(url, { method: "POST", body: fd, credentials: 'include' });
        if (!res.body) {
          const txt = await res.text();
          setLogs(txt || `Build failed with status ${res.status}`);
        } else {
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let finished = false;
          while (!finished) {
            const { value, done } = await reader.read();
            if (value) {
              const chunk = decoder.decode(value, { stream: true });
              setLogs((prev) => prev + chunk);
            }
            finished = !!done;
          }
          if (!res.ok) {
            setLogs((prev) => prev + `\n[HTTP ${res.status}]`);
          }
        }
      } catch (err: unknown) {
        setLogs((prev) => prev + "\nERROR: " + String(err));
      } finally {
        setBuilding(false);
      }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2 items-end">
        <div>
          <Label htmlFor="image">Image name</Label>
          <Input id="image" value={image} onChange={e => setImage((e.target as HTMLInputElement).value)} placeholder="myimage" />
        </div>
        <div>
          <Label htmlFor="tag">Tag</Label>
          <Input id="tag" value={tag} onChange={e => setTag((e.target as HTMLInputElement).value)} placeholder="latest" />
        </div>
        <div>
          <Label htmlFor="context">Context (optional)</Label>
          <input id="context" type="file" accept=".tar,.tar.gz,.tgz" onChange={e => setContextFile(e.target.files?.[0] || null)} />
        </div>
      </div>

      <div>
        <Label htmlFor="dockerfile">Dockerfile</Label>
        <textarea
          id="dockerfile"
          className="w-full h-64 border rounded p-2 font-mono text-sm"
          value={dockerfile}
          onChange={e => setDockerfile(e.target.value)}
        />
      </div>

      <div className="flex items-center gap-2">
        <Button onClick={handleBuild} disabled={building}>{building ? "Building..." : "Build Image"}</Button>
        <Button variant="outline" onClick={() => { setDockerfile("FROM alpine:3.18\nCMD [\"/bin/sh\"]") }}>Reset</Button>
      </div>

      {error && (
        <div className="text-red-600 bg-red-50 p-2 rounded">
          {error}
        </div>
      )}

      {logs && (
        <div>
          <Label>Build logs</Label>
          <pre className="bg-black text-white p-2 rounded overflow-auto max-h-64">{logs}</pre>
        </div>
      )}
    </div>
  )
}

export default DockerfileEditor
