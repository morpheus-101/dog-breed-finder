// POSTs to /recommend. In development, VITE_API_URL is unset so this hits the
// Vite proxy (see vite.config.js), which forwards to http://localhost:8001. In
// production, VITE_API_URL points at the deployed backend. Request/response
// shapes are defined in skills/api-contract.md.

const API_BASE_URL = import.meta.env.VITE_API_URL || ''

export async function fetchRecommendations(requestBody) {
  const response = await fetch(`${API_BASE_URL}/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody),
  })

  if (!response.ok) {
    if (response.status === 429) {
      throw new Error('rate_limited')
    }
    throw new Error(`Request failed with status ${response.status}`)
  }

  return response.json()
}
