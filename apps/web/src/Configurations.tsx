import { useEffect, useRef, useState } from 'react'
import { Bookmark, Save } from 'lucide-react'
import { useAccount } from './Account'
import { post, readProfiles, request } from './api'
import { Button } from './components/ui/button'
import type { components } from '../../../packages/api-client/schema'

type Settings = Record<string, unknown>
type Configuration = components['schemas']['ConfigurationResponse']

function fingerprint(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(fingerprint).join(',')}]`
  if (value && typeof value === 'object')
    return `{${Object.entries(value)
      .filter(([key]) => key !== 'confirm_trim')
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, item]) => `${JSON.stringify(key)}:${fingerprint(item)}`)
      .join(',')}}`
  return JSON.stringify(value)
}
export function Configurations(props: {
  toolId: string
  compact?: boolean
  autoLoadDefault?: boolean
  settings: Settings
  onLoad: (settings: Settings) => void
}) {
  const { user, loading, open } = useAccount()
  const initialFingerprint = useRef(fingerprint(props.settings))
  // A different account always starts with a fresh personal list and selection.
  return (
    <PersonalConfigurations
      key={`${user?.id || 'guest'}:${props.toolId}`}
      {...props}
      initialFingerprint={initialFingerprint.current}
      ownerId={user?.id || ''}
      signedIn={!!user}
      loadingAccount={loading}
      openAccount={open}
    />
  )
}
function PersonalConfigurations({
  toolId,
  initialFingerprint,
  ownerId,
  settings,
  onLoad,
  signedIn,
  loadingAccount,
  openAccount,
  compact = false,
  autoLoadDefault = true,
}: {
  toolId: string
  initialFingerprint: string
  ownerId: string
  settings: Settings
  onLoad: (settings: Settings) => void
  signedIn: boolean
  loadingAccount: boolean
  openAccount: () => void
  compact?: boolean
  autoLoadDefault?: boolean
}) {
  const [items, setItems] = useState<Configuration[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(signedIn)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [legacy, setLegacy] = useState(() => (toolId === 'imposition' ? readProfiles() : {}))
  const latest = useRef({ settings, onLoad })
  latest.current = { settings, onLoad }
  const selected = items.find((item) => item.id === selectedId)
  const modified = selected && fingerprint(settings) !== fingerprint(selected.settings)
  const url = `/api/configurations?tool_id=${encodeURIComponent(toolId)}`
  function personalRequest<T>(target: string, init?: RequestInit) {
    const headers = new Headers(init?.headers)
    headers.set('X-Snackpress-Account', ownerId)
    return request<T>(target, { ...init, headers })
  }
  async function reload() {
    const list = await personalRequest<Configuration[]>(url)
    setItems(list)
    return list
  }
  useEffect(() => {
    if (!signedIn) return
    const controller = new AbortController()
    personalRequest<Configuration[]>(url, { signal: controller.signal })
      .then((list) => {
        setItems(list)
        const preset = list.find((item) => item.is_default)
        // Never replace changes made while the personal list was loading.
        if (
          autoLoadDefault &&
          preset &&
          initialFingerprint === fingerprint(latest.current.settings)
        ) {
          latest.current.onLoad(preset.settings)
          setSelectedId(preset.id)
          setName(preset.name)
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [signedIn, url, initialFingerprint, autoLoadDefault])
  async function action(work: () => Promise<void>) {
    if (busy) return
    setBusy(true)
    setError('')
    setNotice('')
    setConfirmDelete(false)
    try {
      await work()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  async function create(duplicate = false) {
    const value = await personalRequest<Configuration>(url, post({ name: name.trim(), settings }))
    if (fingerprint(latest.current.settings) === fingerprint(settings)) onLoad(value.settings)
    await reload()
    setSelectedId(value.id)
    setName(value.name)
    setNotice(
      duplicate
        ? 'Configuration dupliquée dans votre compte.'
        : 'Configuration enregistrée dans votre compte.',
    )
  }
  async function update(patch: Partial<Configuration>, message: string) {
    if (!selected) return
    const value = await personalRequest<Configuration>(`/api/configurations/${selected.id}`, {
      ...post({
        name: selected.name,
        settings: selected.settings,
        is_default: selected.is_default,
        schema_version: selected.schema_version,
        revision: selected.revision,
        ...patch,
      }),
      method: 'PUT',
    })
    if (patch.settings && fingerprint(latest.current.settings) === fingerprint(patch.settings))
      onLoad(value.settings)
    await reload()
    setName(value.name)
    setNotice(message)
  }
  async function importLegacy() {
    let count = 0
    const remaining = { ...legacy }
    // Preserve local copies; report partial success and retain failed entries for a retry.
    const list = await reload()
    for (const [oldName, value] of Object.entries(legacy)) {
      let candidate = oldName.slice(0, 60)
      let suffix = 1
      while (list.some((item) => item.name === candidate)) {
        candidate = `${oldName.slice(0, 45)} (import ${suffix++})`
      }
      try {
        const created = await personalRequest<Configuration>(
          url,
          post({ name: candidate, settings: value }),
        )
        list.push(created)
        delete remaining[oldName]
        count++
      } catch (e) {
        setLegacy(remaining)
        await reload()
        throw new Error(`${count} modèle(s) importé(s). ${(e as Error).message}`)
      }
    }
    setLegacy(remaining)
    await reload()
    setNotice(
      `${count} modèle(s) importé(s) dans votre compte. Les copies locales sont conservées.`,
    )
  }
  const management = (
    <>
      {modified && (
        <p className="configuration-modified">Modifiée — pensez à enregistrer vos changements.</p>
      )}
      <label className="field">
        <span>Nom de la configuration</span>
        <input
          value={name}
          maxLength={60}
          disabled={busy}
          placeholder="Ex. Cartes de visite — SRA3"
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') e.preventDefault()
          }}
        />
      </label>
      <div className="configuration-actions">
        {selected ? (
          <>
            <Button
              type="button"
              disabled={busy}
              onClick={() => void action(() => update({ settings }, 'Configuration mise à jour.'))}
            >
              <Save size={15} />
              Mettre à jour
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={busy || !name.trim() || name.trim() === selected.name}
              onClick={() => void action(() => create(true))}
            >
              Dupliquer
            </Button>
            <button
              type="button"
              disabled={busy || !name.trim() || name.trim() === selected.name}
              onClick={() =>
                void action(() => update({ name: name.trim() }, 'Configuration renommée.'))
              }
            >
              Renommer
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void action(() =>
                  update(
                    { is_default: !selected.is_default },
                    selected.is_default
                      ? 'Configuration par défaut retirée.'
                      : 'Cette configuration sera chargée à l’ouverture de l’outil.',
                  ),
                )
              }
            >
              {selected.is_default ? 'Retirer le choix par défaut' : 'Définir par défaut'}
            </button>
            <button type="button" disabled={busy} onClick={() => setConfirmDelete(true)}>
              Supprimer
            </button>
          </>
        ) : (
          <Button
            type="button"
            disabled={busy || !name.trim()}
            onClick={() => void action(() => create())}
          >
            <Save size={15} />
            Enregistrer sous…
          </Button>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            void action(async () => {
              await reload()
              setNotice(
                'Liste actualisée. Rechargez la configuration pour appliquer sa dernière version.',
              )
            })
          }
        >
          Actualiser la liste
        </button>
      </div>
      {selected && (
        <p className="configuration-hint">
          Pour dupliquer, saisissez un autre nom. Le choix par défaut utilise la version
          enregistrée.
        </p>
      )}
      {confirmDelete && selected && (
        <div className="configuration-delete" role="group" aria-label="Confirmer la suppression">
          <p>Supprimer « {selected.name} » de votre compte ?</p>
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              void action(async () => {
                await personalRequest(
                  `/api/configurations/${selected.id}?revision=${selected.revision}`,
                  { method: 'DELETE' },
                )
                await reload()
                setSelectedId('')
                setName('')
                setNotice('Configuration supprimée. Les réglages actuels sont conservés.')
              })
            }
          >
            Confirmer la suppression
          </Button>
          <button type="button" onClick={() => setConfirmDelete(false)}>
            Annuler
          </button>
        </div>
      )}
      {Object.keys(legacy).length > 0 && (
        <div className="configuration-import">
          <p>{Object.keys(legacy).length} modèle(s) enregistré(s) sur ce navigateur.</p>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => void action(importLegacy)}
          >
            Importer dans ce compte
          </Button>
        </div>
      )}
    </>
  )
  return (
    <section
      className={`personal-configurations${compact ? ' compact-configurations' : ''}`}
      aria-label="Mes configurations"
    >
      <h2>
        <Bookmark size={17} />
        Mes configurations
      </h2>
      {!signedIn ? (
        <>
          {!compact && <p>Retrouvez vos réglages sur tous vos appareils.</p>}
          <Button type="button" variant="outline" disabled={loadingAccount} onClick={openAccount}>
            Se connecter pour sauvegarder
          </Button>
        </>
      ) : (
        <>
          {!compact && <p>Vos réglages sont enregistrés dans votre compte.</p>}
          {loading ? (
            <p role="status">Chargement des configurations…</p>
          ) : (
            <>
              {items.length === 0 ? (
                <p>
                  Aucune configuration pour cet outil. Enregistrez vos premiers réglages ci-dessous.
                </p>
              ) : (
                <label className="field">
                  <span>Charger une configuration</span>
                  <select
                    value={selectedId}
                    disabled={busy}
                    onChange={(e) => {
                      const item = items.find((item) => item.id === e.target.value)
                      setSelectedId(e.target.value)
                      setConfirmDelete(false)
                      setNotice('')
                      setError('')
                      if (item) {
                        onLoad(item.settings)
                        setName(item.name)
                      } else setName('')
                    }}
                  >
                    <option value="">Nouvelle configuration</option>
                    {items.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                        {item.is_default ? ' — par défaut' : ''}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {compact ? (
                <details className="configuration-management">
                  <summary>Enregistrer ou gérer les configurations</summary>
                  {management}
                </details>
              ) : (
                management
              )}
            </>
          )}
        </>
      )}
      {busy && <p role="status">Enregistrement en cours…</p>}
      {error && (
        <p className="account-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="account-message" role="status">
          {notice}
        </p>
      )}
    </section>
  )
}
