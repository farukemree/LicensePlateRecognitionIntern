import { useState } from 'react'

import UserToolbar from './UserToolbar'
import UsersTable from './UsersTable'
import UserDetailCard from './UserDetailCard'

export type User = {
  id: string
  fullName: string
  username: string
  role: string
  status: string
}

type Props = {
  users: User[]
}

function UserManagementView({ users }: Props) {
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)

  const selectedUser = users.find(
    (user) => user.id === selectedUserId
  )

  return (
    <section className="expected-page">
      <UserToolbar userCount={users.length} />

      <div className="expected-workspace">
        <UsersTable
          users={users}
          selectedId={selectedUserId}
          onSelect={setSelectedUserId}
        />

        <UserDetailCard
          user={selectedUser}
        />
      </div>
    </section>
  )
}

export default UserManagementView