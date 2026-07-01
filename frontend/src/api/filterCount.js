// POSTs to /filter-count with just hard_filters. Layer 1 only on the backend
// (no scoring, no Groq), used to show a live "N breeds match so far" count
// while the user works through the questionnaire. See frontend/api/recommend.js
// for the equivalent /recommend client.

const API_BASE_URL = import.meta.env.VITE_API_URL || ''

export async function fetchFilterCount(hardFilters) {
  const response = await fetch(`${API_BASE_URL}/filter-count`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hard_filters: hardFilters }),
  })

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`)
  }

  return response.json()
}
