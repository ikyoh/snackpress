import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { LogOut, UserRound, X } from 'lucide-react'
import { ApiError, post, request } from './api'
import { Button } from './components/ui/button'
import './account.css'
import type { components } from '../../../packages/api-client/schema'

type User = components['schemas']['AccountResponse']
type Mode = 'login' | 'register' | 'forgot' | 'verify' | 'reset' | 'account'
const link = new URLSearchParams(window.location.hash.slice(1))
const initialMode = link.get('account')
const initialToken = link.get('token') || ''
if (initialMode === 'verify' || initialMode === 'reset') {
  window.history.replaceState(null, '', window.location.pathname + window.location.search)
}
const AccountContext = createContext<{
  user: User | null
  loading: boolean
  open: () => void
}>({ user: null, loading: true, open: () => {} })
export const useAccount = () => useContext(AccountContext)

export function AccountProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<Mode | null>(
    initialMode === 'verify' || initialMode === 'reset' ? initialMode : null,
  )
  const [token, setToken] = useState(initialToken)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  const channel = useRef<BroadcastChannel | null>(null)
  const refreshVersion = useRef(0)
  const authBusy = useRef(false)
  const refresh = useCallback(async () => {
    if (authBusy.current) return
    const version = ++refreshVersion.current
    try {
      const account = await request<User>('/api/auth/me')
      if (version === refreshVersion.current) setUser(account)
    } catch (e) {
      if (version === refreshVersion.current && e instanceof ApiError && e.status === 401)
        setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => {
    void refresh()
    const expired = () => {
      refreshVersion.current++
      setUser(null)
      setError('Votre session a expiré. Reconnectez-vous.')
      setMode('login')
    }
    const focus = () => {
      void refresh()
    }
    const incomingLink = () => {
      const fragment = new URLSearchParams(window.location.hash.slice(1))
      const nextMode = fragment.get('account')
      if (nextMode === 'verify' || nextMode === 'reset') {
        setToken(fragment.get('token') || '')
        setMode(nextMode)
        setError('')
        setMessage('')
        setPassword('')
        setConfirmation('')
        window.history.replaceState(null, '', window.location.pathname + window.location.search)
      }
    }
    window.addEventListener('hashchange', incomingLink)
    window.addEventListener('snackpress-session-expired', expired)
    window.addEventListener('focus', focus)
    if ('BroadcastChannel' in window) {
      channel.current = new BroadcastChannel('snackpress-account')
      channel.current.onmessage = () => {
        void refresh()
      }
    }
    return () => {
      window.removeEventListener('hashchange', incomingLink)
      window.removeEventListener('snackpress-session-expired', expired)
      window.removeEventListener('focus', focus)
      channel.current?.close()
    }
  }, [refresh])
  useEffect(() => {
    if (mode && !dialog.current?.open) dialog.current?.showModal()
    else if (!mode) dialog.current?.close()
  }, [mode])
  function change(next: Mode) {
    setMode(next)
    setError('')
    setMessage('')
    setPassword('')
    setConfirmation('')
  }
  const open = () => change(user ? 'account' : 'login')
  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (busy || !mode) return
    if ((mode === 'verify' || mode === 'reset') && password !== confirmation) {
      setError('Les deux mots de passe doivent être identiques.')
      return
    }
    authBusy.current = true
    refreshVersion.current++
    setBusy(true)
    setError('')
    setMessage('')
    try {
      if (mode === 'login') {
        setUser(await request<User>('/api/auth/login', post({ email, password })))
        setMode(null)
        channel.current?.postMessage('changed')
      } else if (mode === 'account') {
        await request('/api/auth/logout', post({}))
        setUser(null)
        setMode(null)
        channel.current?.postMessage('changed')
      } else {
        const endpoint = {
          register: 'register',
          forgot: 'forgot-password',
          verify: 'verify',
          reset: 'reset-password',
        }[mode]
        const data = mode === 'verify' || mode === 'reset' ? { token, password } : { email }
        const result = await request<{ message: string }>(`/api/auth/${endpoint}`, post(data))
        setMessage(result.message)
        if (mode === 'verify' || mode === 'reset') {
          setMode('login')
          setToken('')
          setUser(null)
          channel.current?.postMessage('changed')
        }
      }
      setPassword('')
      setConfirmation('')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      authBusy.current = false
      setBusy(false)
    }
  }
  const titles: Record<Mode, string> = {
    login: 'Retrouvez vos réglages.',
    register: 'Créez votre compte.',
    forgot: 'Un nouveau mot de passe.',
    verify: 'Bienvenue chez Snackpress.',
    reset: 'Choisissez votre mot de passe.',
    account: 'Votre compte.',
  }
  return (
    <AccountContext.Provider value={{ user, loading, open }}>
      {children}
      <dialog
        ref={dialog}
        className="account-dialog"
        aria-labelledby="account-title"
        onClose={() => {
          setMode(null)
          setPassword('')
          setConfirmation('')
        }}
      >
        <button
          type="button"
          className="account-close"
          aria-label="Fermer le compte"
          onClick={() => setMode(null)}
        >
          <X size={21} />
        </button>
        {mode && (
          <form onSubmit={(e) => void submit(e)}>
            <h2 id="account-title">{titles[mode]}</h2>
            <p className="account-intro">
              {mode === 'account'
                ? user?.email
                : mode === 'register'
                  ? 'Recevez un lien par e-mail pour choisir votre mot de passe. Vos configurations vous suivront sur tous vos appareils.'
                  : mode === 'forgot'
                    ? 'Recevez un lien pour récupérer l’accès à votre compte.'
                    : mode === 'verify' || mode === 'reset'
                      ? 'Choisissez au moins 15 caractères, par exemple une phrase facile à retenir.'
                      : 'Connectez-vous pour enregistrer et retrouver vos configurations personnelles.'}
            </p>
            {error && (
              <p className="account-error" role="alert">
                {error}
              </p>
            )}
            {message && (
              <p className="account-message" role="status">
                {message}
              </p>
            )}
            {['login', 'register', 'forgot'].includes(mode) && (
              <label className="field">
                <span>Adresse e-mail</span>
                <input
                  type="email"
                  autoComplete="email"
                  required
                  maxLength={254}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
            )}
            {['login', 'verify', 'reset'].includes(mode) && (
              <label className="field">
                <span>Mot de passe</span>
                <input
                  type="password"
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  required
                  minLength={mode === 'login' ? undefined : 15}
                  maxLength={128}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
            )}
            {['verify', 'reset'].includes(mode) && (
              <label className="field">
                <span>Confirmer le mot de passe</span>
                <input
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={15}
                  maxLength={128}
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                />
              </label>
            )}
            <Button type="submit" disabled={busy}>
              {busy
                ? 'Veuillez patienter…'
                : {
                    login: 'Se connecter',
                    register: 'Recevoir le lien d’activation',
                    forgot: 'Recevoir le lien de réinitialisation',
                    verify: 'Activer mon compte',
                    reset: 'Enregistrer le mot de passe',
                    account: 'Se déconnecter',
                  }[mode]}
              {mode === 'account' && <LogOut size={16} />}
            </Button>
            <nav className="account-links" aria-label="Options du compte">
              {mode === 'login' && (
                <>
                  <button type="button" onClick={() => change('register')}>
                    Créer un compte
                  </button>
                  <button type="button" onClick={() => change('forgot')}>
                    Mot de passe oublié ?
                  </button>
                </>
              )}
              {mode !== 'login' && mode !== 'account' && (
                <button type="button" onClick={() => change('login')}>
                  Revenir à la connexion
                </button>
              )}
              {mode === 'verify' && (
                <button type="button" onClick={() => change('register')}>
                  Recevoir un nouveau lien
                </button>
              )}
              {mode === 'reset' && (
                <button type="button" onClick={() => change('forgot')}>
                  Recevoir un nouveau lien
                </button>
              )}
            </nav>
            {mode !== 'account' && (
              <p className="account-footnote">Les outils restent accessibles sans compte.</p>
            )}
          </form>
        )}
      </dialog>
    </AccountContext.Provider>
  )
}

export function AccountButton() {
  const { user, loading, open } = useAccount()
  return (
    <button
      type="button"
      className="account-button"
      onClick={open}
      disabled={loading}
      aria-label={user ? 'Mon compte' : 'Se connecter'}
      title={user?.email}
    >
      <UserRound size={18} />
      <span>{loading ? 'Chargement…' : user ? 'Mon compte' : 'Se connecter'}</span>
    </button>
  )
}
