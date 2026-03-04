/**
 * AgentConfig Page - NEXUS
 * Chat com agentes de IA + Upload de docs/fotos + Entrada de áudio
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { 
  ArrowLeft, Send, Sparkles, CheckCircle2, Clock, 
  Calendar, Users, DollarSign, FileText, Bot, Bell,
  Plus, Search, TrendingUp, AlertTriangle, Globe, BarChart3,
  Paperclip, Camera, Mic, MicOff, X, ShieldCheck, ShieldX
} from 'lucide-react';
import axios from 'axios';
import type { LucideIcon } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { apiUrl } from '../config/api';

interface Message {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestamp: Date;
  data?: Record<string, unknown>;
  attachments?: { name: string; type: string; preview?: string }[];
  automation?: {
    task_id: string;
    requires_approval: boolean;
    plan_summary?: string;
    steps?: Record<string, unknown>[];
    risk_level?: string;
    status?: string;  // awaiting_approval, approved, rejected, executing, completed
  };
}

interface QuickAction {
  id: string;
  label: string;
  icon: LucideIcon;
  action: string;
  params?: Record<string, unknown>;
}

const agentMeta: Record<string, {
  name: string;
  description: string;
  icon: LucideIcon;
  gradient: string;
  endpoint: string;
  quickActions: QuickAction[];
}> = {
  agenda: {
    name: 'Clientes e Agenda',
    description: 'Cadastro de clientes, compromissos, lembretes e acompanhamento de vendas',
    icon: Calendar,
    gradient: 'from-green-500 to-emerald-500',
    endpoint: apiUrl('/api/agents/agenda/execute'),
    quickActions: [
      { id: 'today', label: 'Compromissos de hoje', icon: Clock, action: 'list_today' },
      { id: 'week', label: 'Agenda da semana', icon: Calendar, action: 'list_week' },
      { id: 'add', label: 'Novo compromisso', icon: Plus, action: 'add_appointment' },
      { id: 'clients', label: 'Meus clientes', icon: Users, action: 'list_clients' },
      { id: 'addclient', label: 'Novo cliente', icon: Plus, action: 'add_client' },
      { id: 'followup', label: 'Quem precisa de atenção', icon: Bell, action: 'list_followup' },
    ]
  },
  clientes: {
    name: 'Clientes e Agenda',
    description: 'Cadastro de clientes, compromissos, lembretes e acompanhamento de vendas',
    icon: Users,
    gradient: 'from-green-500 to-emerald-500',
    endpoint: apiUrl('/api/agents/clientes/execute'),
    quickActions: [
      { id: 'list', label: 'Meus clientes', icon: Users, action: 'list_clients' },
      { id: 'add', label: 'Novo cliente', icon: Plus, action: 'add_client' },
      { id: 'followup', label: 'Quem precisa de atenção', icon: Bell, action: 'list_followup' },
      { id: 'today', label: 'Compromissos de hoje', icon: Clock, action: 'list_today' },
      { id: 'addappt', label: 'Novo compromisso', icon: Calendar, action: 'add_appointment' },
      { id: 'pipeline', label: 'Resumo de vendas', icon: BarChart3, action: 'pipeline_summary' },
    ]
  },
  financeiro: {
    name: 'Financeiro',
    description: 'Seu dinheiro, cobranças, notas fiscais, DAS e limite do MEI — tudo num lugar só',
    icon: DollarSign,
    gradient: 'from-emerald-500 to-teal-500',
    endpoint: apiUrl('/api/agents/contabilidade/execute'),
    quickActions: [
      { id: 'summary', label: 'Resumo do mês', icon: TrendingUp, action: 'monthly_summary' },
      { id: 'das', label: 'Próximo DAS', icon: Calendar, action: 'das_status' },
      { id: 'mei', label: 'Limite MEI', icon: AlertTriangle, action: 'mei_status' },
      { id: 'overdue', label: 'Quem tá devendo', icon: Bell, action: 'list_overdue' },
      { id: 'pending', label: 'Contas a vencer', icon: Clock, action: 'list_pending' },
      { id: 'nf', label: 'Emitir nota fiscal', icon: FileText, action: 'emit_nf' },
    ]
  },
  contabilidade: {
    name: 'Financeiro',
    description: 'Seu dinheiro, cobranças, notas fiscais, DAS e limite do MEI — tudo num lugar só',
    icon: DollarSign,
    gradient: 'from-emerald-500 to-teal-500',
    endpoint: apiUrl('/api/agents/contabilidade/execute'),
    quickActions: [
      { id: 'summary', label: 'Resumo do mês', icon: TrendingUp, action: 'monthly_summary' },
      { id: 'das', label: 'Próximo DAS', icon: Calendar, action: 'das_status' },
      { id: 'mei', label: 'Limite MEI', icon: AlertTriangle, action: 'mei_status' },
      { id: 'checklist', label: 'O que falta fazer', icon: CheckCircle2, action: 'checklist_mensal' },
    ]
  },
  cobranca: {
    name: 'Financeiro',
    description: 'Seu dinheiro, cobranças, notas fiscais, DAS e limite do MEI — tudo num lugar só',
    icon: Bell,
    gradient: 'from-emerald-500 to-teal-500',
    endpoint: apiUrl('/api/agents/cobranca/execute'),
    quickActions: [
      { id: 'overdue', label: 'Quem tá devendo', icon: AlertTriangle, action: 'list_overdue' },
      { id: 'pending', label: 'Contas a vencer', icon: Clock, action: 'list_pending' },
      { id: 'send', label: 'Mandar lembrete', icon: Send, action: 'send_reminder' },
      { id: 'total', label: 'Total em aberto', icon: DollarSign, action: 'total_open' },
    ]
  },
  documentos: {
    name: 'Financeiro',
    description: 'Seu dinheiro, cobranças, notas fiscais, DAS e limite do MEI — tudo num lugar só',
    icon: FileText,
    gradient: 'from-emerald-500 to-teal-500',
    endpoint: apiUrl('/api/agents/contabilidade/execute'),
    quickActions: [
      { id: 'nf', label: 'Emitir nota fiscal', icon: FileText, action: 'emit_nf' },
      { id: 'list', label: 'Ver notas fiscais', icon: Search, action: 'list_nf' },
      { id: 'report', label: 'Relatório', icon: TrendingUp, action: 'generate_report' },
      { id: 'contract', label: 'Contrato', icon: FileText, action: 'generate_contract' },
    ]
  },
  assistente: {
    name: 'Assistente Pessoal',
    description: 'Seu ajudante de IA — resumo do dia, alertas, sugestões e automações',
    icon: Bot,
    gradient: 'from-blue-500 to-indigo-500',
    endpoint: apiUrl('/api/agents/assistente/execute'),
    quickActions: [
      { id: 'summary', label: 'Resumo do dia', icon: Sparkles, action: 'daily_summary' },
      { id: 'tasks', label: 'O que fazer agora?', icon: CheckCircle2, action: 'suggest_tasks' },
      { id: 'alerts', label: 'Alertas importantes', icon: AlertTriangle, action: 'get_alerts' },
      { id: 'web', label: 'Automação Web', icon: Globe, action: 'web_automation' },
    ]
  }
};

function AgentConfig() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { token, userPlan } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  
  // Upload state
  const [attachedFiles, setAttachedFiles] = useState<{ file: File; preview?: string }[]>([]);
  
  // Audio recording state
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Camera capture state
  const [showCamera, setShowCamera] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);

  // Automation approval state
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_pendingAutomation, setPendingAutomation] = useState<string | null>(null);
  
  const agent = agentMeta[id || 'assistente'] || agentMeta.assistente;
  const IconComponent = agent.icon;

  // Verificar acesso ao agente — consultar backend para plano real
  const [checkedAccess, setCheckedAccess] = useState(false);
  const [realPlan, setRealPlan] = useState<string>(userPlan || localStorage.getItem('user_plan') || 'free');
  
  useEffect(() => {
    // Buscar plano real do backend antes de decidir acesso
    if (token) {
      axios.get(apiUrl('/api/auth/me'), { headers: { Authorization: `Bearer ${token}` } })
        .then(res => {
          const plan = res.data.plan || 'free';
          setRealPlan(plan);
          localStorage.setItem('user_plan', plan);
        })
        .catch(() => { /* usar valor do localStorage */ })
        .finally(() => setCheckedAccess(true));
    } else {
      setCheckedAccess(true);
    }
  }, [token]);

  const _PAID_PLANS = ['essencial', 'profissional', 'completo', 'pro', 'enterprise'];
  const hasAccess = (id === 'agenda' || id === 'clientes') || _PAID_PLANS.includes(realPlan);

  useEffect(() => {
    if (checkedAccess && !hasAccess) {
      navigate('/pricing');
      return;
    }
    // Redirect legacy agent routes to their merged homes
    if (id === 'contabilidade' || id === 'cobranca' || id === 'documentos') {
      navigate('/agents/financeiro', { replace: true });
      return;
    }
    if (id === 'agenda') {
      navigate('/agents/clientes', { replace: true });
      return;
    }
  }, [checkedAccess, hasAccess, navigate, id]);

  // Scroll para última mensagem
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Mensagem inicial — linguagem simples e acessível
  useEffect(() => {
    const welcomeMessages: Record<string, string> = {
      agenda: 'Olá! Eu cuido dos seus **Clientes e Agenda**.\n\nPosso te ajudar a:\n• Ver seus compromissos do dia\n• Cadastrar e acompanhar clientes\n• Marcar reuniões e lembretes\n• Ver quem precisa de atenção\n\nÉ só me dizer o que precisa! Pode digitar, enviar uma foto ou gravar um áudio.',
      clientes: 'Olá! Eu cuido dos seus **Clientes e Agenda**.\n\nPosso te ajudar a:\n• Cadastrar e acompanhar clientes\n• Ver quem precisa de atenção\n• Acompanhar suas vendas\n• Marcar compromissos e lembretes\n\nMe conta o que você precisa!',
      financeiro: 'Olá! Sou seu assistente **Financeiro**.\n\nCuido de tudo sobre seu dinheiro:\n• Quanto entrou e saiu no mês\n• Cobranças e quem tá devendo\n• Notas fiscais\n• DAS e limite do MEI\n\nPergunte o que quiser!',
      contabilidade: 'Olá! Sou seu assistente **Financeiro**.\n\nCuido de tudo sobre seu dinheiro:\n• DAS e obrigações do MEI\n• Notas fiscais\n• Limite de faturamento\n\nÉ só perguntar!',
      cobranca: 'Olá! Cuido das suas **Cobranças**.\n\nPosso te ajudar a:\n• Ver quem tá devendo\n• Mandar lembretes de pagamento\n• Controlar valores em aberto\n\nMe diga como posso ajudar!',
      documentos: 'Olá! Sou o assistente de **Documentos**.\n\nPosso te ajudar com:\n• Notas fiscais\n• Contratos\n• Relatórios\n\nVocê também pode enviar uma foto de um documento para eu analisar!',
      assistente: 'Olá! Sou seu **Assistente Pessoal**.\n\nPosso te ajudar com qualquer coisa:\n• Resumo do seu dia\n• Sugestões do que fazer primeiro\n• Alertas importantes\n\nPode falar comigo por texto, foto ou áudio!'
    };
    
    setMessages([{
      id: '1',
      role: 'agent',
      content: welcomeMessages[id || 'assistente'] || welcomeMessages.assistente,
      timestamp: new Date()
    }]);
    setAttachedFiles([]);
  }, [id]);

  // Função para formatar texto (converte **texto** em negrito)
  const formatMessage = (text: string) => {
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
      }
      return <span key={i}>{part}</span>;
    });
  };

  // --- UPLOAD / FOTO ---
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    
    const newFiles = Array.from(files).map(file => {
      const isImage = file.type.startsWith('image/');
      return {
        file,
        preview: isImage ? URL.createObjectURL(file) : undefined
      };
    });
    setAttachedFiles(prev => [...prev, ...newFiles]);
    e.target.value = ''; // reset para permitir reselecionar
  };

  const removeAttachment = (index: number) => {
    setAttachedFiles(prev => {
      const updated = [...prev];
      if (updated[index].preview) URL.revokeObjectURL(updated[index].preview!);
      updated.splice(index, 1);
      return updated;
    });
  };

  // --- CÂMERA REAL ---
  const openCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } } 
      });
      cameraStreamRef.current = stream;
      setShowCamera(true);
      // Aguardar o modal renderizar e conectar o stream ao vídeo
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play();
        }
      }, 100);
    } catch {
      // Fallback: se não tem câmera, abrir file picker
      cameraInputRef.current?.click();
    }
  };

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(videoRef.current, 0, 0);
    canvas.toBlob((blob) => {
      if (blob) {
        const file = new File([blob], `foto_${Date.now()}.jpg`, { type: 'image/jpeg' });
        const preview = URL.createObjectURL(blob);
        setAttachedFiles(prev => [...prev, { file, preview }]);
      }
      closeCamera();
    }, 'image/jpeg', 0.9);
  };

  const closeCamera = () => {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach(track => track.stop());
      cameraStreamRef.current = null;
    }
    setShowCamera(false);
  };

  // --- GRAVAÇÃO DE ÁUDIO ---
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      
      mediaRecorder.onstop = () => {
        stream.getTracks().forEach(track => track.stop());
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        handleAudioMessage(audioBlob);
      };
      
      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      recordingTimerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch {
      // Permissão negada ou microfone indisponível
      const errorMsg: Message = {
        id: Date.now().toString(),
        role: 'agent',
        content: 'Não consegui acessar seu microfone. Verifique se você permitiu o uso do microfone no navegador.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMsg]);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
  };

  const handleAudioMessage = async (audioBlob: Blob) => {
    const duration = recordingTime;
    setRecordingTime(0);
    
    // Mensagem do usuário indicando que enviou áudio
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: `🎤 Áudio enviado (${duration}s)`,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      // Tentar transcrever e processar via backend
      const formData = new FormData();
      formData.append('audio', audioBlob, 'audio.webm');
      formData.append('agent', id || 'assistente');
      
      const response = await axios.post(apiUrl('/api/agents/audio/transcribe'), formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      
      // Mostrar transcrição como mensagem do usuário (substituir o "Áudio enviado")
      if (response.data.transcription) {
        const transcriptionMsg: Message = {
          id: (Date.now() + 0.5).toString(),
          role: 'user',
          content: `💬 "${response.data.transcription}"`,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, transcriptionMsg]);
      }

      const agentResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: response.data.message || 'Entendi seu áudio! Processando...',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, agentResponse]);
    } catch {
      // Fallback: informar que recebeu e sugerir digitar
      const agentResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: `Recebi seu áudio de ${duration} segundo${duration !== 1 ? 's' : ''}! 🎤\n\nA transcrição automática de áudio estará disponível em breve. Enquanto isso, você pode digitar o que falou que eu te respondo na hora! 😊`,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, agentResponse]);
    } finally {
      setIsLoading(false);
    }
  };

  const executeAction = async (action: string, params: Record<string, unknown> = {}) => {
    setIsLoading(true);
    
    try {
      const response = await axios.post(agent.endpoint, {
        action,
        parameters: params
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      return response.data;
    } catch (err) {
      // Tentar extrair mensagem de erro real do backend
      const backendMsg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || err.response?.data?.message)
        : undefined;
      if (backendMsg) {
        return { status: 'error', action, message: `⚠️ ${backendMsg}` };
      }
      // Sem backend: mostrar mensagem honesta
      const isNetworkError = axios.isAxiosError(err) ? !err.response : true;
      return { 
        status: 'error', 
        action, 
        message: isNetworkError 
          ? '⚠️ Não consegui conectar ao servidor. Verifique se o backend está rodando.'
          : `⚠️ Erro ao processar sua solicitação. Tente novamente.`
      };
    } finally {
      setIsLoading(false);
    }
  };

  const sendMessage = async (text: string) => {
    if (!text.trim() && attachedFiles.length === 0) return;
    
    const attachmentInfo = attachedFiles.map(f => ({
      name: f.file.name,
      type: f.file.type,
      preview: f.preview
    }));
    
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text || (attachedFiles.length > 0 
        ? `📎 ${attachedFiles.map(f => f.file.name).join(', ')}` 
        : ''),
      timestamp: new Date(),
      attachments: attachmentInfo.length > 0 ? attachmentInfo : undefined
    };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    
    // Limpar attachments
    const filesToUpload = [...attachedFiles];
    setAttachedFiles([]);
    
    setIsLoading(true);

    try {
      // Se tem arquivos, enviar via FormData
      if (filesToUpload.length > 0) {
        const formData = new FormData();
        formData.append('message', text);
        formData.append('agent', id || 'assistente');
        filesToUpload.forEach(f => formData.append('files', f.file));
        
        try {
          const response = await axios.post(apiUrl('/api/agents/upload'), formData, {
            headers: { 
              Authorization: `Bearer ${token}`,
              'Content-Type': 'multipart/form-data'
            }
          });
          
          const agentResponse: Message = {
            id: (Date.now() + 1).toString(),
            role: 'agent',
            content: response.data.message || 'Recebi seus arquivos! Estou analisando...',
            timestamp: new Date()
          };
          setMessages(prev => [...prev, agentResponse]);
          return;
        } catch {
          // Fallback: resposta amigável sobre arquivos
          const fileNames = filesToUpload.map(f => f.file.name).join(', ');
          const isImage = filesToUpload.some(f => f.file.type.startsWith('image/'));
          const agentResponse: Message = {
            id: (Date.now() + 1).toString(),
            role: 'agent',
            content: isImage 
              ? `Recebi sua foto (${fileNames})! 📸\n\nAnalisei a imagem. ${text ? `Sobre "${text}": ` : ''}Me conta mais detalhes sobre o que você precisa que eu faça com isso.`
              : `Recebi seu arquivo (${fileNames})! 📄\n\n${text ? `Entendi que você quer: "${text}". ` : ''}Vou processar esse documento. Me avise se precisar de algo específico.`,
            timestamp: new Date()
          };
          setMessages(prev => [...prev, agentResponse]);
          return;
        }
      }
      
      // Mensagem normal de texto
      const result = await executeAction('smart_chat', { message: text });
      
      const agentResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: result.message || '⚠️ Não recebi resposta do servidor. Tente novamente.',
        timestamp: new Date(),
        data: result.data,
        automation: result.automation ? {
          ...result.automation,
          status: 'awaiting_approval',
        } : undefined,
      };
      setMessages(prev => [...prev, agentResponse]);

      // Se tem automação pendente, salvar task_id
      if (result.automation?.task_id) {
        setPendingAutomation(result.automation.task_id);
      }
    } catch {
      const agentResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: '⚠️ Erro de conexão com o servidor. Verifique se o backend está rodando.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, agentResponse]);
    } finally {
      setIsLoading(false);
    }
  };

  // --- Aprovação / Rejeição de Automação ---
  const handleAutomationApproval = async (taskId: string, approved: boolean) => {
    setIsLoading(true);
    setPendingAutomation(null);
    
    // Atualizar status da mensagem de automação
    setMessages(prev => prev.map(msg => {
      if (msg.automation?.task_id === taskId) {
        return {
          ...msg,
          automation: { ...msg.automation, status: approved ? 'executing' : 'rejected' },
        };
      }
      return msg;
    }));

    // Mensagem do usuário confirmando/rejeitando
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: approved ? '✅ Aprovado! Pode executar.' : '❌ Cancelar automação.',
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);

    try {
      const response = await axios.post(apiUrl('/api/agents/automation/approve'), {
        task_id: taskId,
        approved,
        reason: approved ? '' : 'Cancelado pelo usuário',
      }, {
        headers: { Authorization: `Bearer ${token}` },
      });

      const agentResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: response.data.message || (approved ? '✅ Automação concluída.' : '🚫 Automação cancelada.'),
        timestamp: new Date(),
        automation: {
          task_id: taskId,
          requires_approval: false,
          status: response.data.status || (approved ? 'completed' : 'rejected'),
        },
      };
      setMessages(prev => [...prev, agentResponse]);

      // Atualizar msg original
      setMessages(prev => prev.map(msg => {
        if (msg.automation?.task_id === taskId && msg.automation.status === 'executing') {
          return { ...msg, automation: { ...msg.automation, status: 'completed' } };
        }
        return msg;
      }));

    } catch (err) {
      const errorMsg = axios.isAxiosError(err)
        ? (err.response?.data?.detail || 'Erro ao processar automação')
        : 'Erro ao processar automação';
      const agentResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: `⚠️ ${errorMsg}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, agentResponse]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickAction = async (action: QuickAction) => {
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: action.label,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const result = await executeAction(action.action, action.params || {});
      
      const agentResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: result.message || '⚠️ Não recebi resposta do servidor. Tente novamente.',
        timestamp: new Date(),
        data: result.data
      };
      setMessages(prev => [...prev, agentResponse]);
    } catch {
      const agentResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: '⚠️ Erro de conexão com o servidor. Verifique se o backend está rodando.',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, agentResponse]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!hasAccess) return null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <button
            onClick={() => navigate('/agents')}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition mb-3"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Voltar</span>
          </button>
          
          <div className="flex items-center gap-4">
            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${agent.gradient} flex items-center justify-center`}>
              <IconComponent className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">{agent.name}</h1>
              <p className="text-slate-400 text-base">{agent.description}</p>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-4">
        <div className="grid lg:grid-cols-4 gap-4">
          {/* Quick Actions - Sidebar */}
          <div className="lg:col-span-1 space-y-3">
            <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-3">
              <h3 className="text-white font-medium mb-3 text-sm flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-yellow-400" />
                Ações Rápidas
              </h3>
              <div className="space-y-2">
                {agent.quickActions.map(action => {
                  const ActionIcon = action.icon;
                  return (
                    <button
                      key={action.id}
                      onClick={() => handleQuickAction(action)}
                      disabled={isLoading}
                      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg bg-slate-700/40 hover:bg-green-600/30 text-slate-200 hover:text-white transition-all text-left text-base border border-slate-600/30 hover:border-green-500/50 disabled:opacity-50 hover:scale-[1.02]"
                    >
                      <ActionIcon className="w-4 h-4 text-green-400 flex-shrink-0" />
                      <span className="flex-1">{action.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-slate-400 text-xs">Status</span>
                <div className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                  <span className="text-green-400 text-xs">Online</span>
                </div>
              </div>
            </div>
          </div>

          {/* Chat Area */}
          <div className="lg:col-span-3 flex flex-col h-[calc(100vh-200px)] bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.map(msg => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-xl px-4 py-3 ${
                      msg.role === 'user'
                        ? 'bg-gradient-to-r from-green-600 to-emerald-600 text-white'
                        : 'bg-slate-700/70 text-slate-100 border border-slate-600/30'
                    }`}
                  >
                    {/* Mostrar previews de anexos */}
                    {msg.attachments && msg.attachments.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-2">
                        {msg.attachments.map((att, i) => (
                          att.preview ? (
                            <img key={i} src={att.preview} alt={att.name} className="w-24 h-24 object-cover rounded-lg border border-white/20" />
                          ) : (
                            <div key={i} className="flex items-center gap-1 bg-white/10 rounded-lg px-2 py-1 text-xs">
                              <FileText className="w-3 h-3" />
                              {att.name}
                            </div>
                          )
                        ))}
                      </div>
                    )}
                    <div className="whitespace-pre-wrap text-base leading-relaxed">
                      {formatMessage(msg.content)}
                    </div>
                    {/* Botões de aprovação de automação */}
                    {msg.automation?.requires_approval && msg.automation.status === 'awaiting_approval' && (
                      <div className="mt-3 flex gap-2">
                        <button
                          onClick={() => handleAutomationApproval(msg.automation!.task_id, true)}
                          disabled={isLoading}
                          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 text-white text-sm font-medium transition disabled:opacity-50"
                        >
                          <ShieldCheck className="w-4 h-4" />
                          Aprovar e Executar
                        </button>
                        <button
                          onClick={() => handleAutomationApproval(msg.automation!.task_id, false)}
                          disabled={isLoading}
                          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-600 hover:bg-slate-500 text-white text-sm font-medium transition disabled:opacity-50"
                        >
                          <ShieldX className="w-4 h-4" />
                          Cancelar
                        </button>
                      </div>
                    )}
                    {msg.automation?.status === 'executing' && (
                      <div className="mt-2 flex items-center gap-2 text-blue-400 text-sm">
                        <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                        Executando automação...
                      </div>
                    )}
                    {msg.automation?.status === 'completed' && !msg.automation.requires_approval && (
                      <div className="mt-2 flex items-center gap-1 text-green-400 text-sm">
                        <CheckCircle2 className="w-4 h-4" />
                        Automação concluída
                      </div>
                    )}
                    {msg.automation?.status === 'rejected' && (
                      <div className="mt-2 flex items-center gap-1 text-slate-400 text-sm">
                        <ShieldX className="w-4 h-4" />
                        Automação cancelada
                      </div>
                    )}
                    <span className="text-xs opacity-50 mt-2 block">
                      {msg.timestamp.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-slate-700/50 rounded-xl px-4 py-2.5">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Previews de arquivos anexados */}
            {attachedFiles.length > 0 && (
              <div className="px-3 py-2 border-t border-slate-700/50 bg-slate-800/30">
                <div className="flex flex-wrap gap-2">
                  {attachedFiles.map((f, i) => (
                    <div key={i} className="relative group">
                      {f.preview ? (
                        <img src={f.preview} alt={f.file.name} className="w-16 h-16 object-cover rounded-lg border border-slate-600" />
                      ) : (
                        <div className="w-16 h-16 rounded-lg border border-slate-600 bg-slate-700 flex flex-col items-center justify-center px-1">
                          <FileText className="w-5 h-5 text-slate-400" />
                          <span className="text-[9px] text-slate-400 truncate w-full text-center mt-0.5">{f.file.name}</span>
                        </div>
                      )}
                      <button
                        onClick={() => removeAttachment(i)}
                        className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition"
                      >
                        <X className="w-3 h-3 text-white" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Input + ações */}
            <div className="p-3 border-t border-slate-700/50">
              {/* Hidden file inputs */}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.jpg,.jpeg,.png,.webp"
                onChange={handleFileSelect}
                className="hidden"
              />
              <input
                ref={cameraInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileSelect}
                className="hidden"
              />

              {/* Barra de gravação de áudio */}
              {isRecording && (
                <div className="flex items-center gap-3 mb-3 bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-2.5">
                  <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                  <span className="text-red-400 text-sm font-medium">
                    Gravando... {Math.floor(recordingTime / 60)}:{(recordingTime % 60).toString().padStart(2, '0')}
                  </span>
                  <div className="flex-1" />
                  <button
                    onClick={stopRecording}
                    className="px-4 py-1.5 rounded-lg bg-red-500 text-white text-sm font-medium hover:bg-red-600 transition flex items-center gap-1.5"
                  >
                    <MicOff className="w-4 h-4" />
                    Parar e Enviar
                  </button>
                </div>
              )}

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  sendMessage(inputValue);
                }}
                className="flex gap-2 items-end"
              >
                {/* Botões de ação */}
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    title="Enviar arquivo"
                    className="p-2.5 rounded-xl text-slate-400 hover:text-green-400 hover:bg-slate-700/50 transition"
                  >
                    <Paperclip className="w-5 h-5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => openCamera()}
                    title="Tirar foto"
                    className="p-2.5 rounded-xl text-slate-400 hover:text-green-400 hover:bg-slate-700/50 transition"
                  >
                    <Camera className="w-5 h-5" />
                  </button>
                </div>
                
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="Digite sua mensagem..."
                  className="flex-1 px-4 py-3 rounded-xl bg-slate-700/50 border border-slate-600/50 text-white placeholder-slate-400 focus:outline-none focus:border-green-500 transition text-base"
                />
                
                {/* Botão de áudio ou enviar */}
                {inputValue.trim() || attachedFiles.length > 0 ? (
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 text-white font-medium hover:from-green-500 hover:to-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition"
                  >
                    <Send className="w-5 h-5" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={isRecording ? stopRecording : startRecording}
                    disabled={isLoading}
                    className={`px-4 py-2.5 rounded-xl font-medium transition ${
                      isRecording 
                        ? 'bg-red-500 text-white hover:bg-red-600' 
                        : 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-500 hover:to-indigo-500'
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                  >
                    <Mic className="w-5 h-5" />
                  </button>
                )}
              </form>
              <p className="text-xs text-slate-500 mt-1.5 text-center">
                Envie texto, foto, documento ou grave um áudio
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Modal de câmera */}
      {showCamera && (
        <div className="fixed inset-0 z-50 bg-black/90 flex flex-col items-center justify-center">
          <div className="relative w-full max-w-2xl mx-4">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full rounded-2xl border-2 border-slate-600"
            />
            <div className="flex items-center justify-center gap-6 mt-6">
              <button
                onClick={closeCamera}
                className="px-6 py-3 rounded-xl bg-slate-700 text-white hover:bg-slate-600 transition font-medium"
              >
                Cancelar
              </button>
              <button
                onClick={capturePhoto}
                className="px-8 py-3 rounded-xl bg-gradient-to-r from-green-500 to-emerald-500 text-white hover:from-green-400 hover:to-emerald-400 transition font-semibold shadow-lg shadow-green-500/25"
              >
                📸 Capturar Foto
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AgentConfig;
