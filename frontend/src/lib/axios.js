import axios from 'axios';

// In production (Vercel), point to the Render backend URL
// In development, Vite proxy handles /api → localhost:8000
const API_BASE = import.meta.env.VITE_API_URL || '';

axios.defaults.baseURL = API_BASE;

export default axios;
