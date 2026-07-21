type Props = {
  activeTab: 'active' | 'requests'
  activeCount: number
  requestCount: number
  onTabChange: (tab: 'active' | 'requests') => void
}

function BlacklistToolbar({
  activeTab,
  activeCount,
  requestCount,
  onTabChange,
}: Props) {
  return (
    <div
      className="blacklist-tabs"
      role="tablist"
      aria-label="Kara liste görünümü"
    >
      <button
        className={activeTab === 'active' ? 'active' : ''}
        type="button"
        role="tab"
        aria-selected={activeTab === 'active'}
        onClick={() => onTabChange('active')}
      >
        Aktif Kara Liste ({activeCount})
      </button>

      <button
        className={activeTab === 'requests' ? 'active' : ''}
        type="button"
        role="tab"
        aria-selected={activeTab === 'requests'}
        onClick={() => onTabChange('requests')}
      >
        Bekleyen Talepler ({requestCount})
      </button>
    </div>
  )
}

export default BlacklistToolbar