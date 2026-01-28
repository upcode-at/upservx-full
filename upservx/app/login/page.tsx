"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import Image from "next/image"
import { useAuth } from "@/components/auth-provider"
import { apiUrl } from "@/lib/api"

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
      const res = await fetch(apiUrl("/"), {
        headers: { Authorization: `Basic ${token}` },
      })
      if (res.ok) {
        setToken(token)
        router.push("/")
      } else {
        setToken(null)
        setError("Login failed")
      }
    } catch {
      setToken(null)
      setError("Login failed")
    }
  }

  return (
    <div className="flex min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-slate-900 dark:via-slate-800 dark:to-indigo-900">
      <div className="relative w-1/2 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-purple-600/20 z-10"></div>
        <Image
          src="/login.jpg"
          alt="Login illustration"
          fill
          sizes="50vw"
          className="object-cover"
        />
        <div className="absolute inset-0 z-20 flex items-center justify-center">
          <div className="text-center text-white p-8">
            <div className="flex items-center justify-center mx-auto mb-6">
              <img src="/logo.png" alt="UpServX Logo" className="h-24 w-auto object-contain" />
            </div>
            <h1 className="text-4xl font-bold mb-4">Welcome to UpServX</h1>
            <p className="text-xl opacity-90">Professional Server Management Platform</p>
          </div>
        </div>
      </div>
      <div className="flex w-1/2 items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="upservx-card p-8 space-y-6">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-white mb-2">
                Sign In
              </h2>
              <p className="text-muted-foreground">Access your server dashboard</p>
            </div>
            
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-foreground">Username</label>
                <input
                  className="w-full h-12 px-4 rounded-xl border border-border/50 bg-background/80 backdrop-blur-sm focus:border-primary/60 focus:ring-2 focus:ring-primary/20 focus:outline-none transition-all duration-200"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-foreground">Password</label>
                <input
                  type="password"
                  className="w-full h-12 px-4 rounded-xl border border-border/50 bg-background/80 backdrop-blur-sm focus:border-primary/60 focus:ring-2 focus:ring-primary/20 focus:outline-none transition-all duration-200"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                />
              </div>
              {error && (
                <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20">
                  <p className="text-destructive text-sm font-medium">{error}</p>
                </div>
              )}
              <button 
                type="submit" 
                className="w-full upservx-button-primary text-white font-semibold py-3 px-4 rounded-xl shadow-lg hover:shadow-xl transform hover:-translate-y-1 transition-all duration-300"
              >
                Sign In
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
