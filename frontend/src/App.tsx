import { Navigate } from 'react-router-dom'
import { Routes, Route } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import ProjectDetailPage from './pages/ProjectDetailPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function GuestRoute({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      <Route path="/projects/:id" element={<ProtectedRoute><ProjectDetailPage /></ProtectedRoute>} />
      <Route path="/login" element={<GuestRoute><LoginPage /></GuestRoute>} />
      <Route path="/register" element={<GuestRoute><RegisterPage /></GuestRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
