"use client"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Bell, Search, User, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { useAuth } from "@/components/auth-provider"
import { useRouter } from "next/navigation"

export function Header() {
  const { setTheme, theme } = useTheme()
  const { setToken } = useAuth()
  const router = useRouter()

  const handleLogout = () => {
    setToken(null)
    router.push("/login")
  }

  return (
    <header className="h-16 border-b border-border/30 upservx-glass px-6 flex items-center justify-end backdrop-blur-md">
      <div className="flex items-center space-x-3">
        <Button 
          variant="ghost" 
          size="icon" 
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="rounded-xl bg-background/60 backdrop-blur-sm border border-border/30 hover:bg-primary/10 hover:border-primary/40"
        >
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          <span className="sr-only">Toggle theme</span>
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button 
              variant="ghost" 
              size="icon"
              className="rounded-xl bg-gradient-to-br from-primary/10 to-purple-600/10 border border-primary/20 hover:from-primary/20 hover:to-purple-600/20"
            >
              <User className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="upservx-glass rounded-xl border-border/30">
            <DropdownMenuItem 
              onClick={handleLogout}
              className="rounded-lg hover:bg-destructive/10 hover:text-destructive font-medium"
            >
              Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
