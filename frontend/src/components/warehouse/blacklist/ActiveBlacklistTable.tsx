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

type Props = {
  vehicles: ActiveBlacklistVehicle[]
  selectedId: string | null
  onSelect: (id: string) => void
}

function ActiveBlacklistTable({
  vehicles,
  selectedId,
  onSelect,
}: Props) {
  return (
    <table>
      <thead>
        <tr>
          <th>Plaka</th>
          <th>Firma</th>
          <th>Kara Liste Nedeni</th>
          <th>Eklenme Tarihi</th>
          <th>Durum</th>
        </tr>
      </thead>

      <tbody>
        {vehicles.map((vehicle) => (
          <tr
            key={vehicle.id}
            className={
              vehicle.id === selectedId
                ? 'selected'
                : ''
            }
            onClick={() => onSelect(vehicle.id)}
          >
            <td>{vehicle.plate}</td>
            <td>{vehicle.company}</td>
            <td>{vehicle.reason}</td>
            <td>{vehicle.addedDate}</td>
            <td>{vehicle.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default ActiveBlacklistTable