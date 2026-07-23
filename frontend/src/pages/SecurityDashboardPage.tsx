import { useState } from 'react'
import type { ReactNode } from 'react'
import BlockOutlinedIcon from '@mui/icons-material/BlockOutlined'
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined'
import LocalShippingOutlinedIcon from '@mui/icons-material/LocalShippingOutlined'
import DashboardLayout from '../components/layout/DashboardLayout'
import SecurityPanelHome from '../components/security/SecurityPanelHome'
import SecuritySectionPlaceholder from '../components/security/SecuritySectionPlaceholder'
import { useDashboardData } from '../lib/dashboardData'

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
    <DashboardLayout
      activeSection={activeSection}
      ariaLabel="Plaka Tanıma Sistemi güvenlik ekranı"
      menuAriaLabel="Güvenlik görevlisi menüsü"
      menuItems={securityMenuItems}
      menuOpen={menuOpen}
      onMenuToggle={() => setMenuOpen((current) => !current)}
      onSectionChange={setActiveSection}
      pageClassName="dashboard-page"
      roleLabel="Güvenlik Görevlisi"
      userName={currentUserName}
    >
      <section className="security-main manager-main">
        {activeSection === 'Ana Menü' && (
          <SecurityPanelHome entryLogs={entryLogs} exitLogs={exitLogs} />
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
    </DashboardLayout>
  )
}

export default SecurityDashboardPage
