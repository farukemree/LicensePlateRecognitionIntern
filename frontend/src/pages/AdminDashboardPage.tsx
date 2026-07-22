import { useState } from 'react'
import type { ReactNode } from 'react'
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined'
import VideocamOutlinedIcon from '@mui/icons-material/VideocamOutlined'
import LocalShippingOutlinedIcon from '@mui/icons-material/LocalShippingOutlined'
import BlockOutlinedIcon from '@mui/icons-material/BlockOutlined'
import GroupOutlinedIcon from '@mui/icons-material/GroupOutlined'
import DirectionsCarOutlinedIcon from '@mui/icons-material/DirectionsCarOutlined'
import ErrorOutlineOutlinedIcon from '@mui/icons-material/ErrorOutlineOutlined'
import HourglassTopOutlinedIcon from '@mui/icons-material/HourglassTopOutlined'
import CheckCircleOutlineOutlinedIcon from '@mui/icons-material/CheckCircleOutlineOutlined'
import Inventory2OutlinedIcon from '@mui/icons-material/Inventory2Outlined'
import LoginOutlinedIcon from '@mui/icons-material/LoginOutlined'
import LogoutIcon from '@mui/icons-material/Logout'
import AccessTimeOutlinedIcon from '@mui/icons-material/AccessTimeOutlined'
import DashboardLayout from '../components/layout/DashboardLayout'
import SecurityPanelHome from '../components/security/SecurityPanelHome'
import ExpectedVehiclesView from '../components/warehouse/expected/ExpectedVehiclesView'
import BlacklistView from '../components/warehouse/blacklist/BlacklistView'
import UserManagementView from '../components/admin/users/UserManagementView'
import { useDashboardData } from '../lib/dashboardData'
import type { VehicleLog } from '../lib/dashboardData'

type AdminSection =
  | 'Ana Menü'
  | 'Kamera İzleme'
  | 'Beklenen Araçlar'
  | 'Kara Liste'
  | 'Kullanıcı Yönetimi'

type User = {
  id: string
  fullName: string
  username: string
  role: string
  status: string
}

const adminMenuItems: Array<{
  icon: ReactNode
  label: AdminSection
}> = [
  {
    icon: <HomeOutlinedIcon />,
    label: 'Ana Menü',
  },
  {
    icon: <VideocamOutlinedIcon />,
    label: 'Kamera İzleme',
  },
  {
    icon: <LocalShippingOutlinedIcon />,
    label: 'Beklenen Araçlar',
  },
  {
    icon: <BlockOutlinedIcon />,
    label: 'Kara Liste',
  },
  {
    icon: <GroupOutlinedIcon />,
    label: 'Kullanıcı Yönetimi',
  },
]

const users: User[] = []

function AdminDashboardPage() {
  const [menuOpen, setMenuOpen] = useState(true)
  const {
    expectedVehicles,
    activeBlacklistVehicles,
    blacklistRequests,
    entryLogs,
    exitLogs,
  } = useDashboardData()

  const [activeSection, setActiveSection] = useState<AdminSection>('Ana Menü')
  const currentUserName = 'Beyza Bora'

  return (
    <DashboardLayout
      activeSection={activeSection}
      ariaLabel="Admin ekranı"
      menuAriaLabel="Admin Menüsü"
      menuItems={adminMenuItems}
      menuOpen={menuOpen}
      onMenuToggle={() => setMenuOpen((current) => !current)}
      onSectionChange={setActiveSection}
      roleLabel="Sistem Yöneticisi"
      userName={currentUserName}
    >
        <section className="manager-main">
          {activeSection === 'Ana Menü' && (
            <AdminHome
              expectedVehiclesCount={expectedVehicles.length}
              blacklistVehiclesCount={activeBlacklistVehicles.length}
              entryLogs={entryLogs}
              exitLogs={exitLogs}
              usersCount={users.length}
            />
          )}

          {activeSection === 'Kamera İzleme' && (
            <SecurityPanelHome entryLogs={entryLogs} exitLogs={exitLogs} />
          )}

          {activeSection === 'Beklenen Araçlar' && (
            <ExpectedVehiclesView vehicles={expectedVehicles} />
          )}

          {activeSection === 'Kara Liste' && (
            <BlacklistView
              activeVehicles={activeBlacklistVehicles}
              requests={blacklistRequests}
            />
          )}

          {activeSection === 'Kullanıcı Yönetimi' && (
            <UserManagementView users={users} />
          )}
        </section>
    </DashboardLayout>
  )
}

function AdminHome({
  expectedVehiclesCount,
  blacklistVehiclesCount,
  entryLogs,
  exitLogs,
  usersCount,
}: {
  expectedVehiclesCount: number
  blacklistVehiclesCount: number
  entryLogs: VehicleLog[]
  exitLogs: VehicleLog[]
  usersCount: number
}) {
  const totalMovements = entryLogs.length + exitLogs.length
  const recentLogs = [...entryLogs, ...exitLogs].slice(0, 5)

  const systemItems = [
    { label: 'Backend', tag: 'Backend', value: 'Çalışıyor' },
    { label: 'Veritabanı', tag: 'Veritabanı', value: 'Bağlı' },
    { label: 'Keycloak', tag: 'Keycloak', value: 'Ayar bekliyor' },
  ]

  return (
    <section className="admin-home" aria-label="Admin ana sayfası">
      {/* Üst Başlık Alanı */}
      <div className="admin-home-heading">
        <div>
          <small>Canlı operasyon özeti</small>
          <h2>Admin Kontrol Paneli</h2>
        </div>
        <p>
          Depo hareketleri, beklenen araçlar ve kritik sistem durumları tek
          ekranda izlenir.
        </p>
      </div>

      {/* KPI Kartları Grid */}
      <section className="admin-kpi-grid" aria-label="Admin özet kartları">
        <article className="admin-kpi-card">
          <div className="admin-kpi-header">
            <span className="admin-kpi-icon">
              <DirectionsCarOutlinedIcon />
            </span>
            <h3>Bugünkü hareket</h3>
          </div>
          <strong>{totalMovements}</strong>
          <div className="admin-kpi-footer">
            <span className="badge">0%</span>
            <small>Dün ile aynı</small>
          </div>
        </article>

        <article className="admin-kpi-card">
          <div className="admin-kpi-header">
            <span className="admin-kpi-icon">
              <HourglassTopOutlinedIcon />
            </span>
            <h3>Beklenen araç</h3>
          </div>
          <strong>{expectedVehiclesCount}</strong>
          <div className="admin-kpi-footer">
            <span className="badge">0%</span>
            <small>Onay bekleyen 0</small>
          </div>
        </article>

        <article className="admin-kpi-card">
          <div className="admin-kpi-header">
            <span className="admin-kpi-icon">
              <ErrorOutlineOutlinedIcon />
            </span>
            <h3>Kara liste</h3>
          </div>
          <strong>{blacklistVehiclesCount}</strong>
          <div className="admin-kpi-footer">
            <span className="badge">0%</span>
            <small>Aktif kayıt 0</small>
          </div>
        </article>

        <article className="admin-kpi-card">
          <div className="admin-kpi-header">
            <span className="admin-kpi-icon">
              <GroupOutlinedIcon />
            </span>
            <h3>Kullanıcı</h3>
          </div>
          <strong>{usersCount}</strong>
          <div className="admin-kpi-footer">
            <span className="badge">0%</span>
            <small>Toplam kullanıcı 0</small>
          </div>
        </article>
      </section>

      {/* Ana Gövde Düzeni (2 Sütunlu Grid) */}
      <section className="admin-home-grid">
        {/* Sol Taraf: Son Hareketler Panel */}
        <article className="admin-panel">
          <h3>
            <span>Son hareketler</span>
            <small style={{ fontWeight: 400, color: '#6b7280' }}>
              Kapı Kayıtları
            </small>
          </h3>

          <div className="admin-log-list">
            {recentLogs.length > 0 ? (
              <ul>
                {recentLogs.map((log) => (
                  <li key={`${log.plate}-${log.time}`}>
                    <time>{log.time}</time>
                    <div>
                      <strong>{log.plate}</strong>
                      <p>{log.vehicleType}</p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="admin-empty-state">
                <div className="icon-box">
                  <Inventory2OutlinedIcon />
                </div>
                <span>Henüz araç hareketi yok.</span>
              </div>
            )}
          </div>
        </article>

        {/* Sağ Taraf: Sistem Servis Durumu */}
        <article className="admin-panel">
          <h3>Sistem Servis Durumu</h3>

          <ul className="admin-status-list">
            {systemItems.map((item) => (
              <li key={item.label}>
                <div className="admin-status-left">
                  <span className="admin-status-check">
                    <CheckCircleOutlineOutlinedIcon fontSize="inherit" />
                  </span>
                  <span className="admin-status-tag">{item.tag}</span>
                </div>
                <span className="admin-status-value">{item.value}</span>
              </li>
            ))}
          </ul>
        </article>
      </section>

      {/* Alt Taraf: Yönetim Hızlı Bakış Paneli */}
      <article className="admin-panel">
        <h3>Yönetim Hızlı Bakış</h3>

        <ul className="admin-summary-list">
          <li>
            <div className="admin-summary-icon">
              <LoginOutlinedIcon />
            </div>
            <div className="admin-summary-info">
              <span>Giriş kayıtları</span>
              <strong>{entryLogs.length}</strong>
            </div>
          </li>

          <li>
            <div className="admin-summary-icon">
              <LogoutIcon />
            </div>
            <div className="admin-summary-info">
              <span>Çıkış kayıtları</span>
              <strong>{exitLogs.length}</strong>
            </div>
          </li>

          <li>
            <div className="admin-summary-icon">
              <AccessTimeOutlinedIcon />
            </div>
            <div className="admin-summary-info">
              <span>Bekleyen tanımlar</span>
              <strong>0</strong>
            </div>
          </li>
        </ul>
      </article>
    </section>
  )
}

export default AdminDashboardPage
