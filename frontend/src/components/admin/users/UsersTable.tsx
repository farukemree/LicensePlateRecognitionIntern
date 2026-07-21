type User = {
  id: string
  fullName: string
  username: string
  role: string
  status: string
}

type Props = {
  users: User[]
  selectedId: string | null
  onSelect: (id: string) => void
}

function UsersTable({
  users,
  selectedId,
  onSelect,
}: Props) {
  return (
    <div className="expected-table-card">
      <table>
        <thead>
          <tr>
            <th>Ad Soyad</th>
            <th>Kullanıcı Adı</th>
            <th>Rol</th>
            <th>Durum</th>
          </tr>
        </thead>

        <tbody>
          {users.length === 0 ? (
            <tr>
              <td
                colSpan={4}
                style={{
                  textAlign: 'center',
                  padding: '40px',
                  color: '#777',
                }}
              >
                Henüz kullanıcı bulunmuyor.
              </td>
            </tr>
          ) : (
            users.map((user) => (
              <tr
                key={user.id}
                className={
                  selectedId === user.id
                    ? 'selected'
                    : ''
                }
                onClick={() => onSelect(user.id)}
              >
                <td>{user.fullName}</td>

                <td>{user.username}</td>

                <td>{user.role}</td>

                <td>{user.status}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

export default UsersTable