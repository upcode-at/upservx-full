"use client"
import React, { createContext, useContext, useEffect, useState } from "react"
import { apiUrl } from "@/lib/api"

export interface UserPermissions {
  admin: boolean
  containers: boolean
  vms: boolean
  storage: boolean
  shell: boolean
}

export interface AuthContextType {
  token: string | null
  setToken: (token: string | null) => void
  isLoaded: boolean
  username: string | null
  groups: string[]
  permissions: UserPermissions
  reloadPermissions: () => Promise<void>
}

const DEFAULT_PERMISSIONS: UserPermissions = { admin: false, containers: false, vms: false, storage: false, shell: false }

const AuthContext = createContext<AuthContextType>({
  token: null,
  setToken: () => {},
  isLoaded: false,
  username: null,
  groups: [],
  permissions: DEFAULT_PERMISSIONS,
  reloadPermissions: async () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null)
  const [isLoaded, setIsLoaded] = useState(false)
  const [username, setUsername] = useState<string | null>(null)
  const [groups, setGroups] = useState<string[]>([])
  const [permissions, setPermissions] = useState<UserPermissions>(DEFAULT_PERMISSIONS)

  // Fetch /auth/me using a raw token (bypasses the patched window.fetch to avoid
  // circular dependency while the token state is being set up)
  const fetchMe = async (rawToken: string | null) => {
    if (!rawToken) {
      setUsername(null)
      setGroups([])
      setPermissions(DEFAULT_PERMISSIONS)
      return
    }
    try {
      const res = await fetch(apiUrl("/auth/me"), {
        headers: { Authorization: `Basic ${rawToken}` },
      })
      if (res.ok) {
        const data = await res.json()
        setUsername(data.username ?? null)
        setGroups(data.groups ?? [])
        setPermissions(data.permissions ?? DEFAULT_PERMISSIONS)
      }
    } catch {
      // network error — keep whatever we had
    }
  }

  // Load stored token on mount
  useEffect(() => {
    if (typeof window === "undefined") return
    const stored = localStorage.getItem("authToken")
    if (stored) {
      setTokenState(stored)
      // Wait for /auth/me before marking as loaded so the sidebar
      // doesn't flash with empty permissions.
      fetchMe(stored).finally(() => setIsLoaded(true))
    } else {
      setIsLoaded(true)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Patch window.fetch to inject Authorization header and handle 401
  useEffect(() => {
    if (typeof window === "undefined") return
    const origFetch = window.fetch
    window.fetch = async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const headers =
        init.headers instanceof Headers
          ? new Headers(init.headers)
          : { ...(init.headers as Record<string, string>) }

      if (token) {
        const hasAuth =
          headers instanceof Headers
            ? headers.has("Authorization")
            : Object.keys(headers).some(
                (h) => h.toLowerCase() === "authorization",
              )

        if (!hasAuth) {
          if (headers instanceof Headers) {
            headers.set("Authorization", `Basic ${token}`)
          } else {
            ;(headers as Record<string, string>)["Authorization"] = `Basic ${token}`
          }
        }
      }

      init.headers = headers

      const response = await origFetch(input, init)

      // If unauthorized and we have a token, clear it and redirect to login
      if (response.status === 401 && token) {
        setTokenState(null)
        setUsername(null)
        setGroups([])
        setPermissions(DEFAULT_PERMISSIONS)
        localStorage.removeItem("authToken")
        if (window.location.pathname !== "/login") {
          window.location.href = "/login"
        }
      }

      return response
    }
    return () => {
      window.fetch = origFetch
    }
  }, [token])

  const reloadPermissions = async () => {
    await fetchMe(token)
  }

  const setToken = (t: string | null) => {
    setTokenState(t)
    if (typeof window === "undefined") return
    if (t) {
      localStorage.setItem("authToken", t)
      fetchMe(t)
    } else {
      localStorage.removeItem("authToken")
      setUsername(null)
      setGroups([])
      setPermissions(DEFAULT_PERMISSIONS)
    }
  }

  return (
    <AuthContext.Provider value={{ token, setToken, isLoaded, username, groups, permissions, reloadPermissions }}>
      {children}
    </AuthContext.Provider>
  )
}
