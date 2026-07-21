type User = {
  id: string
  fullName: string
  username: string
  role: string
  status: string
}

type Props = {
  user?: User
}

function UserDetailCard({ user }: Props) {
  if (!user) {
    return (
      <aside className="expected-detail-card">
        <h3>Kullanıcı Bilgileri</h3>

        <p>
          Detaylarını görmek için tablodan bir kullanıcı seçin.
        </p>

        <div className="expected-detail-actions">
          <button
            className="expected-secondary"
            type="button"
            disabled
          >
            Düzenle
          </button>

          <button
            className="expected-danger"
            type="button"
            disabled
          >
            Pasife Al
          </button>
        </div>
      </aside>
    )
  }

  return (
    <aside className="expected-detail-card">
      <h3>Kullanıcı Bilgileri</h3>

      <dl className="expected-detail-list">
        <div>
          <dt>Ad Soyad</dt>
          <dd>{user.fullName}</dd>
        </div>

        <div>
          <dt>Kullanıcı Adı</dt>
          <dd>{user.username}</dd>
        </div>

        <div>
          <dt>Rol</dt>
          <dd>{user.role}</dd>
        </div>

        <div>
          <dt>Durum</dt>
          <dd>{user.status}</dd>
        </div>
      </dl>

      <div className="expected-detail-actions">
        <button
          className="expected-secondary"
          type="button"
        >
          Düzenle
        </button>

        <button
          className="expected-danger"
          type="button"
        >
          Pasife Al
        </button>
      </div>
    </aside>
  )
}

export default UserDetailCard