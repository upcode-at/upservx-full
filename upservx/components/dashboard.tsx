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
import BackupManagement from "@/components/backup-management"
import { ImageManagement } from "@/components/image-management"
import { Logs } from "@/components/logs"
import { SystemShell } from "@/components/system-shell"
import { ComposeBuilder } from "@/components/compose-builder"
import { AppStore } from "@/components/app-store"
import FirewallManagement from "@/components/firewall-management"
import ClusterManagement from "@/components/cluster-management"

export function Dashboard() {
  const [activeSection, setActiveSection] = useState("dashboard")

  const renderContent = () => {
    switch (activeSection) {
      case "dashboard":
        return <SystemOverview />
      case "shell":
        return <SystemShell />
      case "vms":
        return <VirtualMachines />
      case "containers":
        return <Containers />
      case "compose":
        return <ComposeBuilder />
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
      case "logs":
        return <Logs />
      case "settings":
        return <Settings />
      case "images":
        return <ImageManagement />
      case "app-store":
        return <AppStore />
      case "firewall":
        return <FirewallManagement />
      case "cluster":
        return <ClusterManagement />
      default:
        return <SystemOverview />
    }
  }

  return (
    <div className="flex h-screen bg-background">
      <Sidebar activeSection={activeSection} onSectionChange={setActiveSection} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto p-4 md:p-6 lg:p-8">{renderContent()}</main>
      </div>
    </div>
  )
}
