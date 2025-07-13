"use client"
import React, { createContext, useContext, useEffect, useState } from "react"

interface AuthContextType {
  token: string | null
  setToken: (token: string | null) => void
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  setToken: () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null)

  useEffect(() => {
    if (typeof window === "undefined") return
    const stored = localStorage.getItem("authToken")
    if (stored) setTokenState(stored)
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") return
    const origFetch = window.fetch
    window.fetch = (input: RequestInfo | URL, init: RequestInit = {}) => {
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
      return origFetch(input, init)
    }
    return () => {
      window.fetch = origFetch
    }
  }, [token])

  const setToken = (t: string | null) => {
    setTokenState(t)
    if (typeof window === "undefined") return
    if (t) {
      localStorage.setItem("authToken", t)
    } else {
      localStorage.removeItem("authToken")
    }
  }

  return (
    <AuthContext.Provider value={{ token, setToken }}>
      {children}
    </AuthContext.Provider>
  )
}
