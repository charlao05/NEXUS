/**
 * Profile — Página de Perfil do Usuário
 * ========================================
 * Permite ao usuário editar dados pessoais (PF/PJ), endereço,
 * alterar senha e enviar feedback para melhoria contínua.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, User, Building2, Save, Lock, Star,
  MessageSquare, CheckCircle2, AlertTriangle, Phone, Mail, MapPin,
  Eye, EyeOff, Trash2, ShieldAlert, ChevronDown,
} from 'lucide-react';
import axios from 'axios';
import apiClient from '../services/apiClient';
import { useAuth } from '../contexts/AuthContext';
import { apiUrl } from '../config/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ProfileData {
  user_id: string;
  email: string;
  full_name: string;
  plan: string;
  role: string;
  communication_preference: string;
  person_type: string | null;
  cpf: string | null;
  cnpj: string | null;
  phone: string | null;
  company_name: string | null;
  trade_name: string | null;
  state_registration: string | null;
  municipal_registration: string | null;
  address_street: string | null;
  address_number: string | null;
  address_complement: string | null;
  address_neighborhood: string | null;
  address_city: string | null;
  address_state: string | null;
  address_zip: string | null;
  birth_date: string | null;
  business_type: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Input masks — Brazilian formats
// ---------------------------------------------------------------------------

function maskCPF(v: string): string {
  return v.replace(/\D/g, '').slice(0, 11)
    .replace(/(\d{3})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d{1,2})$/, '$1-$2');
}

function maskCNPJ(v: string): string {
  return v.replace(/\D/g, '').slice(0, 14)
    .replace(/(\d{2})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d)/, '$1/$2')
    .replace(/(\d{4})(\d{1,2})$/, '$1-$2');
}

function maskPhone(v: string): string {
  const d = v.replace(/\D/g, '').slice(0, 11);
  if (d.length <= 10) return d.replace(/(\d{2})(\d)/, '($1) $2').replace(/(\d{4})(\d)/, '$1-$2');
  return d.replace(/(\d{2})(\d)/, '($1) $2').replace(/(\d{5})(\d)/, '$1-$2');
}

function maskCEP(v: string): string {
  return v.replace(/\D/g, '').slice(0, 8).replace(/(\d{5})(\d)/, '$1-$2');
}

// ---------------------------------------------------------------------------
// Stable InputField — defined OUTSIDE to avoid re-mount on parent re-render
// ---------------------------------------------------------------------------

interface ProfileInputProps {
  label: string;
  field: string;
  value: string;
  onFieldChange: (field: string, value: string) => void;
  placeholder?: string;
  maxLength?: number;
  type?: string;
  icon?: React.ComponentType<{ className?: string }>;
  mask?: 'cpf' | 'cnpj' | 'phone' | 'cep';
}

function ProfileInput({
  label, field, value, onFieldChange, placeholder, maxLength, type = 'text', icon: Icon, mask,
}: ProfileInputProps) {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let val = e.target.value;
    if (mask === 'cpf') val = maskCPF(val);
    else if (mask === 'cnpj') val = maskCNPJ(val);
    else if (mask === 'phone') val = maskPhone(val);
    else if (mask === 'cep') val = maskCEP(val);
    onFieldChange(field, val);
  };

  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-1">{label}</label>
      <div className="relative">
        {Icon && <Icon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />}
        <input
          type={type}
          value={value}
          onChange={handleChange}
          placeholder={placeholder}
          maxLength={maxLength}
          className={`w-full bg-slate-800/50 border border-slate-700/50 rounded-lg px-3 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-green-500/50 focus:border-green-500/50 transition text-sm ${Icon ? 'pl-10' : ''}`}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Profile() {
  const navigate = useNavigate();
  const { token } = useAuth();
  const headers = { Authorization: `Bearer ${token}` };

  // Profile state
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // Form state — inicializar com dados do localStorage para renderização rápida
  const [form, setForm] = useState(() => ({
    full_name: localStorage.getItem('user_name') || '',
    person_type: 'PF' as 'PF' | 'PJ',
    cpf: '',
    cnpj: '',
    phone: '',
    company_name: '',
    trade_name: '',
    state_registration: '',
    municipal_registration: '',
    address_street: '',
    address_number: '',
    address_complement: '',
    address_neighborhood: '',
    address_city: '',
    address_state: '',
    address_zip: '',
    birth_date: '',
    business_type: '',
    communication_preference: 'email',
  }));

  // Password change state
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [passwordMsg, setPasswordMsg] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);

  // Delete account state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [showDeletePw, setShowDeletePw] = useState(false);
  const [deletingAccount, setDeletingAccount] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  // Feedback state
  const [feedbackRating, setFeedbackRating] = useState(0);
  const [feedbackCategory, setFeedbackCategory] = useState('');
  const [feedbackMessage, setFeedbackMessage] = useState('');
  const [feedbackMsg, setFeedbackMsg] = useState('');
  const [sendingFeedback, setSendingFeedback] = useState(false);

  // Active tab
  const [activeTab, setActiveTab] = useState<'dados' | 'senha' | 'feedback' | 'conta'>('dados');

  // ---------------------------------------------------------------------------
  // Load profile
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!token) return;
    apiClient.get(apiUrl('/api/auth/me'), { headers })
      .then(res => {
        const p = res.data as ProfileData;
        setProfile(p);
        setForm({
          full_name: p.full_name || '',
          person_type: (p.person_type as 'PF' | 'PJ') || 'PF',
          cpf: p.cpf || '',
          cnpj: p.cnpj || '',
          phone: p.phone || '',
          company_name: p.company_name || '',
          trade_name: p.trade_name || '',
          state_registration: p.state_registration || '',
          municipal_registration: p.municipal_registration || '',
          address_street: p.address_street || '',
          address_number: p.address_number || '',
          address_complement: p.address_complement || '',
          address_neighborhood: p.address_neighborhood || '',
          address_city: p.address_city || '',
          address_state: p.address_state || '',
          address_zip: p.address_zip || '',
          birth_date: p.birth_date || '',
          business_type: p.business_type || '',
          communication_preference: p.communication_preference || 'email',
        });
      })
      .catch(() => setErrorMsg('Erro ao carregar perfil'))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  // ---------------------------------------------------------------------------
  // Save profile
  // ---------------------------------------------------------------------------

  const handleSaveProfile = async () => {
    setSaving(true);
    setSuccessMsg('');
    setErrorMsg('');
    try {
      // Only send non-empty fields
      const payload: Record<string, string> = {};
      for (const [key, value] of Object.entries(form)) {
        if (value && value.trim()) {
          payload[key] = value.trim();
        }
      }
      await apiClient.put(apiUrl('/api/auth/me'), payload, { headers });
      setSuccessMsg('Perfil salvo com sucesso!');
      setTimeout(() => setSuccessMsg(''), 4000);
    } catch (err) {
      const msg = axios.isAxiosError(err) ? (err.response?.data?.detail || 'Erro ao salvar') : 'Erro ao salvar';
      setErrorMsg(typeof msg === 'string' ? msg : 'Erro ao salvar perfil');
    } finally {
      setSaving(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Change password
  // ---------------------------------------------------------------------------

  const handleChangePassword = async () => {
    setPasswordMsg('');
    setPasswordError('');

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setPasswordError('As senhas não conferem');
      return;
    }
    if (passwordForm.new_password.length < 8) {
      setPasswordError('A nova senha deve ter pelo menos 8 caracteres');
      return;
    }

    setChangingPassword(true);
    try {
      await apiClient.post(apiUrl('/api/auth/change-password'), {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      }, { headers });
      setPasswordMsg('Senha alterada com sucesso!');
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
      setTimeout(() => setPasswordMsg(''), 4000);
    } catch (err) {
      const msg = axios.isAxiosError(err) ? (err.response?.data?.detail || 'Erro ao alterar senha') : 'Erro ao alterar senha';
      setPasswordError(typeof msg === 'string' ? msg : 'Erro ao alterar senha');
    } finally {
      setChangingPassword(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Send feedback
  // ---------------------------------------------------------------------------

  // ---------------------------------------------------------------------------
  // Delete account
  // ---------------------------------------------------------------------------

  const handleDeleteAccount = async () => {
    if (!deletePassword) return;
    setDeletingAccount(true);
    setDeleteError('');
    try {
      await apiClient.delete(apiUrl('/api/auth/delete-account'), {
        headers,
        data: { password: deletePassword, confirm: true },
      });
      // Logout after deletion
      localStorage.clear();
      window.location.href = '/login';
    } catch (err) {
      const msg = axios.isAxiosError(err) ? (err.response?.data?.detail || 'Erro ao excluir conta') : 'Erro ao excluir conta';
      setDeleteError(typeof msg === 'string' ? msg : 'Erro ao excluir conta');
    } finally {
      setDeletingAccount(false);
    }
  };

  const handleSendFeedback = async () => {
    if (feedbackRating === 0) return;
    setSendingFeedback(true);
    setFeedbackMsg('');
    try {
      await apiClient.post(apiUrl('/api/auth/feedback'), {
        rating: feedbackRating,
        category: feedbackCategory || null,
        message: feedbackMessage || null,
        page: 'profile',
      }, { headers });
      setFeedbackMsg('Obrigado pelo feedback! 🙏');
      setFeedbackRating(0);
      setFeedbackCategory('');
      setFeedbackMessage('');
      setTimeout(() => setFeedbackMsg(''), 4000);
    } catch {
      setFeedbackMsg('Erro ao enviar feedback');
    } finally {
      setSendingFeedback(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  const updateForm = (field: string, value: string) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="w-10 h-10 border-4 border-slate-700 border-t-green-400 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition mb-3"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Voltar ao Dashboard</span>
          </button>
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center">
              <User className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold">Meu Perfil</h1>
              <p className="text-slate-400 text-sm">{profile?.email} · Plano {profile?.plan?.toUpperCase()}</p>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-slate-800/50 rounded-xl p-1 border border-slate-700/50">
          {[
            { id: 'dados' as const, label: 'Dados Pessoais', icon: User },
            { id: 'senha' as const, label: 'Alterar Senha', icon: Lock },
            { id: 'feedback' as const, label: 'Feedback', icon: MessageSquare },
            { id: 'conta' as const, label: 'Conta', icon: ShieldAlert },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-medium transition ${
                activeTab === tab.id
                  ? 'bg-green-600 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Messages */}
        {successMsg && (
          <div className="mb-4 flex items-center gap-2 px-4 py-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> {successMsg}
          </div>
        )}
        {errorMsg && (
          <div className="mb-4 flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" /> {errorMsg}
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB: Dados Pessoais */}
        {/* ================================================================= */}
        {activeTab === 'dados' && (
          <div className="space-y-6">
            {/* Tipo de Pessoa */}
            <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                {form.person_type === 'PJ' ? <Building2 className="w-5 h-5 text-blue-400" /> : <User className="w-5 h-5 text-green-400" />}
                Tipo de Cadastro
              </h2>
              <div className="flex gap-3">
                {(['PF', 'PJ'] as const).map(type => (
                  <button
                    key={type}
                    onClick={() => updateForm('person_type', type)}
                    className={`flex-1 py-3 rounded-lg border text-sm font-medium transition ${
                      form.person_type === type
                        ? 'bg-green-600/20 border-green-500 text-green-400'
                        : 'bg-slate-800/30 border-slate-700/50 text-slate-400 hover:border-slate-600'
                    }`}
                  >
                    {type === 'PF' ? '👤 Pessoa Física' : '🏢 Pessoa Jurídica'}
                  </button>
                ))}
              </div>
            </div>

            {/* Dados Pessoais */}
            <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
              <h2 className="text-lg font-semibold mb-4">Dados Pessoais</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <ProfileInput label="Nome Completo" field="full_name" value={form.full_name} onFieldChange={updateForm} icon={User} placeholder="Seu nome completo" maxLength={200} />
                <ProfileInput label="Telefone" field="phone" value={form.phone} onFieldChange={updateForm} icon={Phone} placeholder="(11) 99999-9999" maxLength={15} mask="phone" />
                {form.person_type === 'PF' ? (
                  <>
                    <ProfileInput label="CPF" field="cpf" value={form.cpf} onFieldChange={updateForm} placeholder="000.000.000-00" maxLength={14} mask="cpf" />
                    <ProfileInput label="Data de Nascimento" field="birth_date" value={form.birth_date} onFieldChange={updateForm} type="date" />
                  </>
                ) : (
                  <>
                    <ProfileInput label="CNPJ" field="cnpj" value={form.cnpj} onFieldChange={updateForm} placeholder="00.000.000/0000-00" maxLength={18} mask="cnpj" />
                    <ProfileInput label="CPF do Responsável" field="cpf" value={form.cpf} onFieldChange={updateForm} placeholder="000.000.000-00" maxLength={14} mask="cpf" />
                    <ProfileInput label="Razão Social" field="company_name" value={form.company_name} onFieldChange={updateForm} icon={Building2} placeholder="Razão social da empresa" maxLength={200} />
                    <ProfileInput label="Nome Fantasia" field="trade_name" value={form.trade_name} onFieldChange={updateForm} placeholder="Nome fantasia" maxLength={200} />
                    <ProfileInput label="Inscrição Estadual" field="state_registration" value={form.state_registration} onFieldChange={updateForm} placeholder="Isento ou número" maxLength={30} />
                    <ProfileInput label="Inscrição Municipal" field="municipal_registration" value={form.municipal_registration} onFieldChange={updateForm} placeholder="Número" maxLength={30} />
                  </>
                )}
                <ProfileInput label="Tipo de Negócio" field="business_type" value={form.business_type} onFieldChange={updateForm} placeholder="MEI, ME, EPP, etc." maxLength={50} />
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-1">Preferência de Comunicação</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <select
                      value={form.communication_preference}
                      onChange={e => updateForm('communication_preference', e.target.value)}
                      className="w-full bg-slate-800/50 border border-slate-700/50 rounded-lg pl-10 pr-10 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-green-500/50 transition text-sm appearance-none cursor-pointer"
                    >
                      <option value="email">📧 Email</option>
                      <option value="telegram">💬 Telegram</option>
                      <option value="sms">📱 SMS</option>
                    </select>
                    <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
                  </div>
                </div>
              </div>
            </div>

            {/* Endereço */}
            <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <MapPin className="w-5 h-5 text-orange-400" />
                Endereço
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <ProfileInput label="Logradouro" field="address_street" value={form.address_street} onFieldChange={updateForm} placeholder="Rua, Avenida, etc." maxLength={200} />
                </div>
                <ProfileInput label="Número" field="address_number" value={form.address_number} onFieldChange={updateForm} placeholder="Nº" maxLength={20} />
                <ProfileInput label="Complemento" field="address_complement" value={form.address_complement} onFieldChange={updateForm} placeholder="Apto, Sala, etc." maxLength={100} />
                <ProfileInput label="Bairro" field="address_neighborhood" value={form.address_neighborhood} onFieldChange={updateForm} placeholder="Bairro" maxLength={100} />
                <ProfileInput label="Cidade" field="address_city" value={form.address_city} onFieldChange={updateForm} placeholder="Cidade" maxLength={100} />
                <ProfileInput label="UF" field="address_state" value={form.address_state} onFieldChange={updateForm} placeholder="SP" maxLength={2} />
                <ProfileInput label="CEP" field="address_zip" value={form.address_zip} onFieldChange={updateForm} placeholder="00000-000" maxLength={9} mask="cep" />
              </div>
            </div>

            {/* Save Button */}
            <div className="flex justify-end">
              <button
                onClick={handleSaveProfile}
                disabled={saving}
                className="flex items-center gap-2 px-6 py-3 bg-green-600 hover:bg-green-500 text-white rounded-xl font-medium transition disabled:opacity-50"
              >
                <Save className="w-5 h-5" />
                {saving ? 'Salvando...' : 'Salvar Perfil'}
              </button>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB: Alterar Senha */}
        {/* ================================================================= */}
        {activeTab === 'senha' && (
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6 max-w-md mx-auto">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Lock className="w-5 h-5 text-amber-400" />
              Alterar Senha
            </h2>

            {passwordMsg && (
              <div className="mb-4 flex items-center gap-2 px-4 py-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
                <CheckCircle2 className="w-4 h-4" /> {passwordMsg}
              </div>
            )}
            {passwordError && (
              <div className="mb-4 flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                <AlertTriangle className="w-4 h-4" /> {passwordError}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Senha Atual</label>
                <div className="relative">
                  <input
                    type={showCurrentPw ? 'text' : 'password'}
                    value={passwordForm.current_password}
                    onChange={e => setPasswordForm(p => ({ ...p, current_password: e.target.value }))}
                    className="w-full bg-slate-800/50 border border-slate-700/50 rounded-lg px-3 py-2.5 pr-10 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-green-500/50 transition text-sm"
                    placeholder="Digite sua senha atual"
                  />
                  <button type="button" onClick={() => setShowCurrentPw(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition">
                    {showCurrentPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Nova Senha</label>
                <div className="relative">
                  <input
                    type={showNewPw ? 'text' : 'password'}
                    value={passwordForm.new_password}
                    onChange={e => setPasswordForm(p => ({ ...p, new_password: e.target.value }))}
                    className="w-full bg-slate-800/50 border border-slate-700/50 rounded-lg px-3 py-2.5 pr-10 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-green-500/50 transition text-sm"
                    placeholder="Mín. 8 caracteres, 1 maiúscula, 1 número, 1 especial"
                  />
                  <button type="button" onClick={() => setShowNewPw(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition">
                    {showNewPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Confirmar Nova Senha</label>
                <div className="relative">
                  <input
                    type={showConfirmPw ? 'text' : 'password'}
                    value={passwordForm.confirm_password}
                    onChange={e => setPasswordForm(p => ({ ...p, confirm_password: e.target.value }))}
                    className="w-full bg-slate-800/50 border border-slate-700/50 rounded-lg px-3 py-2.5 pr-10 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-green-500/50 transition text-sm"
                    placeholder="Repita a nova senha"
                  />
                  <button type="button" onClick={() => setShowConfirmPw(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition">
                    {showConfirmPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <button
                onClick={handleChangePassword}
                disabled={changingPassword || !passwordForm.current_password || !passwordForm.new_password}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-amber-600 hover:bg-amber-500 text-white rounded-xl font-medium transition disabled:opacity-50"
              >
                <Lock className="w-4 h-4" />
                {changingPassword ? 'Alterando...' : 'Alterar Senha'}
              </button>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB: Feedback */}
        {/* ================================================================= */}
        {activeTab === 'feedback' && (
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-6 max-w-lg mx-auto">
            <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-blue-400" />
              Nos ajude a melhorar!
            </h2>
            <p className="text-slate-400 text-sm mb-6">
              Seu feedback é essencial para evoluirmos o NEXUS. Conte o que achou!
            </p>

            {feedbackMsg && (
              <div className={`mb-4 flex items-center gap-2 px-4 py-3 rounded-lg text-sm ${
                feedbackMsg.includes('Obrigado')
                  ? 'bg-green-500/10 border border-green-500/30 text-green-400'
                  : 'bg-red-500/10 border border-red-500/30 text-red-400'
              }`}>
                <CheckCircle2 className="w-4 h-4" /> {feedbackMsg}
              </div>
            )}

            {/* Stars */}
            <div className="mb-5">
              <label className="block text-sm font-medium text-slate-300 mb-2">Como foi sua experiência?</label>
              <div className="flex gap-2">
                {[1, 2, 3, 4, 5].map(i => (
                  <button
                    key={i}
                    onClick={() => setFeedbackRating(i)}
                    className="transition hover:scale-110"
                  >
                    <Star
                      className={`w-8 h-8 ${i <= feedbackRating ? 'fill-yellow-400 text-yellow-400' : 'text-slate-600'}`}
                    />
                  </button>
                ))}
              </div>
            </div>

            {/* Category */}
            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-300 mb-1">Categoria</label>
              <div className="flex flex-wrap gap-2">
                {[
                  { value: 'elogio', label: '👍 Elogio' },
                  { value: 'sugestao', label: '💡 Sugestão' },
                  { value: 'bug', label: '🐛 Bug' },
                  { value: 'reclamacao', label: '😟 Reclamação' },
                ].map(cat => (
                  <button
                    key={cat.value}
                    onClick={() => setFeedbackCategory(feedbackCategory === cat.value ? '' : cat.value)}
                    className={`px-3 py-1.5 rounded-full text-sm transition ${
                      feedbackCategory === cat.value
                        ? 'bg-green-600/30 border-green-500 text-green-400 border'
                        : 'bg-slate-700/50 text-slate-400 border border-transparent hover:border-slate-600'
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Message */}
            <div className="mb-5">
              <label className="block text-sm font-medium text-slate-300 mb-1">Comentário (opcional)</label>
              <textarea
                value={feedbackMessage}
                onChange={e => setFeedbackMessage(e.target.value)}
                rows={4}
                maxLength={1000}
                placeholder="Conte mais sobre sua experiência..."
                className="w-full bg-slate-800/50 border border-slate-700/50 rounded-lg px-3 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-green-500/50 transition text-sm resize-none"
              />
            </div>

            <button
              onClick={handleSendFeedback}
              disabled={sendingFeedback || feedbackRating === 0}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition disabled:opacity-50"
            >
              <MessageSquare className="w-4 h-4" />
              {sendingFeedback ? 'Enviando...' : 'Enviar Feedback'}
            </button>
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB: Conta (Exclusão) */}
        {/* ================================================================= */}
        {activeTab === 'conta' && (
          <div className="space-y-6 max-w-lg mx-auto">
            {/* Info */}
            <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-5">
              <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
                <User className="w-5 h-5 text-slate-400" />
                Informações da Conta
              </h2>
              <div className="space-y-2 text-sm text-slate-400">
                <p>Email: <span className="text-white">{profile?.email}</span></p>
                <p>Plano: <span className="text-white">{profile?.plan?.toUpperCase()}</span></p>
                <p>Conta criada em: <span className="text-white">{profile?.created_at ? new Date(profile.created_at).toLocaleDateString('pt-BR') : '—'}</span></p>
              </div>
            </div>

            {/* Danger Zone */}
            <div className="bg-red-500/5 rounded-xl border border-red-500/20 p-5">
              <h2 className="text-lg font-semibold mb-2 text-red-400 flex items-center gap-2">
                <Trash2 className="w-5 h-5" />
                Zona de Perigo
              </h2>
              <p className="text-sm text-slate-400 mb-4">
                Ao excluir sua conta, todos os seus dados (clientes, agendamentos, faturas, transações)
                serão removidos permanentemente. Esta ação é <strong className="text-red-400">irreversível</strong>.
              </p>

              {!showDeleteConfirm ? (
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="px-4 py-2.5 bg-red-600/20 border border-red-500/30 text-red-400 rounded-lg text-sm font-medium hover:bg-red-600/30 transition"
                >
                  Excluir Minha Conta
                </button>
              ) : (
                <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/30">
                  <p className="text-sm text-red-300 mb-3 font-medium">
                    Tem certeza? Digite sua senha para confirmar:
                  </p>
                  {deleteError && (
                    <div className="mb-3 flex items-center gap-2 text-red-400 text-sm">
                      <AlertTriangle className="w-4 h-4" /> {deleteError}
                    </div>
                  )}
                  <div className="relative mb-3">
                    <input
                      type={showDeletePw ? 'text' : 'password'}
                      value={deletePassword}
                      onChange={e => { setDeletePassword(e.target.value); setDeleteError(''); }}
                      placeholder="Sua senha de login"
                      className="w-full bg-slate-800/50 border border-red-500/30 rounded-lg px-3 py-2.5 pr-10 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-red-500/50 transition text-sm"
                    />
                    <button type="button" onClick={() => setShowDeletePw(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition">
                      {showDeletePw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={() => { setShowDeleteConfirm(false); setDeletePassword(''); setDeleteError(''); }}
                      className="flex-1 px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition"
                    >
                      Cancelar
                    </button>
                    <button
                      onClick={handleDeleteAccount}
                      disabled={deletingAccount || !deletePassword}
                      className="flex-1 px-4 py-2.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium transition disabled:opacity-50"
                    >
                      {deletingAccount ? 'Excluindo...' : 'Confirmar Exclusão'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
