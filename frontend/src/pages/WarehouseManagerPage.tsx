import { useState } from 'react'
import type { ReactNode } from 'react'
import AccountCircleOutlinedIcon from '@mui/icons-material/AccountCircleOutlined'
import BlockOutlinedIcon from '@mui/icons-material/BlockOutlined'
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined'
import DirectionsCarOutlinedIcon from '@mui/icons-material/DirectionsCarOutlined'
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import LocalShippingOutlinedIcon from '@mui/icons-material/LocalShippingOutlined'
import MenuOutlinedIcon from '@mui/icons-material/MenuOutlined'
import NotificationsNoneOutlinedIcon from '@mui/icons-material/NotificationsNoneOutlined'
import VideocamOutlinedIcon from '@mui/icons-material/VideocamOutlined'
import WarehouseOutlinedIcon from '@mui/icons-material/WarehouseOutlined'
import dhlLogo from '../assets/dhl-logo.png'
import ExpectedVehiclesView from '../components/warehouse/expected/ExpectedVehiclesView'

import BlacklistView from '../components/warehouse/blacklist/BlacklistView'
import { useDashboardData } from '../lib/dashboardData'
type ManagerSection =
  | 'Ana Menü'
  | 'Beklenen Araçlar'
  | 'Kara Liste'

const managerMenuItems: Array<{ icon: ReactNode; label: ManagerSection }> = [
  { icon: <HomeOutlinedIcon />, label: 'Ana Menü' },
  { icon: <LocalShippingOutlinedIcon />, label: 'Beklenen Araçlar' },
  { icon: <BlockOutlinedIcon />, label: 'Kara Liste' },
]

const statCards = [
  {
    accent: 'orange',
    icon: <DirectionsCarOutlinedIcon />,
    title: 'Bugünkü araç hareketi',
  },
  {
    accent: 'yellow',
    icon: <CalendarMonthOutlinedIcon />,
    title: 'Bugün planlanan girişler',
  },
  {
    accent: 'blue',
    icon: <WarehouseOutlinedIcon />,
    title: 'Depoda bulunan araçlar',
  },
  {
    accent: 'green',
    icon: <VideocamOutlinedIcon />,
    title: 'Aktif Kamera',
  },
]

function WarehouseManagerPage() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [activeSection, setActiveSection] = useState<ManagerSection>('Ana Menü')
  const { expectedVehicles, activeBlacklistVehicles, blacklistRequests } = useDashboardData()
  const currentUserName = 'Beyza Bora'

  return (
    <main className="manager-page" aria-label="Depo yöneticisi ekranı">
      <header className="manager-header">
        <div className="manager-brand">
          <img className="manager-logo" src={dhlLogo} alt="DHL" />
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
          <button className="manager-icon-button" type="button" aria-label="Bildirimler">
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
          <aside className="manager-sidebar" aria-label="Depo yöneticisi menüsü">
            {managerMenuItems.map((item) => (
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

        <section className="manager-main">
          {activeSection === 'Ana Menü' && <DashboardOverview />}
          {activeSection === 'Beklenen Araçlar' && (
            <ExpectedVehiclesView vehicles={expectedVehicles} />
          )}
          {activeSection === 'Kara Liste' && (
            <BlacklistView activeVehicles={activeBlacklistVehicles} requests={blacklistRequests} />
          )}
          {activeSection !== 'Ana Menü' &&
            activeSection !== 'Beklenen Araçlar' &&
            activeSection !== 'Kara Liste' && (
            <ManagerSectionPlaceholder title={activeSection} />
          )}
        </section>
      </div>
    </main>
  )
}

function DashboardOverview() {
  return (
    <>
      <section className="manager-stats" aria-label="Depo özet kartları">
        {statCards.map((card) => (
          <article className={`manager-stat-card ${card.accent}`} key={card.title}>
            <div className="manager-stat-title">
              <span>{card.icon}</span>
              <strong>{card.title}</strong>
            </div>
          </article>
        ))}
      </section>

      <section className="manager-panel-grid">
        <ManagerPanel title="Bekleyen Talepleri" actionLabel="Tümünü Gör →" />
        <ManagerPanel title="Planlanan Araçlar" actionLabel="Tümünü Gör →" />
        <ManagerPanel title="Giriş Kamerası" />
        <ManagerPanel title="Çıkış Kamerası" />
      </section>
    </>
  )
}

function ManagerPanel({ title, actionLabel }: { title: string; actionLabel?: string }) {
  return (
    <article className="manager-panel">
      <h2>{title}</h2>
      <div className="manager-panel-body" />
      {actionLabel && (
        <button className="manager-panel-action" type="button">
          {actionLabel}
        </button>
      )}
    </article>
  )
}

function ManagerSectionPlaceholder({ title }: { title: ManagerSection }) {
  return (
    <article className="manager-section-card">
      <h2>{title}</h2>
      <div className="manager-empty-state">Backend bağlantısı sonrası bu alan doldurulacak.</div>
    </article>
  )
}

export default WarehouseManagerPage
