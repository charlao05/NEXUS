import API from './api'

export interface Client {
  id: string
  name: string
  email?: string
  phone?: string
  notes?: string
}

class ClientService {
  async listClients(): Promise<{ status: string; clients: Client[] }> {
    const res = await API.get('/api/clients')
    return res.data
  }
}

export default new ClientService()
