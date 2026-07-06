// GETs /breed/{breed_name}. In development this hits the Vite proxy (see
// vite.config.js), which forwards to http://localhost:8001. Request/response
// shapes are defined in skills/api-contract.md.

const API_BASE_URL = import.meta.env.VITE_API_URL || ''

export async function fetchBreed(breedName) {
  const response = await fetch(`${API_BASE_URL}/breed/${encodeURIComponent(breedName)}`)

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('not_found')
    }
    throw new Error(`Request failed with status ${response.status}`)
  }

  return response.json()
}
