import axios from 'axios';

export interface UploadResponse {
  status: string;
  extracted_data: Record<string, any>;
  confidence: number;
  message: string;
}

export interface ExternalCrmConfig {
  url: string;
  api_token: string;
  endpoint: string;
  field_mappings?: Record<string, string>;
}

export interface SyncResult {
  status: string;
  synced_clients: number;
  synced_obligations: number;
  synced_sales: number;
  errors: string[];
}

const API = axios.create({
  baseURL: '/api'
});

export const uploadService = {
  // Processar documento em base64
  processDocument: async (documentType: string, fileBase64: string): Promise<UploadResponse> => {
    const response = await API.post('/api/upload/process', {
      document_type: documentType,
      file_base64: fileBase64
    });
    return response.data;
  },

  // Converter arquivo para base64
  fileToBase64: (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        const base64 = (reader.result as string).split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
    });
  }
};

export const externalCrmService = {
  // Sincronizar com CRM externo
  syncExternal: async (config: ExternalCrmConfig): Promise<SyncResult> => {
    const response = await API.post('/api/external-crm/sync', config);
    return response.data;
  },

  // Testar conexão
  testConnection: async (config: ExternalCrmConfig): Promise<{ status: string; message: string }> => {
    const response = await API.post('/api/external-crm/test-connection', config);
    return response.data;
  }
};
