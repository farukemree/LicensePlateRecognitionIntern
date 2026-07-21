type ExpectedVehicle = {
  id: string
  plate: string
  company: string
  vehicleType: string
  expectedTime: string
  status: string
}

type VehicleDetailCardProps = {
  vehicle?: ExpectedVehicle
}

function VehicleDetailCard({
  vehicle,
}: VehicleDetailCardProps) {
  return (
    <aside className="expected-detail-card">
      <h3>Araç Bilgileri</h3>

      {vehicle ? (
        <>
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
              <dt>Beklenen Saat</dt>
              <dd>{vehicle.expectedTime}</dd>
            </div>

            <div>
              <dt>Durum</dt>
              <dd>{vehicle.status}</dd>
            </div>
          </dl>

          <div className="expected-detail-actions">
            <button
              className="edit"
              type="button"
            >
              Düzenle
            </button>

            <button
              className="delete"
              type="button"
            >
              Sil
            </button>
          </div>
        </>
      ) : (
        <p>
          Detaylarını görmek için tablodan
          bir araç seçin.
        </p>
      )}
    </aside>
  )
}

export default VehicleDetailCard