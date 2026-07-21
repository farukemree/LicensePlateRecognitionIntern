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
  request?: BlacklistRequest
}

function BlacklistRequestDetail({
  request,
}: Props) {
  if (!request) {
    return (
      <>
        <h3>Talep Bilgileri</h3>
        <p>
          Detaylarını görmek için tablodan
          bir talep seçin.
        </p>
      </>
    )
  }

  return (
    <>
      <h3>🚚 Araç Bilgileri</h3>

      <dl>
        <div>
          <dt>Plaka</dt>
          <dd>{request.plate}</dd>
        </div>

        <div>
          <dt>Firma</dt>
          <dd>{request.company}</dd>
        </div>

        <div>
          <dt>Araç Tipi</dt>
          <dd>{request.vehicleType}</dd>
        </div>
      </dl>

      <div className="blacklist-detail-divider" />

      <h3>👮 Talep Eden</h3>
      <p>{request.requester}</p>

      <div className="blacklist-detail-divider" />

      <h3>📝 Güvenlik Görevlisi Açıklaması</h3>
      <p>{request.securityNote}</p>

      <div className="blacklist-detail-divider" />

      <h3>🎥 Kamera Kaydı</h3>
      <div className="blacklist-video-preview">
        Video Önizleme
      </div>

      <div className="blacklist-detail-divider" />

      <label className="blacklist-manager-note">
        Yönetici Notu
        <textarea />
      </label>

      <div className="blacklist-request-actions">
        <button
          className="approve"
          type="button"
        >
          Onayla
        </button>

        <button
          className="reject"
          type="button"
        >
          Reddet
        </button>
      </div>
    </>
  )
}

export default BlacklistRequestDetail