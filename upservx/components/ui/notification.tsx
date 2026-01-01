"use client"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle, CheckCircle2, AlertTriangle, Info, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export type NotificationType = "success" | "error" | "warning" | "info"

interface NotificationProps {
  type: NotificationType
  message: string
  onClose?: () => void
  className?: string
}

const notificationConfig = {
  success: {
    icon: CheckCircle2,
    variant: "default" as const,
    className: "border-green-500/50 bg-green-500/10 text-green-700 dark:text-green-400",
    iconClassName: "text-green-600 dark:text-green-400"
  },
  error: {
    icon: AlertCircle,
    variant: "destructive" as const,
    className: "border-red-500/50 bg-red-500/10 text-red-700 dark:text-red-400",
    iconClassName: "text-red-600 dark:text-red-400"
  },
  warning: {
    icon: AlertTriangle,
    variant: "default" as const,
    className: "border-yellow-500/50 bg-yellow-500/10 text-yellow-700 dark:text-yellow-400",
    iconClassName: "text-yellow-600 dark:text-yellow-400"
  },
  info: {
    icon: Info,
    variant: "default" as const,
    className: "border-blue-500/50 bg-blue-500/10 text-blue-700 dark:text-blue-400",
    iconClassName: "text-blue-600 dark:text-blue-400"
  }
}

export function Notification({ type, message, onClose, className }: NotificationProps) {
  const config = notificationConfig[type]
  const Icon = config.icon

  return (
    <Alert variant={config.variant} className={cn(config.className, className)}>
      <Icon className={cn("h-4 w-4", config.iconClassName)} />
      <AlertDescription className="flex items-center justify-between">
        <span>{message}</span>
        {onClose && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-6 w-6 p-0 ml-4 hover:bg-transparent"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}

interface NotificationContainerProps {
  success?: string | null
  error?: string | null
  warning?: string | null
  info?: string | null
  onClearSuccess?: () => void
  onClearError?: () => void
  onClearWarning?: () => void
  onClearInfo?: () => void
  className?: string
}

export function NotificationContainer({
  success,
  error,
  warning,
  info,
  onClearSuccess,
  onClearError,
  onClearWarning,
  onClearInfo,
  className
}: NotificationContainerProps) {
  return (
    <div className={cn("space-y-2", className)}>
      {error && (
        <Notification
          type="error"
          message={error}
          onClose={onClearError}
        />
      )}
      {warning && (
        <Notification
          type="warning"
          message={warning}
          onClose={onClearWarning}
        />
      )}
      {success && (
        <Notification
          type="success"
          message={success}
          onClose={onClearSuccess}
        />
      )}
      {info && (
        <Notification
          type="info"
          message={info}
          onClose={onClearInfo}
        />
      )}
    </div>
  )
}
