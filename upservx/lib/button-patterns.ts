/**
 * Standardized Button Patterns for Upcode Harbor
 * 
 * This file defines consistent button configurations for common actions
 * across the application. Use these patterns to ensure UI consistency.
 */

import { Plus, Trash2, Edit, Save, X, Download, Upload, Play, Square, Pause, RotateCw, Power, Search, Filter, Settings, RefreshCw } from "lucide-react"

export const buttonPatterns = {
  // Primary Actions
  create: {
    variant: "default" as const,
    icon: Plus,
    iconPosition: "left" as const,
    label: "Create"
  },
  add: {
    variant: "default" as const,
    icon: Plus,
    iconPosition: "left" as const,
    label: "Add"
  },
  save: {
    variant: "default" as const,
    icon: Save,
    iconPosition: "left" as const,
    label: "Save"
  },
  
  // Secondary Actions
  edit: {
    variant: "outline" as const,
    icon: Edit,
    iconPosition: "left" as const,
    label: "Edit"
  },
  cancel: {
    variant: "outline" as const,
    icon: X,
    iconPosition: "left" as const,
    label: "Cancel"
  },
  
  // Destructive Actions
  delete: {
    variant: "destructive" as const,
    icon: Trash2,
    iconPosition: "left" as const,
    label: "Delete"
  },
  remove: {
    variant: "destructive" as const,
    icon: Trash2,
    iconPosition: "left" as const,
    label: "Remove"
  },
  
  // Data Actions
  download: {
    variant: "outline" as const,
    icon: Download,
    iconPosition: "left" as const,
    label: "Download"
  },
  upload: {
    variant: "outline" as const,
    icon: Upload,
    iconPosition: "left" as const,
    label: "Upload"
  },
  export: {
    variant: "outline" as const,
    icon: Download,
    iconPosition: "left" as const,
    label: "Export"
  },
  import: {
    variant: "outline" as const,
    icon: Upload,
    iconPosition: "left" as const,
    label: "Import"
  },
  
  // Control Actions
  start: {
    variant: "default" as const,
    icon: Play,
    iconPosition: "left" as const,
    label: "Start"
  },
  stop: {
    variant: "destructive" as const,
    icon: Square,
    iconPosition: "left" as const,
    label: "Stop"
  },
  pause: {
    variant: "outline" as const,
    icon: Pause,
    iconPosition: "left" as const,
    label: "Pause"
  },
  restart: {
    variant: "outline" as const,
    icon: RotateCw,
    iconPosition: "left" as const,
    label: "Restart"
  },
  power: {
    variant: "outline" as const,
    icon: Power,
    iconPosition: "left" as const,
    label: "Power"
  },
  
  // Utility Actions
  search: {
    variant: "ghost" as const,
    icon: Search,
    iconPosition: "left" as const,
    label: "Search"
  },
  filter: {
    variant: "ghost" as const,
    icon: Filter,
    iconPosition: "left" as const,
    label: "Filter"
  },
  settings: {
    variant: "ghost" as const,
    icon: Settings,
    iconPosition: "left" as const,
    label: "Settings"
  },
  refresh: {
    variant: "ghost" as const,
    icon: RefreshCw,
    iconPosition: "left" as const,
    label: "Refresh"
  }
}

export type ButtonPatternKey = keyof typeof buttonPatterns

/**
 * Standard button sizes
 */
export const buttonSizes = {
  sm: "sm" as const,
  default: "default" as const,
  lg: "lg" as const,
  icon: "icon" as const
}

/**
 * Standard spacing between buttons in a group
 */
export const buttonGroupSpacing = "space-x-2"

/**
 * Standard button loading text
 */
export const loadingText = {
  create: "Creating...",
  add: "Adding...",
  save: "Saving...",
  delete: "Deleting...",
  remove: "Removing...",
  start: "Starting...",
  stop: "Stopping...",
  restart: "Restarting...",
  download: "Downloading...",
  upload: "Uploading...",
  default: "Loading..."
}
