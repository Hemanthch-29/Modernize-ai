import axios from 'axios'

// baseURL is intentionally left to VITE_API_URL (unset in dev), so calls stay relative
// and go through the Vite dev proxy to the .NET API.
export const client = axios.create({ baseURL: import.meta.env.VITE_API_URL })
