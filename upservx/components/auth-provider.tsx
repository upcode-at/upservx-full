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
      if (token) {
        init.headers = {
          ...(init.headers || {}),
          Authorization: `Basic ${token}`,
        }
      }
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
