import { useState } from 'react'
import type { ReactNode } from 'react'
import AccountCircleOutlinedIcon from '@mui/icons-material/AccountCircleOutlined'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import NotificationsNoneOutlinedIcon from '@mui/icons-material/NotificationsNoneOutlined'
import MenuOutlinedIcon from '@mui/icons-material/MenuOutlined'
import LogoutOutlinedIcon from '@mui/icons-material/LogoutOutlined'
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined'
import VideocamOutlinedIcon from '@mui/icons-material/VideocamOutlined'
import LocalShippingOutlinedIcon from '@mui/icons-material/LocalShippingOutlined'
import BlockOutlinedIcon from '@mui/icons-material/BlockOutlined'
import GroupOutlinedIcon from '@mui/icons-material/GroupOutlined'
import dhlLogo from '../assets/dhl-logo.png'
import SecurityPanelHome from '../components/security/SecurityPanelHome'
import ExpectedVehiclesView from '../components/warehouse/expected/ExpectedVehiclesView'
import BlacklistView from '../components/warehouse/blacklist/BlacklistView'
import UserManagementView from '../components/admin/users/UserManagementView'
import { useDashboardData } from '../lib/dashboardData'
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
  const [menuOpen, setMenuOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const {
    expectedVehicles,
    activeBlacklistVehicles,
    blacklistRequests,
    entryLogs,
    exitLogs,
  } = useDashboardData()

  const [activeSection, setActiveSection] =
    useState<AdminSection>('Ana Menü')

  const currentUserName = 'Beyza Bora'

  return (
    <main
      className="manager-page"
      aria-label="Admin ekranı"
    >
      <header className="manager-header">

        <div className="manager-brand">

          <img
            className="manager-logo"
            src={dhlLogo}
            alt="DHL"
          />

          <h1>Plaka Tanıma Sistemi</h1>

          <button
            className="manager-menu-toggle"
            type="button"
            aria-expanded={menuOpen}
            onClick={() =>
              setMenuOpen((current) => !current)
            }
          >
            <MenuOutlinedIcon />
          </button>

        </div>

        <div className="manager-user-actions">

          <button
            className="manager-icon-button"
            type="button"
          >
            <NotificationsNoneOutlinedIcon />
          </button>

          <div className="header-menu">

            <button
              className="manager-profile"
              type="button"
              aria-expanded={profileOpen}
              onClick={() =>
                setProfileOpen((current) => !current)
              }
            >
              <AccountCircleOutlinedIcon />

              <span>{currentUserName}</span>

              <KeyboardArrowDownIcon />

            </button>
                        {profileOpen && (
              <section
                className="profile-menu"
                aria-label="Profil Menüsü"
              >
                <strong>{currentUserName}</strong>

                <span>Sistem Yöneticisi</span>

                <button type="button">
                  <LogoutOutlinedIcon />
                  Çıkış Yap
                </button>
              </section>
            )}

          </div>

        </div>

      </header>

      <div className={`manager-layout${menuOpen ? ' menu-open' : ''}`}>

        {menuOpen && (
          <aside
            className="manager-sidebar"
            aria-label="Admin Menüsü"
          >
            {adminMenuItems.map((item) => (
              <button
                key={item.label}
                type="button"
                className={
                  item.label === activeSection
                    ? 'active'
                    : ''
                }
                onClick={() =>
                  setActiveSection(item.label)
                }
              >
                <span>{item.icon}</span>

                {item.label}
              </button>
            ))}
          </aside>
        )}

        <section className="manager-main">

          {activeSection === 'Ana Menü' && (
            <AdminHome
              expectedVehiclesCount={expectedVehicles.length}
              blacklistVehiclesCount={activeBlacklistVehicles.length}
            />
          )}

          {activeSection === 'Kamera İzleme' && (
           <SecurityPanelHome
  entryLogs={entryLogs}
  exitLogs={exitLogs}
/>
          )}

          {activeSection === 'Beklenen Araçlar' && (
            <ExpectedVehiclesView
              vehicles={expectedVehicles}
            />
          )}

          {activeSection === 'Kara Liste' && (
            <BlacklistView
              activeVehicles={activeBlacklistVehicles}
              requests={blacklistRequests}
            />
          )}

          {activeSection === 'Kullanıcı Yönetimi' && (
            <UserManagementView
              users={users}
            />
          )}

        </section>

      </div>

    </main>
  )
}
function AdminHome({
  expectedVehiclesCount,
  blacklistVehiclesCount,
}: {
  expectedVehiclesCount: number
  blacklistVehiclesCount: number
}) {
  return (
    <>
      <section className="manager-stats">
        <article className="manager-stat-card orange">
          <strong>Bugünkü Araç Hareketi</strong>
          <h2>0</h2>
        </article>

        <article className="manager-stat-card yellow">
          <strong>Beklenen Araçlar</strong>
          <h2>{expectedVehiclesCount}</h2>
        </article>

        <article className="manager-stat-card red">
          <strong>Kara Listedeki Araçlar</strong>
          <h2>{blacklistVehiclesCount}</h2>
        </article>

        <article className="manager-stat-card blue">
          <strong>Kullanıcılar</strong>
          <h2>{users.length}</h2>
        </article>
      </section>

      <section className="manager-panel-grid">

        <article className="manager-panel">
          <h2>Giriş Kamerası</h2>
          <div className="manager-panel-body" />
        </article>

        <article className="manager-panel">
          <h2>Çıkış Kamerası</h2>
          <div className="manager-panel-body" />
        </article>

        <article className="manager-panel">
          <h2>Son Giriş Yapan Araçlar</h2>
          <div className="manager-panel-body" />
        </article>

        <article className="manager-panel">
          <h2>Son Çıkış Yapan Araçlar</h2>
          <div className="manager-panel-body" />
        </article>

      </section>
    </>
  )
}


export default AdminDashboardPage
