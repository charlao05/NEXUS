import { useState } from 'react';
import { externalCrmService } from '../../services/integrationService';
import '../styles/Modal.css';

interface ExternalCrmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSyncComplete: (result: { synced_clients: number; synced_obligations: number; synced_sales: number }) => void;
}

export default function ExternalCrmModal({ isOpen, onClose, onSyncComplete }: ExternalCrmModalProps) {
  const [url, setUrl] = useState('');
  const [apiToken, setApiToken] = useState('');
  const [endpoint, setEndpoint] = useState('/persons');
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [connectionOk, setConnectionOk] = useState<boolean | null>(null);

  const handleTest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url || !apiToken) {
      setError('URL e Token são obrigatórios');
      return;
    }

    setTesting(true);
    setError('');
    try {
      const result = await externalCrmService.testConnection({
        url,
        api_token: apiToken,
        endpoint
      });
      setConnectionOk(result.status === 'ok');
      setSuccess(result.message);
    } catch (err) {
      setError(`Erro ao testar: ${err instanceof Error ? err.message : 'desconhecido'}`);
      setConnectionOk(false);
    } finally {
      setTesting(false);
    }
  };

  const handleSync = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!connectionOk) {
      setError('Teste a conexão primeiro');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const result = await externalCrmService.syncExternal({
        url,
        api_token: apiToken,
        endpoint,
        field_mappings: {}
      });

      if (result.status === 'ok') {
        setSuccess(`✓ Sincronizados ${result.synced_clients} clientes`);
        onSyncComplete(result);
        setTimeout(() => {
          setUrl('');
          setApiToken('');
          setEndpoint('/persons');
          setConnectionOk(null);
          onClose();
        }, 2000);
      } else {
        setError(`Erro: ${result.errors.join(', ')}`);
      }
    } catch (err) {
      setError(`Erro na sincronização: ${err instanceof Error ? err.message : 'desconhecido'}`);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>🔗 Integrar com CRM Externo</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSync} className="modal-form">
          <div className="form-group">
            <label>URL da API (ex: https://api.pipedrive.com):</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://api...."
              required
            />
          </div>

          <div className="form-group">
            <label>API Token / Bearer:</label>
            <input
              type="password"
              value={apiToken}
              onChange={(e) => setApiToken(e.target.value)}
              placeholder="Bearer token ou API key"
              required
            />
          </div>

          <div className="form-group">
            <label>Endpoint (ex: /persons, /contacts):</label>
            <input
              type="text"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              placeholder="/persons"
            />
          </div>

          {error && <div className="error-message">❌ {error}</div>}
          {success && <div className="success-message">✅ {success}</div>}

          <div className="modal-actions">
            <button 
              type="button" 
              onClick={handleTest} 
              disabled={testing || loading || !url || !apiToken}
              className="secondary"
            >
              {testing ? '⏳ Testando...' : '🧪 Testar Conexão'}
            </button>

            {connectionOk === true && (
              <span className="connection-ok">✓ Conectado</span>
            )}
            {connectionOk === false && (
              <span className="connection-error">✗ Falhou</span>
            )}

            <button 
              type="submit" 
              disabled={!connectionOk || loading}
            >
              {loading ? '⏳ Sincronizando...' : '🚀 Sincronizar'}
            </button>
          </div>
        </form>

        <div className="modal-info">
          <p>💡 Conecte sua conta do CRM externo para sincronizar clientes, obrigações e vendas automaticamente.</p>
          <p style={{ fontSize: '0.9em', color: '#666', marginTop: '10px' }}>
            Exemplos: Pipedrive, Zendesk, HubSpot (configure a URL e token de sua conta)
          </p>
        </div>
      </div>
    </div>
  );
}
