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
  vehicle?: ActiveBlacklistVehicle
}

function ActiveBlacklistDetail({
  vehicle,
}: Props) {
  if (!vehicle) {
    return (
      <>
        <h3>Araç Bilgileri</h3>
        <p>
          Detaylarını görmek için
          tablodan bir araç seçin.
        </p>
      </>
    )
  }

  return (
    <>
      <h3>Araç Bilgileri</h3>

      <dl>
        <div>
          <dt>Plaka</dt>
          <dd>{vehicle.plate}</dd>
        </div>

        <div>
          <dt>Firma</dt>
          <dd>{vehicle.company}</dd>
        </div>

        <div>
          <dt>Araç Tipi</dt>
          <dd>{vehicle.vehicleType}</dd>
        </div>

        <div>
          <dt>Kara Liste Nedeni</dt>
          <dd>{vehicle.reason}</dd>
        </div>

        <div>
          <dt>Eklenme Tarihi</dt>
          <dd>{vehicle.addedDate}</dd>
        </div>

        <div>
          <dt>Ekleyen</dt>
          <dd>{vehicle.addedBy}</dd>
        </div>

        <div>
          <dt>Açıklama</dt>
          <dd>{vehicle.description}</dd>
        </div>
      </dl>

      <button
        className="blacklist-remove-button"
        type="button"
      >
        Listeden Çıkar
      </button>
    </>
  )
}

export default ActiveBlacklistDetail