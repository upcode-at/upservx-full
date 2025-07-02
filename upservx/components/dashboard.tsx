"use client"

import { useState } from "react"
import { Sidebar } from "@/components/sidebar"
import { Header } from "@/components/header"
import { SystemOverview } from "@/components/system-overview"
import { VirtualMachines } from "@/components/virtual-machines"
import { Containers } from "@/components/containers"
import { Services } from "@/components/services"
import { Settings } from "@/components/settings"
import { NetworkManagement } from "@/components/network-management"
import { StorageManagement } from "@/components/storage-management"
import { UserManagement } from "@/components/user-management"
import { BackupManagement } from "@/components/backup-management"
import { ImageManagement } from "@/components/image-management"

export function Dashboard() {
  const [activeSection, setActiveSection] = useState("dashboard")

  const renderContent = () => {
    switch (activeSection) {
      case "dashboard":
        return <SystemOverview />
      case "vms":
        return <VirtualMachines />
      case "containers":
        return <Containers />
      case "services":
        return <Services />
      case "network":
        return <NetworkManagement />
      case "storage":
        return <StorageManagement />
      case "users":
        return <UserManagement />
      case "backup":
        return <BackupManagement />
      case "settings":
        return <Settings />
      case "images":
        return <ImageManagement />
      default:
        return <SystemOverview />
    }
  }

  return (
    <div className="flex h-screen bg-background">
      <Sidebar activeSection={activeSection} onSectionChange={setActiveSection} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto p-6">{renderContent()}</main>
      </div>
    </div>
  )
}
