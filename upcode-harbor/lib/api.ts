// Request models are generated from FastAPI's OpenAPI schema.
import type {
  BackupJobCreate,
  BackupJobUpdate,
  BackupRestoreRequest,
  BackupServerCreate,
  BackupServerUpdate,
  SSHKeyGenerateRequest,
  SSHKeyImportRequest,
  SSHKeyTestRequest,
} from './generated-api-types'

export function apiUrl(path: string): string {
  // ALWAYS check runtime location first (browser-side)
  if (typeof window !== "undefined") {
    const { protocol, hostname, port } = window.location
    
    // If accessing via standard ports (80/443), always use reverse proxy
    // This ensures HTTPS works correctly and avoids mixed content issues
    if (port === "" || port === "80" || port === "443") {
      return `/api${path}`
    }
    
    // Check if hostname is localhost or an IP address
    // These always use direct port access for development
    const isIP = /^(\d{1,3}\.){3}\d{1,3}$/.test(hostname)
    const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1"
    
    if (isIP || isLocalhost) {
      // Direct access for IPs and localhost (development)
      const apiPort = ":9500"
      return `${protocol}//${hostname}${apiPort}${path}`
    }
    
    // Domain names always use reverse proxy for consistency
    return `/api${path}`
  }
  
  // Fallback for SSR: use environment variable if set
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL
  if (apiBase) {
    return `${apiBase}${path}`
  }
  
  // Last resort fallback for SSR
  return ""
}

export interface PersistentJob<T = unknown> {
  id: string
  kind: string
  status: "queued" | "running" | "retry_wait" | "cancel_requested" | "completed" | "failed" | "cancelled"
  progress: number
  message?: string | null
  result?: T | null
  error?: string | null
}

export async function waitForJob<T = unknown>(
  jobId: string,
  onProgress?: (job: PersistentJob<T>) => void,
  timeoutMs = 4 * 60 * 60 * 1000,
  statusPath = `/jobs/${encodeURIComponent(jobId)}`,
): Promise<PersistentJob<T>> {
  const deadline = Date.now() + timeoutMs
  let lastError: Error | null = null

  while (Date.now() < deadline) {
    let job: PersistentJob<T> | null = null
    let fatalError: Error | null = null
    try {
      const response = await fetch(apiUrl(statusPath), {
        credentials: "include",
        headers: getAuthHeaders(),
      })
      if (response.ok) {
        job = await response.json() as PersistentJob<T>
        onProgress?.(job)
        lastError = null
      } else if (response.status === 401 || response.status === 403 || response.status === 404) {
        fatalError = new Error(`Unable to read job status (HTTP ${response.status})`)
      } else {
        lastError = new Error(`Job status returned HTTP ${response.status}`)
      }
    } catch (error) {
      lastError = error instanceof Error ? error : new Error("Unable to read job status")
    }
    if (job?.status === "completed") return job
    if (fatalError) throw fatalError
    if (job?.status === "failed" || job?.status === "cancelled") {
      throw new Error(job.error || job.message || `Job ${job.status}`)
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1500))
  }
  throw lastError || new Error("Timed out waiting for the job")
}

export function wsUrl(path: string): string {
  // ALWAYS check runtime location first (browser-side)
  if (typeof window !== "undefined") {
    const { protocol, hostname, port } = window.location
    const wsProtocol = protocol === "https:" ? "wss:" : "ws:"
    
    // If accessing via standard ports, always use reverse proxy
    if (port === "" || port === "80" || port === "443") {
      return `${wsProtocol}//${hostname}/ws${path}`
    }
    
    // Check if hostname is localhost or an IP address
    // These always use direct port access for development
    const isIP = /^(\d{1,3}\.){3}\d{1,3}$/.test(hostname)
    const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1"
    
    if (isIP || isLocalhost) {
      // Direct access for IPs and localhost (development)
      return `${wsProtocol}//${hostname}:9500${path}`
    }
    
    // Domain names always use reverse proxy for consistency
    return `${wsProtocol}//${hostname}/ws${path}`
  }
  
  // Fallback for SSR: use environment variable if set
  const wsBase = process.env.NEXT_PUBLIC_WS_BASE_URL
  if (wsBase) {
    return `${wsBase}${path}`
  }
  
  // Last resort fallback for SSR
  return `ws://localhost:9500${path}`
}

// Session auth is handled via HttpOnly cookie (credentials: include).
// Do not inject Authorization headers from browser storage, as stale
// values can override valid cookie sessions and trigger 401 responses.
export function getAuthHeaders(): HeadersInit {
  return {}
}

export function getJsonHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json'
  }
}

// API client for backup management
export const api = {
  // Backup Servers
  backupServers: {
    list: async () => {
      const response = await fetch(apiUrl("/backup/servers"), {
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    create: async (server: BackupServerCreate) => {
      const response = await fetch(apiUrl("/backup/servers"), {
        method: 'POST',
        credentials: 'include',
        headers: getJsonHeaders(),
        body: JSON.stringify(server)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    get: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/servers/${id}`), {
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    update: async (id: number, data: BackupServerUpdate) => {
      const response = await fetch(apiUrl(`/backup/servers/${id}`), {
        method: 'PUT',
        credentials: 'include',
        headers: getJsonHeaders(),
        body: JSON.stringify(data)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    delete: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/servers/${id}`), {
        method: 'DELETE',
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    test: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/servers/${id}/test`), {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    getInfo: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/servers/${id}/info`), {
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    }
  },
  
  // Backup Jobs
  backupJobs: {
    list: async () => {
      const response = await fetch(apiUrl("/backup/jobs"), {
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    create: async (job: BackupJobCreate) => {
      const response = await fetch(apiUrl("/backup/jobs"), {
        method: 'POST',
        credentials: 'include',
        headers: getJsonHeaders(),
        body: JSON.stringify(job)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    get: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/jobs/${id}`), {
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    update: async (id: number, data: BackupJobUpdate) => {
      const response = await fetch(apiUrl(`/backup/jobs/${id}`), {
        method: 'PUT',
        credentials: 'include',
        headers: getJsonHeaders(),
        body: JSON.stringify(data)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    delete: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/jobs/${id}`), {
        method: 'DELETE',
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    execute: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/jobs/${id}/execute`), {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    }
  },
  
  // Backup Instances
  backupInstances: {
    list: async (jobId?: number, serverId?: number) => {
      const params = new URLSearchParams()
      if (jobId) params.append('job_id', jobId.toString())
      if (serverId) params.append('server_id', serverId.toString())
      
      const url = params.toString() ? 
        `${apiUrl("/backup/instances")}?${params.toString()}` : 
        apiUrl("/backup/instances")
        
      const response = await fetch(url, {
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    get: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/instances/${id}`), {
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    delete: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/instances/${id}`), {
        method: 'DELETE',
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },

    restore: async (id: number, restorePath: string) => {
      const request: BackupRestoreRequest = { restore_path: restorePath }
      const response = await fetch(apiUrl(`/backup/instances/${id}/restore`), {
        method: 'POST',
        credentials: 'include',
        headers: getJsonHeaders(),
        body: JSON.stringify(request)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },

    verify: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/instances/${id}/verify`), {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    }
  },
  
  // SSH Keys
  sshKeys: {
    list: async () => {
      const response = await fetch(apiUrl("/ssh-keys"), {
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    generate: async (keyName: string, keyType: string = "rsa", keySize: number = 4096, passphrase?: string) => {
      const request: SSHKeyGenerateRequest = {
        key_name: keyName, key_type: keyType, key_size: keySize, passphrase
      }
      const response = await fetch(apiUrl('/ssh-keys/generate'), {
        method: 'POST',
        credentials: 'include',
        headers: getJsonHeaders(),
        body: JSON.stringify(request)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    import: async (keyName: string, privateKey: string, passphrase?: string) => {
      const request: SSHKeyImportRequest = {
        key_name: keyName, private_key: privateKey, passphrase
      }
      const response = await fetch(apiUrl('/ssh-keys/import'), {
        method: 'POST',
        credentials: 'include',
        headers: getJsonHeaders(),
        body: JSON.stringify(request)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    get: async (keyName: string) => {
      const response = await fetch(apiUrl(`/ssh-keys/${encodeURIComponent(keyName)}`), {
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    delete: async (keyName: string) => {
      const response = await fetch(apiUrl(`/ssh-keys/${encodeURIComponent(keyName)}`), {
        method: 'DELETE',
        credentials: 'include',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    test: async (keyName: string, host: string, username: string, port: number = 22, passphrase?: string) => {
      const request: SSHKeyTestRequest = { host, username, port, passphrase }
      const response = await fetch(apiUrl(`/ssh-keys/${encodeURIComponent(keyName)}/test`), {
        method: 'POST',
        credentials: 'include',
        headers: getJsonHeaders(),
        body: JSON.stringify(request)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    }
  }
}
