import { Dashboard } from "@/components/dashboard"
import ProtectedPage from "@/components/protected-page"

export default function Home() {
  return (
    <ProtectedPage>
      <Dashboard />
    </ProtectedPage>
  )
}
