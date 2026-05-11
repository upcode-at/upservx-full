// Type definitions

interface BackupServerCreate {
  name: string
  type: string
  host?: string
  port?: number
  remote_path?: string
  local_path?: string
}

interface BackupServerUpdate {
  name?: string
  type?: string
  host?: string
  port?: number
  remote_path?: string
  local_path?: string
}



interface BackupJobCreate {
  name: string
  backup_type: 'vm' | 'container' | 'system' | 'database'
  targets: string[]
  schedule: string
  server_id: number
}

interface BackupJobUpdate {
  name?: string
  backup_type?: 'vm' | 'container' | 'system' | 'database'
  targets?: string[]
  schedule?: string
  server_id?: number
}

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
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    create: async (server: BackupServerCreate) => {
      const response = await fetch(apiUrl("/backup/servers"), {
        method: 'POST',
        headers: getJsonHeaders(),
        body: JSON.stringify(server)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    get: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/servers/${id}`), {
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    update: async (id: number, data: BackupServerUpdate) => {
      const response = await fetch(apiUrl(`/backup/servers/${id}`), {
        method: 'PUT',
        headers: getJsonHeaders(),
        body: JSON.stringify(data)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    delete: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/servers/${id}`), {
        method: 'DELETE',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    test: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/servers/${id}/test`), {
        method: 'POST',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    getInfo: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/servers/${id}/info`), {
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
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    create: async (job: BackupJobCreate) => {
      const response = await fetch(apiUrl("/backup/jobs"), {
        method: 'POST',
        headers: getJsonHeaders(),
        body: JSON.stringify(job)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    get: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/jobs/${id}`), {
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    update: async (id: number, data: BackupJobUpdate) => {
      const response = await fetch(apiUrl(`/backup/jobs/${id}`), {
        method: 'PUT',
        headers: getJsonHeaders(),
        body: JSON.stringify(data)
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    delete: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/jobs/${id}`), {
        method: 'DELETE',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    execute: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/jobs/${id}/execute`), {
        method: 'POST',
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
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    get: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/instances/${id}`), {
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    delete: async (id: number) => {
      const response = await fetch(apiUrl(`/backup/instances/${id}`), {
        method: 'DELETE',
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
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    generate: async (keyName: string, keyType: string = "rsa", keySize: number = 4096, passphrase?: string) => {
      const params = new URLSearchParams({
        key_name: keyName,
        key_type: keyType,
        key_size: keySize.toString()
      })
      if (passphrase) params.append('passphrase', passphrase)
      
      const response = await fetch(apiUrl(`/ssh-keys/generate?${params.toString()}`), {
        method: 'POST',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    import: async (keyName: string, privateKey: string, passphrase?: string) => {
      const params = new URLSearchParams({
        key_name: keyName,
        private_key: privateKey
      })
      if (passphrase) params.append('passphrase', passphrase)
      
      const response = await fetch(apiUrl(`/ssh-keys/import?${params.toString()}`), {
        method: 'POST',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    get: async (keyName: string) => {
      const response = await fetch(apiUrl(`/ssh-keys/${keyName}`), {
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    delete: async (keyName: string) => {
      const response = await fetch(apiUrl(`/ssh-keys/${keyName}`), {
        method: 'DELETE',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    },
    
    test: async (keyName: string, host: string, username: string, port: number = 22, passphrase?: string) => {
      const params = new URLSearchParams({
        host,
        username,
        port: port.toString()
      })
      if (passphrase) params.append('passphrase', passphrase)
      
      const response = await fetch(apiUrl(`/ssh-keys/${keyName}/test?${params.toString()}`), {
        method: 'POST',
        headers: getAuthHeaders()
      })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      return response.json()
    }
  }
}
