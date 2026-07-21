type ApiEnvelope<T> = {
  success: boolean
  data?: T
  error?: {
    code: string
    message: string
  }
}

export type ExpectedArrivalDto = {
  id: string
  depot_id: string
  plaka: string
  beklenen_zaman: string
  durum: string
  created_at: string
}

export type BlacklistDto = {
  id: string
  tip: string
  ref_id: string
  sebep: string
  eklenen_yetkili_id?: string
  created_at: string
  aktif: boolean
}

export type VehicleLogDto = {
  id: string
  depot_id: string
  vehicle_id: string
  driver_id?: string
  user_id?: string
  yon: 'giris' | 'cikis'
  tasimacilik_sirketi?: string
  tarih: string
  aciklama?: string
  created_at: string
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
const healthUrl = import.meta.env.VITE_BACKEND_HEALTH_URL ?? '/healthz'

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('access_token')

  return token
    ? {
        Authorization: `Bearer ${token}`,
      }
    : {}
}

async function request<T>(path: string) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: authHeaders(),
  })
  const envelope = (await response.json()) as ApiEnvelope<T>

  if (!response.ok || !envelope.success) {
    throw new Error(envelope.error?.message ?? 'API istegi basarisiz oldu')
  }

  return envelope.data as T
}

export async function checkBackendHealth() {
  const response = await fetch(healthUrl)
  const envelope = (await response.json()) as ApiEnvelope<{ status: string }>

  if (!response.ok || !envelope.success) {
    throw new Error(envelope.error?.message ?? 'Backend saglik kontrolu basarisiz oldu')
  }

  return envelope.data
}

export const api = {
  listExpectedArrivals: () => request<ExpectedArrivalDto[]>('/expected-arrivals'),
  listBlacklist: () => request<BlacklistDto[]>('/blacklist'),
  listVehicleLogs: () => request<VehicleLogDto[]>('/vehicle-logs'),
}
