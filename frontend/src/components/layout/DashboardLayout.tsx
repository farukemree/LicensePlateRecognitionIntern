import type { ReactNode } from 'react'
import AccountCircleOutlinedIcon from '@mui/icons-material/AccountCircleOutlined'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import LogoutOutlinedIcon from '@mui/icons-material/LogoutOutlined'
import MenuOutlinedIcon from '@mui/icons-material/MenuOutlined'
import NotificationsNoneOutlinedIcon from '@mui/icons-material/NotificationsNoneOutlined'
import dhlLogo from '../../assets/dhl-logo.png'

export type DashboardMenuItem<T extends string> = {
  icon: ReactNode
  label: T
}

type DashboardLayoutProps<T extends string> = {
  activeSection: T
  ariaLabel: string
  children: ReactNode
  menuAriaLabel: string
  menuItems: DashboardMenuItem<T>[]
  menuOpen: boolean
  onMenuToggle: () => void
  onSectionChange: (section: T) => void
  pageClassName?: string
  roleLabel: string
  title?: string
  userName: string
}

function DashboardLayout<T extends string>({
  activeSection,
  ariaLabel,
  children,
  menuAriaLabel,
  menuItems,
  menuOpen,
  onMenuToggle,
  onSectionChange,
  pageClassName = 'manager-page',
  roleLabel,
  title = 'Plaka Tanıma Sistemi',
  userName,
}: DashboardLayoutProps<T>) {
  return (
    <main className={`${pageClassName}${menuOpen ? ' sidebar-active' : ''}`} aria-label={ariaLabel}>
      <header className="manager-header">
        <div className="manager-brand">
          <img className="manager-logo" src={dhlLogo} alt="DHL" />
          <button
            className="manager-menu-toggle"
            type="button"
            aria-label="Menüyü aç veya kapat"
            aria-expanded={menuOpen}
            onClick={onMenuToggle}
          >
            <MenuOutlinedIcon />
          </button>
          <h1>{title}</h1>
        </div>

        <div className="manager-user-actions">
          <button className="manager-icon-button" type="button" aria-label="Bildirimler">
            <NotificationsNoneOutlinedIcon />
          </button>
          <button className="manager-profile manager-profile-transfer" type="button">
            <AccountCircleOutlinedIcon />
            <span>{userName}</span>
            <KeyboardArrowDownIcon />
          </button>
        </div>
      </header>

      <div className={`manager-layout${menuOpen ? ' menu-open' : ''}`}>
        {menuOpen && (
          <aside className="manager-sidebar" aria-label={menuAriaLabel}>
            <nav className="manager-sidebar-nav">
              {menuItems.map((item) => (
                <button
                  key={item.label}
                  type="button"
                  className={`manager-sidebar-item${item.label === activeSection ? ' active' : ''}`}
                  onClick={() => onSectionChange(item.label)}
                >
                  <span>{item.icon}</span>
                  {item.label}
                </button>
              ))}
            </nav>

            <div className="manager-sidebar-profile">
              <div className="manager-sidebar-user">
                <AccountCircleOutlinedIcon />
                <div>
                  <strong>{userName}</strong>
                  <span>{roleLabel}</span>
                </div>
              </div>
              <button className="manager-sidebar-action logout" type="button">
                <LogoutOutlinedIcon />
                Çıkış Yap
              </button>
            </div>
          </aside>
        )}

        {children}
      </div>
    </main>
  )
}

export default DashboardLayout
