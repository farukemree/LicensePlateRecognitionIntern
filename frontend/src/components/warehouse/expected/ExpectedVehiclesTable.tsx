type ExpectedVehicle = {
  id: string
  plate: string
  company: string
  vehicleType: string
  expectedTime: string
  status: string
}

type ExpectedVehiclesTableProps = {
  vehicles: ExpectedVehicle[]
  selectedVehicleId: string | null
  onSelectVehicle: (id: string) => void
}

function ExpectedVehiclesTable({
  vehicles,
  selectedVehicleId,
  onSelectVehicle,
}: ExpectedVehiclesTableProps) {
  return (
    <div className="expected-table-card">
      <table>
        <thead>
          <tr>
            <th>Plaka</th>
            <th>Firma</th>
            <th>Araç Tipi</th>
            <th>Beklenen Saat</th>
            <th>Durum</th>
            <th>İşlem</th>
          </tr>
        </thead>

        <tbody>
          {vehicles.map((vehicle) => (
            <tr
              key={vehicle.id}
              className={
                vehicle.id === selectedVehicleId
                  ? 'selected'
                  : ''
              }
              onClick={() =>
                onSelectVehicle(vehicle.id)
              }
            >
              <td>{vehicle.plate}</td>
              <td>{vehicle.company}</td>
              <td>{vehicle.vehicleType}</td>
              <td>{vehicle.expectedTime}</td>
              <td>{vehicle.status}</td>
              <td>Detay</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default ExpectedVehiclesTable