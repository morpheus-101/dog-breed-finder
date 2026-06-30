// POSTs to /recommend, proxied by Vite to http://localhost:8001 in development
// (see vite.config.js). Request/response shapes are defined in skills/api-contract.md.

export async function fetchRecommendations(requestBody) {
  const response = await fetch('/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody),
  })

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`)
  }

  return response.json()
}
