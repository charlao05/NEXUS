/**
 * API Client - NEXUS Frontend
 * ============================
 * 
 * Cliente HTTP base para todas as requisições à API
 */

import axios from 'axios'

const API = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor para adicionar tokens de autenticação
API.interceptors.request.use(
  (config) => {
    // TODO: Adicionar token JWT do Clerk quando implementado
    // const token = getAuthToken()
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor para tratamento de erros
API.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Servidor respondeu com status de erro
      console.error('API Error:', error.response.status, error.response.data)
    } else if (error.request) {
      // Requisição foi feita mas sem resposta
      console.error('Network Error:', error.request)
    } else {
      // Erro ao configurar a requisição
      console.error('Request Error:', error.message)
    }
    return Promise.reject(error)
  }
)

export default API
