// Generated from the FastAPI OpenAPI schema. Do not edit by hand.

export interface BackupServerCreate {
  name: string
  type: 'local' | 'remote'
  host?: string | null
  port?: number | null
  remote_path?: string | null
  local_path?: string | null
  auth_type?: 'password' | 'ssh_key' | null
  username?: string | null
  password?: string | null
  ssh_key?: string | null
  ssh_key_passphrase?: string | null
}

export interface BackupServerUpdate {
  name?: string | null
  type?: 'local' | 'remote' | null
  host?: string | null
  port?: number | null
  remote_path?: string | null
  local_path?: string | null
  auth_type?: 'password' | 'ssh_key' | null
  username?: string | null
  password?: string | null
  ssh_key?: string | null
  ssh_key_passphrase?: string | null
}

export interface BackupJobCreate {
  name: string
  backup_type: 'vm' | 'container' | 'system' | 'database'
  targets: string[]
  schedule: string
  server_id: number
  retention_days?: number
  compression?: boolean
}

export interface BackupJobUpdate {
  name?: string | null
  backup_type?: 'vm' | 'container' | 'system' | 'database' | null
  targets?: string[] | null
  schedule?: string | null
  server_id?: number | null
  status?: 'active' | 'paused' | 'error' | null
  retention_days?: number | null
  compression?: boolean | null
}

export interface BackupRestoreRequest {
  restore_path: string
}

export interface SSHKeyGenerateRequest {
  key_name: string
  key_type?: string
  key_size?: number
  passphrase?: string | null
}

export interface SSHKeyImportRequest {
  key_name: string
  private_key: string
  passphrase?: string | null
}

export interface SSHKeyTestRequest {
  host: string
  username: string
  port?: number
  passphrase?: string | null
}
