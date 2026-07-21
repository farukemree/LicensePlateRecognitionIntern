import SearchOutlinedIcon from '@mui/icons-material/SearchOutlined'
import FilterListOutlinedIcon from '@mui/icons-material/FilterListOutlined'

type Props = {
  userCount: number
}

function UserToolbar({ userCount }: Props) {
  return (
    <>
      <div className="expected-heading">
        <div>
          <h2>Kullanıcı Yönetimi</h2>

          <p>
            Sistem kullanıcılarını görüntüleyin,
            düzenleyin ve yönetin.
          </p>
        </div>

        <button
          className="expected-primary"
          type="button"
        >
          + Yeni Kullanıcı
        </button>
      </div>

      <div className="expected-toolbar">
        <label className="expected-search">
          <SearchOutlinedIcon />

          <input
            type="search"
            placeholder="Kullanıcı Ara..."
          />
        </label>

        <button
          className="expected-filter"
          type="button"
        >
          <FilterListOutlinedIcon />
          Filtre
        </button>

        <strong>
          Toplam: {userCount} Kullanıcı
        </strong>
      </div>
    </>
  )
}

export default UserToolbar