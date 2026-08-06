"use client"
import React, { createContext, useContext, useEffect, useRef, useState } from "react"
import { apiUrl } from "@/lib/api"

export interface UserPermissions {
  admin: boolean
  containers: boolean
  vms: boolean
  storage: boolean
  shell: boolean
  logs: boolean
}

export interface AuthContextType {
  /** Non-null when the HttpOnly session cookie is valid; null otherwise. */
  token: string | null
  setToken: (token: string | null) => Promise<void>
  isLoaded: boolean
  username: string | null
  groups: string[]
  permissions: UserPermissions
  reloadPermissions: () => Promise<void>
}

const DEFAULT_PERMISSIONS: UserPermissions = {
  admin: false, containers: false, vms: false,
  storage: false, shell: false, logs: false,
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  setToken: async () => {},

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
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoaded, setIsLoaded] = useState(false)
  const [username, setUsername] = useState<string | null>(null)
  const [groups, setGroups] = useState<string[]>([])
  const [permissions, setPermissions] = useState<UserPermissions>(DEFAULT_PERMISSIONS)

  // Keep a ref so the fetch interceptor (closed over once) always sees the
  // latest auth state without needing to be recreated on every change.
  const isAuthRef = useRef(isAuthenticated)
  useEffect(() => { isAuthRef.current = isAuthenticated }, [isAuthenticated])

  const resetAuth = () => {
    setIsAuthenticated(false)
    setUsername(null)
    setGroups([])
    setPermissions(DEFAULT_PERMISSIONS)
  }

  /**
   * Verify the current session cookie against /auth/me and populate user info.
   * Uses the native (unpatched) fetch with explicit credentials so it works
   * both before and after the interceptor is installed.
   */
  const fetchMe = async () => {
    try {
      const res = await fetch(apiUrl("/auth/me"), { credentials: "include" })
      if (res.ok) {
        const data = await res.json()
        setIsAuthenticated(true)
        setUsername(data.username ?? null)
        setGroups(data.groups ?? [])
        setPermissions(data.permissions ?? DEFAULT_PERMISSIONS)
      } else {
        resetAuth()
      }
    } catch {
      // network error — keep current state
    }
  }

  // On mount: verify session cookie, then mark as loaded.
  useEffect(() => {
    fetchMe().finally(() => setIsLoaded(true))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Patch window.fetch:
  //   • Always send cookies (credentials: "include") so the HttpOnly auth
  //     cookie reaches cross-origin API requests.
  //   • Redirect to /login on 401 when the user was previously authenticated.
  useEffect(() => {
    if (typeof window === "undefined") return
    const origFetch = window.fetch
    window.fetch = (input: RequestInfo | URL, init: RequestInit = {}) => {
      const requestInit: RequestInit = {
        ...init,
        credentials: init.credentials ?? "include",
      }
      return origFetch(input, requestInit).then((response) => {
        if (response.status === 401 && isAuthRef.current) {
          resetAuth()
          if (window.location.pathname !== "/login") {
            window.location.href = "/login"
          }
        }
        return response
      })
    }
    return () => { window.fetch = origFetch }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const reloadPermissions = async () => { await fetchMe() }

  /**
   * setToken(truthy) → called after a successful login; refreshes user info
   *                     from the freshly-set session cookie.
   * setToken(null)   → logout: clears the cookie server-side, resets state.
   */
  const setToken = async (t: string | null): Promise<void> => {
    if (t !== null) {
      await fetchMe()
    } else {
      fetch(apiUrl("/auth/logout"), { method: "POST", credentials: "include" }).catch(() => {})
      resetAuth()
    }
  }

  // Expose a compat shim so all existing `if (!token)` checks keep working.
  const token = isAuthenticated ? "__session__" : null

  return (
    <AuthContext.Provider value={{ token, setToken, isLoaded, username, groups, permissions, reloadPermissions }}>
      {children}
    </AuthContext.Provider>
  )
}

