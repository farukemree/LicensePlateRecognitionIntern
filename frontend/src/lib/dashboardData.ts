import { useEffect, useState } from 'react'
import { api } from './api'
import type { BlacklistDto, ExpectedArrivalDto, VehicleLogDto } from './api'
import type { ActiveBlacklistVehicle, BlacklistRequest } from '../components/warehouse/blacklist/BlacklistView'
import type { ExpectedVehicle } from '../components/warehouse/expected/ExpectedVehiclesView'

export type VehicleStatus = 'success' | 'waiting' | 'blocked'

export type VehicleLog = {
  time: string
  plate: string
  vehicleType: string
  status: VehicleStatus
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function mapExpectedArrival(item: ExpectedArrivalDto): ExpectedVehicle {
  return {
    id: item.id,
    plate: item.plaka,
    company: '-',
    vehicleType: '-',
    expectedTime: formatDateTime(item.beklenen_zaman),
    status: item.durum,
  }
}

function mapBlacklistItem(item: BlacklistDto): ActiveBlacklistVehicle {
  return {
    id: item.id,
    plate: item.tip === 'vehicle' ? item.ref_id : '-',
    company: '-',
    vehicleType: item.tip,
    reason: item.sebep,
    addedDate: formatDateTime(item.created_at),
    addedBy: item.eklenen_yetkili_id ?? '-',
    status: item.aktif ? 'Aktif' : 'Pasif',
    description: item.sebep,
  }
}

function mapVehicleLog(item: VehicleLogDto): VehicleLog {
  return {
    time: formatDateTime(item.tarih),
    plate: item.vehicle_id,
    vehicleType: item.tasimacilik_sirketi ?? '-',
    status: item.yon === 'giris' ? 'success' : 'waiting',
  }
}

export function useDashboardData() {
  const [expectedVehicles, setExpectedVehicles] = useState<ExpectedVehicle[]>([])
  const [activeBlacklistVehicles, setActiveBlacklistVehicles] = useState<ActiveBlacklistVehicle[]>([])
  const [blacklistRequests] = useState<BlacklistRequest[]>([])
  const [entryLogs, setEntryLogs] = useState<VehicleLog[]>([])
  const [exitLogs, setExitLogs] = useState<VehicleLog[]>([])

  useEffect(() => {
    let ignore = false

    async function load() {
      const [expected, blacklist, logs] = await Promise.allSettled([
        api.listExpectedArrivals(),
        api.listBlacklist(),
        api.listVehicleLogs(),
      ])

      if (ignore) {
        return
      }

      if (expected.status === 'fulfilled') {
        setExpectedVehicles(expected.value.map(mapExpectedArrival))
      }

      if (blacklist.status === 'fulfilled') {
        setActiveBlacklistVehicles(blacklist.value.map(mapBlacklistItem))
      }

      if (logs.status === 'fulfilled') {
        setEntryLogs(logs.value.filter((log) => log.yon === 'giris').map(mapVehicleLog))
        setExitLogs(logs.value.filter((log) => log.yon === 'cikis').map(mapVehicleLog))
      }
    }

    void load()

    return () => {
      ignore = true
    }
  }, [])

  return {
    expectedVehicles,
    activeBlacklistVehicles,
    blacklistRequests,
    entryLogs,
    exitLogs,
  }
}
