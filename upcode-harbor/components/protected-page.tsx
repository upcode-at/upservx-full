"use client"
import React, { useEffect } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "./auth-provider"

export default function ProtectedPage({ children }: { children: React.ReactNode }) {
  const { token, isLoaded } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (isLoaded && !token) {
      router.replace("/login")
    }
  }, [token, isLoaded, router])

  if (!isLoaded) {
    return null
  }

  if (!token) {
    return null
  }

  return <>{children}</>
}
