import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-semibold transition-all duration-300 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-primary/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-95",
  {
    variants: {
      variant: {
        default:
          "upservx-button-primary text-white shadow-lg hover:shadow-xl border-0 font-medium tracking-wide",
        destructive:
          "bg-gradient-to-r from-red-500 to-red-600 text-white shadow-lg hover:shadow-xl hover:from-red-600 hover:to-red-700 transform hover:-translate-y-0.5 transition-all duration-200",
        outline:
          "border-2 border-primary/20 bg-background/60 backdrop-blur-sm hover:bg-primary/5 hover:border-primary/40 text-primary shadow-sm hover:shadow-md",
        secondary:
          "bg-gradient-to-r from-slate-100 to-slate-200 dark:from-slate-700 dark:to-slate-800 text-secondary-foreground shadow-sm hover:shadow-md hover:from-slate-200 hover:to-slate-300 dark:hover:from-slate-600 dark:hover:to-slate-700",
        ghost:
          "hover:bg-accent/60 hover:text-accent-foreground rounded-xl backdrop-blur-sm transition-all duration-200 hover:scale-105",
        link: "text-primary underline-offset-4 hover:underline font-medium",
      },
      size: {
        default: "h-10 px-6 py-2 has-[>svg]:px-4 text-sm",
        sm: "h-8 rounded-lg gap-1.5 px-4 has-[>svg]:px-3 text-xs",
        lg: "h-12 rounded-xl px-8 has-[>svg]:px-6 text-base",
        icon: "size-10 rounded-xl",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : "button"

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
