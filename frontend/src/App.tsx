import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './styles/login.css'
import './styles/security.css'
import './styles/warehouse.css'
import './styles/admin.css'

import LoginPage from './pages/LoginPage'
import SecurityDashboardPage from './pages/SecurityDashboardPage'
import WarehouseManagerPage from './pages/WarehouseManagerPage'
import AdminDashboardPage from './pages/AdminDashboardPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />

        <Route path="/login" element={<LoginPage />} />

        <Route
          path="/dashboard"
          element={<SecurityDashboardPage />}
        />

        <Route
          path="/warehouse-manager"
          element={<WarehouseManagerPage />}
        />

        <Route
          path="/admin"
          element={<AdminDashboardPage />}
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App