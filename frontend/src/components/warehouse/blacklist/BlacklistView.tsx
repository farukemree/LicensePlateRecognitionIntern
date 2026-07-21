import { useState } from 'react'

import BlacklistToolbar from './BlacklistToolbar'
import ActiveBlacklistTable from './ActiveBlacklistTable'
import BlacklistRequestTable from './BlacklistRequestTable'
import ActiveBlacklistDetail from './ActiveBlacklistDetail'
import BlacklistRequestDetail from './BlacklistRequestDetail'

export type ActiveBlacklistVehicle = {
  id: string
  plate: string
  company: string
  vehicleType: string
  reason: string
  addedDate: string
  addedBy: string
  status: string
  description: string
}

export type BlacklistRequest = {
  id: string
  plate: string
  company: string
  vehicleType: string
  requester: string
  requestDate: string
  status: string
  securityNote: string
}

type Props = {
  activeVehicles: ActiveBlacklistVehicle[]
  requests: BlacklistRequest[]
}

function BlacklistView({
  activeVehicles,
  requests,
}: Props) {
  const [activeTab, setActiveTab] =
    useState<'active' | 'requests'>('active')

  const [selectedActiveId, setSelectedActiveId] =
    useState<string | null>(null)

  const [selectedRequestId, setSelectedRequestId] =
    useState<string | null>(null)

  const selectedActiveVehicle = activeVehicles.find(
    (vehicle) => vehicle.id === selectedActiveId
  )

  const selectedRequest = requests.find(
    (request) => request.id === selectedRequestId
  )

  const isActiveList = activeTab === 'active'

  return (
    <section className="blacklist-page">
      <BlacklistToolbar
        activeTab={activeTab}
        activeCount={activeVehicles.length}
        requestCount={requests.length}
        onTabChange={setActiveTab}
      />

      <div className="blacklist-workspace">
        <div className="blacklist-table-card">
          {isActiveList ? (
            <ActiveBlacklistTable
              vehicles={activeVehicles}
              selectedId={selectedActiveId}
              onSelect={setSelectedActiveId}
            />
          ) : (
            <BlacklistRequestTable
              requests={requests}
              selectedId={selectedRequestId}
              onSelect={setSelectedRequestId}
            />
          )}
        </div>

        <aside className="blacklist-detail-card">
          {isActiveList ? (
            <ActiveBlacklistDetail
              vehicle={selectedActiveVehicle}
            />
          ) : (
            <BlacklistRequestDetail
              request={selectedRequest}
            />
          )}
        </aside>
      </div>
    </section>
  )
}

export default BlacklistView