"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { useAuth } from "@/components/auth-provider"

export default function LoginPage() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const { setToken } = useAuth()
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const token = btoa(`${username}:${password}`)
    try {
      const res = await fetch("http://localhost:8000/", {
        headers: { Authorization: `Basic ${token}` },
      })
      if (res.ok) {
        setToken(token)
        router.push("/")
      } else {
        setToken(null)
        setError("Login fehlgeschlagen")
      }
    } catch {
      setToken(null)
      setError("Login fehlgeschlagen")
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={handleSubmit} className="space-y-4 p-6 border rounded">
        <div>
          <label className="block mb-1">Benutzername</label>
          <input
            className="border p-2 w-64"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div>
          <label className="block mb-1">Passwort</label>
          <input
            type="password"
            className="border p-2 w-64"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button type="submit" className="p-2 bg-primary text-primary-foreground rounded w-full">
          Login
        </button>
      </form>
    </div>
  )
}
