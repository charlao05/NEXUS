import React, { useEffect, useRef, useState } from 'react'
import './NfModal.css'

interface NfModalProps {
  show: boolean
  onClose: () => void
  onSubmit: (data: any) => void
}

type InputMode = 'camera' | 'upload' | 'qrcode' | 'manual'

const NfModal: React.FC<NfModalProps> = ({ show, onClose, onSubmit }) => {
  const [mode, setMode] = useState<InputMode>('camera')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [manualData, setManualData] = useState({
    cliente_nome: '',
    cliente_cnpj_cpf: '',
    valor_total: '',
    descricao_servicos: '',
    data_venda: new Date().toISOString().split('T')[0]
  })

  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    return () => {
      // Cleanup: parar stream de câmera ao desmontar
      if (stream) {
        stream.getTracks().forEach((track: MediaStreamTrack) => track.stop())
      }
    }
  }, [stream])

  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' } // Câmera traseira no mobile
      })
      setStream(mediaStream)
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream
      }
      setError(null)
    } catch (err) {
      setError('Erro ao acessar câmera. Verifique as permissões.')
      console.error('Camera error:', err)
    }
  }

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach((track: MediaStreamTrack) => track.stop())
      setStream(null)
    }
  }

  const capturePhoto = () => {
    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current
      const canvas = canvasRef.current
      
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.drawImage(video, 0, 0)
        const imageData = canvas.toDataURL('image/jpeg', 0.8)
        setPreview(imageData)
        stopCamera()
        processImage(imageData)
      }
    }
  }

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const imageData = e.target?.result as string
        setPreview(imageData)
        processImage(imageData)
      }
      reader.readAsDataURL(file)
    }
  }

  const processImage = async (imageData: string) => {
    setLoading(true)
    setError(null)

    try {
      // Chamar API de OCR para processar a imagem
      const response = await fetch('/api/upload/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_data: imageData.split(',')[1], // Remove data:image/jpeg;base64,
          document_type: 'invoice'
        })
      })

      if (!response.ok) {
        throw new Error('Erro ao processar imagem')
      }

      const result = await response.json()
      
      // Preencher dados extraídos
      if (result.extracted_data) {
        setManualData({
          cliente_nome: result.extracted_data.client_name || '',
          cliente_cnpj_cpf: result.extracted_data.client_cpf_cnpj || '',
          valor_total: result.extracted_data.total_value?.toString() || '',
          descricao_servicos: result.extracted_data.description || '',
          data_venda: result.extracted_data.date || new Date().toISOString().split('T')[0]
        })
        setMode('manual') // Mostrar formulário para revisar/editar
      }

    } catch (err) {
      setError('Erro ao processar imagem. Tente novamente ou use entrada manual.')
      console.error('OCR error:', err)
    } finally {
      setLoading(false)
    }
  }

  const scanQRCode = async () => {
    setLoading(true)
    setError(null)

    try {
      // Iniciar câmera para QR Code
      await startCamera()
      
      // Aqui você pode integrar uma lib de QR code scanner
      // Por exemplo: jsQR ou quagga2
      // Por ora, vamos simular
      setTimeout(() => {
        setError('Scanner QR Code em desenvolvimento. Use câmera ou upload por enquanto.')
        setLoading(false)
        stopCamera()
      }, 1000)

    } catch (err) {
      setError('Erro ao iniciar scanner QR Code')
      setLoading(false)
    }
  }

  const handleSubmit = () => {
    if (mode === 'manual') {
      // Validar dados manuais
      if (!manualData.cliente_nome || !manualData.valor_total) {
        setError('Preencha pelo menos Cliente e Valor')
        return
      }

      onSubmit({
        sale_data: {
          cliente_nome: manualData.cliente_nome,
          cliente_cnpj_cpf: manualData.cliente_cnpj_cpf,
          valor_total: parseFloat(manualData.valor_total),
          descricao_servicos: manualData.descricao_servicos,
          data_venda: manualData.data_venda
        }
      })
    }
  }

  const handleClose = () => {
    stopCamera()
    setPreview(null)
    setError(null)
    setManualData({
      cliente_nome: '',
      cliente_cnpj_cpf: '',
      valor_total: '',
      descricao_servicos: '',
      data_venda: new Date().toISOString().split('T')[0]
    })
    onClose()
  }

  if (!show) return null

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content nf-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>📄 Nota Fiscal</h2>
          <button className="close-btn" onClick={handleClose}>×</button>
        </div>

        <div className="modal-body">
          {/* Seletor de Modo */}
          <div className="mode-selector">
            <button
              className={`mode-btn ${mode === 'camera' ? 'active' : ''}`}
              onClick={() => {
                setMode('camera')
                setPreview(null)
              }}
            >
              📷 Foto
            </button>
            <button
              className={`mode-btn ${mode === 'upload' ? 'active' : ''}`}
              onClick={() => {
                setMode('upload')
                stopCamera()
              }}
            >
              📄 Upload
            </button>
            <button
              className={`mode-btn ${mode === 'qrcode' ? 'active' : ''}`}
              onClick={() => {
                setMode('qrcode')
                scanQRCode()
              }}
            >
              🔲 QR Code
            </button>
            <button
              className={`mode-btn ${mode === 'manual' ? 'active' : ''}`}
              onClick={() => {
                setMode('manual')
                stopCamera()
                setPreview(null)
              }}
            >
              ⌨️ Manual
            </button>
          </div>

          {error && (
            <div className="error-message">
              ⚠️ {error}
            </div>
          )}

          {/* Modo Câmera */}
          {mode === 'camera' && !preview && (
            <div className="camera-container">
              <video ref={videoRef} autoPlay playsInline className="video-preview" />
              <canvas ref={canvasRef} style={{ display: 'none' }} />
              
              <div className="camera-controls">
                {!stream ? (
                  <button className="btn-primary" onClick={startCamera}>
                    📷 Iniciar Câmera
                  </button>
                ) : (
                  <>
                    <button className="btn-primary" onClick={capturePhoto}>
                      📸 Capturar Foto
                    </button>
                    <button className="btn-secondary" onClick={stopCamera}>
                      ❌ Cancelar
                    </button>
                  </>
                )}
              </div>

              <p className="hint">
                💡 Dica: Posicione a nota fiscal ou cupom de forma clara e bem iluminada
              </p>
            </div>
          )}

          {/* Preview da Foto Capturada */}
          {preview && mode === 'camera' && (
            <div className="preview-container">
              <img src={preview} alt="Preview" className="image-preview" />
              {loading ? (
                <div className="loading">
                  <div className="spinner"></div>
                  <p>Extraindo dados da nota fiscal...</p>
                </div>
              ) : (
                <div className="preview-controls">
                  <button className="btn-secondary" onClick={() => {
                    setPreview(null)
                    startCamera()
                  }}>
                    🔄 Tirar Outra Foto
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Modo Upload */}
          {mode === 'upload' && (
            <div className="upload-container">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,application/pdf"
                onChange={handleFileUpload}
                style={{ display: 'none' }}
              />
              
              {!preview ? (
                <div className="upload-zone" onClick={() => fileInputRef.current?.click()}>
                  <div className="upload-icon">📤</div>
                  <p>Clique para selecionar arquivo</p>
                  <small>Imagem ou PDF da nota fiscal</small>
                </div>
              ) : (
                <div className="preview-container">
                  <img src={preview} alt="Preview" className="image-preview" />
                  {loading ? (
                    <div className="loading">
                      <div className="spinner"></div>
                      <p>Extraindo dados da nota fiscal...</p>
                    </div>
                  ) : (
                    <button className="btn-secondary" onClick={() => {
                      setPreview(null)
                      if (fileInputRef.current) fileInputRef.current.value = ''
                    }}>
                      🔄 Selecionar Outro Arquivo
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Modo QR Code */}
          {mode === 'qrcode' && (
            <div className="qrcode-container">
              <div className="qrcode-scanner">
                <video ref={videoRef} autoPlay playsInline className="video-preview" />
                <div className="qrcode-overlay">
                  <div className="qrcode-frame"></div>
                </div>
              </div>
              
              {loading && (
                <div className="loading">
                  <div className="spinner"></div>
                  <p>Aguardando QR Code...</p>
                </div>
              )}

              <p className="hint">
                💡 Aponte para o QR Code da nota fiscal
              </p>
            </div>
          )}

          {/* Modo Manual */}
          {mode === 'manual' && (
            <div className="manual-form">
              <div className="form-group">
                <label>Cliente *</label>
                <input
                  type="text"
                  value={manualData.cliente_nome}
                  onChange={(e) => setManualData({ ...manualData, cliente_nome: e.target.value })}
                  placeholder="Nome do cliente"
                />
              </div>

              <div className="form-group">
                <label>CPF/CNPJ</label>
                <input
                  type="text"
                  value={manualData.cliente_cnpj_cpf}
                  onChange={(e) => setManualData({ ...manualData, cliente_cnpj_cpf: e.target.value })}
                  placeholder="000.000.000-00"
                />
              </div>

              <div className="form-group">
                <label>Valor Total (R$) *</label>
                <input
                  type="number"
                  step="0.01"
                  value={manualData.valor_total}
                  onChange={(e) => setManualData({ ...manualData, valor_total: e.target.value })}
                  placeholder="250.00"
                />
              </div>

              <div className="form-group">
                <label>Descrição dos Serviços</label>
                <textarea
                  value={manualData.descricao_servicos}
                  onChange={(e) => setManualData({ ...manualData, descricao_servicos: e.target.value })}
                  placeholder="Descreva os serviços prestados"
                  rows={3}
                />
              </div>

              <div className="form-group">
                <label>Data da Venda</label>
                <input
                  type="date"
                  value={manualData.data_venda}
                  onChange={(e) => setManualData({ ...manualData, data_venda: e.target.value })}
                />
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={handleClose}>
            Cancelar
          </button>
          <button
            className="btn-primary"
            onClick={handleSubmit}
            disabled={loading || (mode === 'manual' && (!manualData.cliente_nome || !manualData.valor_total))}
          >
            {loading ? 'Processando...' : 'Gerar Instruções NF'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default NfModal
