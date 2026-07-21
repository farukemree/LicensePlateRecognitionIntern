import SecurityCameraFeed from './SecurityCameraFeed'
import SecurityVehicleLog from './SecurityVehicleLog'

type VehicleStatus = 'success' | 'waiting' | 'blocked'

type VehicleLog = {
  time: string
  plate: string
  vehicleType: string
  status: VehicleStatus
}
type Props = {
  entryLogs: VehicleLog[]
  exitLogs: VehicleLog[]
}

function SecurityPanelHome({
  entryLogs,
  exitLogs,
}: Props) {
  return (
    <section className="dashboard-content">
      <div className="camera-grid">
        <SecurityCameraFeed title="Giriş Kapısı" active />
        <SecurityCameraFeed title="Çıkış Kapısı" />
      </div>

      <div className="log-grid">
        <SecurityVehicleLog
          title="Son Giriş Yapan Araçlar"
          rows={entryLogs}
        />

        <SecurityVehicleLog
          title="Son Çıkış Yapan Araçlar"
          rows={exitLogs}
        />
      </div>
    </section>
  )
}

export default SecurityPanelHome