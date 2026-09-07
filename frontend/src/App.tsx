import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './lib/auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Projects from './pages/Projects'
import ProjectDetail from './pages/ProjectDetail'
import MyIssues from './pages/MyIssues'
import Organizations from './pages/Organizations'
import { Spinner } from './components/ui'

export default function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner className="h-6 w-6 text-[var(--color-accent)]" />
      </div>
    )
  }

  if (!user) return <Login />

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/issues" replace />} />
        <Route path="/issues" element={<MyIssues />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/organizations" element={<Organizations />} />
        <Route path="/projects/:id" element={<ProjectDetail />} />
        <Route path="*" element={<Navigate to="/issues" replace />} />
      </Route>
    </Routes>
  )
}
