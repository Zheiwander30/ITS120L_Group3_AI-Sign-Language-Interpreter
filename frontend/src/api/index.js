/**
 * KamAI API client
 * Attaches Firebase Auth JWT automatically to every request.
 * Set VITE_API_URL=http://localhost:8000 in frontend/.env
 */
import { auth } from '../firebase'

const BASE = import.meta.env.VITE_API_URL ?? 'https://kamai.up.railway.app/'

async function getToken() {
  const user = auth.currentUser
  if (!user) throw new Error('Not authenticated')
  return user.getIdToken()
}

async function request(method, path, body) {
  const token = await getToken()
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Authorization:  `Bearer ${token}`,
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `API error ${res.status}`)
  }
  return res.json()
}

// ── Profile ──────────────────────────────────────────────────────────────────
export const getProfile    = ()     => request('GET',   '/users/me')
export const updateProfile = (data) => request('PATCH', '/users/me', data)

export async function uploadAvatar(file) {
  const token = await getToken()
  const form  = new FormData()
  form.append('photo', file)
  const res = await fetch(`${BASE}/users/me/photo`, {
    method:  'POST',
    headers: { Authorization: `Bearer ${token}` },
    body:    form,                                  // NO Content-Type header — browser sets multipart boundary
  })
  if (!res.ok) {
    const e = await res.json().catch(() => ({}))
    throw new Error(e.detail ?? `Upload failed: ${res.status}`)
  }
  return res.json()   // { photo_url: '...' }
}

// ── Sessions ─────────────────────────────────────────────────────────────────
export const getSessions   = (page = 1, limit = 20) => request('GET',    `/sessions?page=${page}&limit=${limit}`)
export const createSession = (feature)               => request('POST',   '/sessions', { feature })
export const updateSession = (id, data)              => request('PATCH',  `/sessions/${id}`, data)
export const deleteSession = (id)                    => request('DELETE', `/sessions/${id}`)

// ── Stats ─────────────────────────────────────────────────────────────────────
export const getStats = () => request('GET', '/sessions/stats')

// ── Payments / Subscriptions ──────────────────────────────────────────────────
export const getMySubscription  = ()                    => request('GET',  '/payments/my-subscription')
export const createCheckout     = (tier, billingPeriod) => request('POST', '/payments/checkout', { tier, billing_period: billingPeriod })
export const verifyPayment      = (linkId, tier, period) =>
  request('GET', `/payments/success?link_id=${encodeURIComponent(linkId)}&tier=${tier}&period=${period}`)

// ── Autocomplete ──────────────────────────────────────────────────────────────
export async function getSuggestions(prefix, limit = 6) {
  if (!prefix || prefix.length < 2) return []
  // Include auth token if logged in so custom vocab words are merged in
  const headers = {}
  try {
    const token = await getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  } catch {}
  const res = await fetch(
    `${BASE}/autocomplete?q=${encodeURIComponent(prefix.toLowerCase())}&limit=${limit}`,
    { headers }
  )
  if (!res.ok) return []
  const { suggestions } = await res.json()
  return suggestions
}

// ── Custom Vocabulary ─────────────────────────────────────────────────────────
export const getVocab      = (params = '') => request('GET',    `/vocabulary${params ? '?' + params : ''}`)
export const addVocabWord  = (data)        => request('POST',   '/vocabulary', data)
export const updateVocabWord = (id, data)  => request('PATCH',  `/vocabulary/${id}`, data)
export const deleteVocabWord = (id)        => request('DELETE', `/vocabulary/${id}`)
export const markVocabUsed   = (id)        => request('POST',   `/vocabulary/${id}/use`)
