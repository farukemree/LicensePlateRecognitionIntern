import AddIcon from '@mui/icons-material/Add'
import UploadFileOutlinedIcon from '@mui/icons-material/UploadFileOutlined'
import SearchOutlinedIcon from '@mui/icons-material/SearchOutlined'
import FilterListOutlinedIcon from '@mui/icons-material/FilterListOutlined'

type Props = {
  vehicleCount: number
  filtersOpen: boolean
  onToggleFilters: () => void
}

function ExpectedToolbar({
  vehicleCount,
  filtersOpen,
  onToggleFilters,
}: Props) {
  return (
    <>
      <div className="expected-heading">
        <div>
          <h2>Beklenen Araçlar</h2>

          <p>
            Planlanan araç girişlerini yönetin ve
            toplu araç ekleme işlemlerini
            gerçekleştirin.
          </p>
        </div>

        <div className="expected-actions">
          <button
            className="expected-primary"
            type="button"
          >
            <AddIcon />
            Yeni Araç
          </button>

          <button
            className="expected-upload"
            type="button"
          >
            <UploadFileOutlinedIcon />
            Excel Yükle
          </button>
        </div>
      </div>

      <div className="expected-toolbar">
        <label className="expected-search">
          <SearchOutlinedIcon />
          <input
            type="search"
            placeholder="Plaka Ara..."
          />
        </label>

        <div className="expected-filter-wrap">
          <button
            className="expected-filter"
            type="button"
            aria-expanded={filtersOpen}
            onClick={onToggleFilters}
          >
            <FilterListOutlinedIcon />
            Filtre
          </button>
        </div>

        <strong>
          Toplam: {vehicleCount} Kayıt
        </strong>
      </div>
    </>
  )
}

export default ExpectedToolbar