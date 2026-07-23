import { useState } from 'react'
import type { ReactNode } from 'react'
import BlockOutlinedIcon from '@mui/icons-material/BlockOutlined'
import CalendarMonthOutlinedIcon from '@mui/icons-material/CalendarMonthOutlined'
import DirectionsCarOutlinedIcon from '@mui/icons-material/DirectionsCarOutlined'
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined'
import LocalShippingOutlinedIcon from '@mui/icons-material/LocalShippingOutlined'
import VideocamOutlinedIcon from '@mui/icons-material/VideocamOutlined'
import WarehouseOutlinedIcon from '@mui/icons-material/WarehouseOutlined'
import DashboardLayout from '../components/layout/DashboardLayout'
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
    <DashboardLayout
      activeSection={activeSection}
      ariaLabel="Depo yöneticisi ekranı"
      menuAriaLabel="Depo yöneticisi menüsü"
      menuItems={managerMenuItems}
      menuOpen={menuOpen}
      onMenuToggle={() => setMenuOpen((current) => !current)}
      onSectionChange={setActiveSection}
      roleLabel="Depo Yöneticisi"
      userName={currentUserName}
    >
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
    </DashboardLayout>
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
