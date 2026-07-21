import { useState } from 'react'
import type { ReactNode } from 'react'
import LocalShippingOutlinedIcon from '@mui/icons-material/LocalShippingOutlined'
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined'
import BlockOutlinedIcon from '@mui/icons-material/BlockOutlined'
import SecuritySectionPlaceholder from '../components/security/SecuritySectionPlaceholder'
import SecurityPanelHome from '../components/security/SecurityPanelHome'
import { useDashboardData } from '../lib/dashboardData'
import AccountCircleOutlinedIcon from '@mui/icons-material/AccountCircleOutlined'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import MenuOutlinedIcon from '@mui/icons-material/MenuOutlined'
import NotificationsNoneOutlinedIcon from '@mui/icons-material/NotificationsNoneOutlined'

import dhlLogo from '../assets/dhl-logo.png'
type SecuritySection = 'Ana Menü' | 'Beklenen Araçlar' | 'Kara Liste'

type PlannedEntry = {
  time: string
  plate: string
  driver: string
  gate: string
}
type BlacklistVehicle = {
  plate: string
  reason: string
  addedAt: string
}
const blacklistVehicles: BlacklistVehicle[] = []

const plannedEntries: PlannedEntry[] = []

const securityMenuItems: Array<{ icon: ReactNode; label: SecuritySection }> = [
  { icon: <HomeOutlinedIcon />, label: 'Ana Menü' },
  { icon: <LocalShippingOutlinedIcon />, label: 'Beklenen Araçlar' },
  { icon: <BlockOutlinedIcon />, label: 'Kara Liste' },
]

function SecurityDashboardPage() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [activeSection, setActiveSection] = useState<SecuritySection>('Ana Menü')
  const { activeBlacklistVehicles, entryLogs, exitLogs } = useDashboardData()
  const currentUserName = 'Beyza Bora'

  return (
    <main className="dashboard-page" aria-label="Plaka Tanıma Sistemi güvenlik ekranı">
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
      aria-label="Menüyü aç veya kapat"
      aria-expanded={menuOpen}
      onClick={() => setMenuOpen((current) => !current)}
    >
      <MenuOutlinedIcon />
    </button>
  </div>

  <div className="manager-user-actions">
    <button
      className="manager-icon-button"
      type="button"
      aria-label="Bildirimler"
    >
      <NotificationsNoneOutlinedIcon />
    </button>

    <button className="manager-profile" type="button">
      <AccountCircleOutlinedIcon />
      <span>{currentUserName}</span>
      <KeyboardArrowDownIcon />
    </button>
  </div>
</header>
      <div className={`manager-layout${menuOpen ? ' menu-open' : ''}`}>
        {menuOpen && (
          <aside className="manager-sidebar" aria-label="Güvenlik görevlisi menüsü">
            {securityMenuItems.map((item) => (
              <button
                className={item.label === activeSection ? 'active' : ''}
                type="button"
                key={item.label}
                onClick={() => setActiveSection(item.label)}
              >
                <span>{item.icon}</span>
                {item.label}
              </button>
            ))}
          </aside>
        )}

        <section className="security-main">
          {activeSection === 'Ana Menü' && (
  <SecurityPanelHome
    entryLogs={entryLogs}
    exitLogs={exitLogs}
  />
)}
          {activeSection === 'Beklenen Araçlar' && (
            <SecuritySectionPlaceholder
              title="Beklenen Araçlar"
              message={
                 plannedEntries.length > 0
                  ? 'Beklenen araçlar burada listelenecek.'
                  : 'Beklenen araç bulunmuyor.'
              }
            />
          )}
          
          {activeSection === 'Kara Liste' && (
            <SecuritySectionPlaceholder
              title="Kara Liste"
              message={
                blacklistVehicles.length > 0
                  ? 'Kara liste kayıtları burada listelenecek.'
                  : activeBlacklistVehicles.length > 0
                    ? `${activeBlacklistVehicles.length} kara liste kaydı bulundu.`
                    : 'Kara listede araç bulunmuyor.'
              }
            />
          )}
        </section>
      </div>
    </main>
  )
}

export default SecurityDashboardPage
