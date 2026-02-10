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
  // Check for environment variable first (set at build time)
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL
  
  if (apiBase) {
    // Use configured API base URL
    return `${apiBase}${path}`
  }
  
  if (typeof window !== "undefined") {
    // We're in the browser, build URL dynamically at runtime
    const { protocol, hostname, port } = window.location
    
    // If accessing via standard ports (80/443), use reverse proxy with /api/ path
    // This ensures HTTPS works correctly and avoids mixed content issues
    if (port === "" || port === "80" || port === "443") {
      return `/api${path}`
    }
    
    // Check if hostname is a domain name (not an IP address)
    // If it's a domain, always use /api/ path for consistency
    const isIP = /^(\d{1,3}\.){3}\d{1,3}$/.test(hostname)
    if (!isIP) {
      return `/api${path}`
    }
    
    // Otherwise, direct access to backend port (development only)
    // Always use the same hostname as the frontend for consistency
    const apiPort = ":9500"
    return `${protocol}//${hostname}${apiPort}${path}`
  }
  
  // During SSR, return empty string to avoid wrong URLs
  // This should not be used as all fetch calls should be in useEffect (client-side only)
  return ""
}

export function wsUrl(path: string): string {
  // Check for environment variable first
  const wsBase = process.env.NEXT_PUBLIC_WS_BASE_URL
  
  if (wsBase) {
    return `${wsBase}${path}`
  }
  
  if (typeof window !== "undefined") {
    const { protocol, hostname, port } = window.location
    const wsProtocol = protocol === "https:" ? "wss:" : "ws:"
    
    // If accessing via standard ports, use reverse proxy with /ws/ path
    if (port === "" || port === "80" || port === "443") {
      return `${wsProtocol}//${hostname}/ws${path}`
    }
    
    // Check if hostname is a domain name (not an IP address)
    // If it's a domain, always use /ws/ path for consistency
    const isIP = /^(\d{1,3}\.){3}\d{1,3}$/.test(hostname)
    if (!isIP) {
      return `${wsProtocol}//${hostname}/ws${path}`
    }
    
    // Otherwise, direct access to backend port (development only)
    return `${wsProtocol}//${hostname}:9500${path}`
  }
  return `ws://localhost:9500${path}`
}

// Get authorization header with Basic auth
export function getAuthHeaders(): HeadersInit {
  // Try to get token from localStorage first (set by AuthProvider)
  if (typeof window !== "undefined") {
    const storedToken = localStorage.getItem("authToken")
    if (storedToken) {
      return {
        'Authorization': `Basic ${storedToken}`,
      }
    }
  }
  
  // Fallback to default credentials (for SSR or when not logged in)
  const auth = btoa("admin:admin")
  return {
    'Authorization': `Basic ${auth}`,
  }
}

export function getJsonHeaders(): HeadersInit {
  return {
    ...getAuthHeaders(),
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
