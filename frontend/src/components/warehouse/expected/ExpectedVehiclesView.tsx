import { useState } from 'react'

import ExpectedToolbar from './ExpectedToolbar'
import ExpectedVehiclesTable from './ExpectedVehiclesTable'
import VehicleDetailCard from './VehicleDetailCard'

export type ExpectedVehicle = {
  id: string
  plate: string
  company: string
  vehicleType: string
  expectedTime: string
  status: string
}

type Props = {
  vehicles: ExpectedVehicle[]
}

function ExpectedVehiclesView({
  vehicles,
}: Props) {
  const [selectedVehicleId, setSelectedVehicleId] =
    useState<string | null>(null)

  const [filtersOpen, setFiltersOpen] =
    useState(false)

  const selectedVehicle = vehicles.find(
    (vehicle) => vehicle.id === selectedVehicleId
  )

  return (
    <section
      className="expected-page"
      aria-label="Beklenen Araçlar"
    >
      <ExpectedToolbar
        vehicleCount={vehicles.length}
        filtersOpen={filtersOpen}
        onToggleFilters={() =>
          setFiltersOpen((current) => !current)
        }
      />

      <div className="expected-workspace">
        <ExpectedVehiclesTable
          vehicles={vehicles}
          selectedVehicleId={selectedVehicleId}
          onSelectVehicle={setSelectedVehicleId}
        />

        <VehicleDetailCard
          vehicle={selectedVehicle}
        />
      </div>
    </section>
  )
}

export default ExpectedVehiclesView