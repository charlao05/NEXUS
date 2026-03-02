import { useState, useRef } from 'react';
import { uploadService } from '../../services/integrationService';
import '../styles/Modal.css';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDataExtracted: (data: Record<string, any>) => void;
}

export default function UploadModal({ isOpen, onClose, onDataExtracted }: UploadModalProps) {
  const [documentType, setDocumentType] = useState('obligation');
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFile(e.target.files[0]);
      setError('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Selecione um arquivo');
      return;
    }

    setLoading(true);
    try {
      const base64 = await uploadService.fileToBase64(file);
      const result = await uploadService.processDocument(documentType, base64);
      
      if (result.status === 'ok') {
        onDataExtracted(result.extracted_data);
        setFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        onClose();
      } else {
        setError(result.message || 'Erro ao processar documento');
      }
    } catch (err) {
      setError(`Erro: ${err instanceof Error ? err.message : 'desconhecido'}`);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>📄 Carregar Documento (OCR)</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="form-group">
            <label>Tipo de Documento:</label>
            <select 
              value={documentType} 
              onChange={(e) => setDocumentType(e.target.value)}
            >
              <option value="obligation">Obrigação (DAS, FGTS, etc)</option>
              <option value="sale">Venda / Serviço Prestado</option>
              <option value="invoice">NFS-e / Nota Fiscal</option>
              <option value="customer">Dados do Cliente</option>
            </select>
          </div>

          <div className="form-group">
            <label>Arquivo (Foto/PDF):</label>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,.pdf"
              onChange={handleFileChange}
              required
            />
            {file && <p className="file-name">✓ {file.name}</p>}
          </div>

          {error && <div className="error-message">❌ {error}</div>}

          <div className="modal-actions">
            <button type="button" onClick={onClose} disabled={loading}>
              Cancelar
            </button>
            <button type="submit" disabled={!file || loading}>
              {loading ? '⏳ Processando...' : '✨ Extrair Dados'}
            </button>
          </div>
        </form>

        <div className="modal-info">
          <p>💡 Tire uma foto ou selecione um PDF. A IA extrairá os dados automaticamente.</p>
        </div>
      </div>
    </div>
  );
}
