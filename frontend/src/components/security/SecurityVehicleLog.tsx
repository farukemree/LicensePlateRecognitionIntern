import DirectionsCarOutlinedIcon from '@mui/icons-material/DirectionsCarOutlined'
import CheckCircleOutlineOutlinedIcon from '@mui/icons-material/CheckCircleOutlineOutlined'
import HourglassTopOutlinedIcon from '@mui/icons-material/HourglassTopOutlined'
import ErrorOutlineOutlinedIcon from '@mui/icons-material/ErrorOutlineOutlined'
import type { ReactNode } from 'react'

type VehicleStatus = 'success' | 'waiting' | 'blocked'

type VehicleLog = {
  time: string
  plate: string
  vehicleType: string
  status: VehicleStatus
}

type Props = {
  title: string
  rows: VehicleLog[]
}

const statusConfig = {
  success: {
    className: 'status-success',
    icon: <CheckCircleOutlineOutlinedIcon />,
    label: 'Giriş Başarılı',
  },
  waiting: {
    className: 'status-waiting',
    icon: <HourglassTopOutlinedIcon />,
    label: 'Kayıt Bekliyor',
  },
  blocked: {
    className: 'status-blocked',
    icon: <ErrorOutlineOutlinedIcon />,
    label: 'Kara Listede',
  },
} satisfies Record<
  VehicleStatus,
  {
    className: string
    icon: ReactNode
    label: string
  }
>

function SecurityVehicleLog({
  title,
  rows,
}: Props) {
  return (
    <section className="dashboard-panel log-panel">
      <header>{title}</header>

      <table>
        <thead>
          <tr>
            <th>Saat</th>
            <th>Plaka</th>
            <th>Araç Tipi</th>
            <th>Durum</th>
          </tr>
        </thead>

        <tbody>
          {rows.map((row) => {
            const status = statusConfig[row.status]

            return (
              <tr key={`${row.time}-${row.plate}`}>
                <td>{row.time}</td>

                <td>
                  <span className="plate-cell">
                    <DirectionsCarOutlinedIcon />
                    {row.plate}
                  </span>
                </td>

                <td>{row.vehicleType}</td>

                <td>
                  <span className={`status-badge ${status.className}`}>
                    {status.icon}
                    {status.label}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}

export default SecurityVehicleLog