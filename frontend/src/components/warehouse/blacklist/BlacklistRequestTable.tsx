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
  requests: BlacklistRequest[]
  selectedId: string | null
  onSelect: (id: string) => void
}

function BlacklistRequestTable({
  requests,
  selectedId,
  onSelect,
}: Props) {
  return (
    <table>
      <thead>
        <tr>
          <th>Plaka</th>
          <th>Talep Eden</th>
          <th>Talep Tarihi</th>
          <th>Durum</th>
        </tr>
      </thead>

      <tbody>
        {requests.map((request) => (
          <tr
            key={request.id}
            className={
              request.id === selectedId
                ? 'selected'
                : ''
            }
            onClick={() => onSelect(request.id)}
          >
            <td>{request.plate}</td>
            <td>{request.requester}</td>
            <td>{request.requestDate}</td>
            <td>{request.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default BlacklistRequestTable