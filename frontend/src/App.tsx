import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import TemplatesPage from './pages/TemplatesPage'
import ValidationPage from './pages/ValidationPage'
import UploadPage from './pages/UploadPage'
import MapPage from './pages/MapPage'
import ValidateResultsPage from './pages/ValidateResultsPage'
import ExportPage from './pages/ExportPage'
import ChatPage from './pages/ChatPage'
import MemoryPage from './pages/MemoryPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="templates" element={<TemplatesPage />} />
        <Route path="validation" element={<ValidationPage />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="map" element={<MapPage />} />
        <Route path="validate-results" element={<ValidateResultsPage />} />
        <Route path="export" element={<ExportPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="memory" element={<MemoryPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
