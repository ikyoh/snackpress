import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight, Check, Pencil } from 'lucide-react'
import { Button } from './components/ui/button'
import {
  ComponentDimensions,
  VariantEditor,
  newId,
  newVariant,
  type Category,
  type Component,
  type Material,
  type Product,
} from './PrintCatalog'
import { PizzaTemplatePicker, usePizzaTemplates } from './PizzaTemplates'
import type { components } from '../../../packages/api-client/schema'

const steps = ['Produit', 'Format et papier', 'Fichiers et tracés', 'Vérification']

export function ProductCreationWizard({
  categories,
  materials,
  tools,
  initialCategory,
  signedIn,
  otherChanges,
  busy,
  onCancel,
  onCreate,
}: {
  categories: Category[]
  materials: Material[]
  tools: components['schemas']['ToolDefinition'][]
  initialCategory: string
  signedIn: boolean
  otherChanges: boolean
  busy: boolean
  onCancel: () => void
  onCreate: (product: Product) => Promise<void>
}) {
  const [step, setStep] = useState(0)
  const [error, setError] = useState('')
  const [formatMode, setFormatMode] = useState('custom')
  const [product, setProduct] = useState<Product>(() => ({
    id: newId(),
    name: '',
    category_id: categories.find((c) => c.id === initialCategory)?.id || categories[0].id,
    description: '',
    material_ids: materials.map((m) => m.id),
    finish_ids: [],
    variants: [{ ...newVariant(), name: 'Standard' }],
  }))
  const heading = useRef<HTMLHeadingElement>(null)
  const variant = product.variants[0]
  const component = variant.components[0]
  const pizzaTemplates = usePizzaTemplates(formatMode === 'pizza')
  useEffect(() => {
    heading.current?.focus()
  }, [step])

  function updateComponent(patch: Partial<Component>) {
    if (patch.pizza_template === null) setFormatMode('custom')
    setProduct((p) => ({
      ...p,
      variants: [{ ...p.variants[0], components: [{ ...p.variants[0].components[0], ...patch }] }],
    }))
  }
  function goTo(next: number) {
    setError('')
    setStep(next)
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setError('')
    if (step === 0 && !product.name.trim()) {
      setError('Donnez un nom à votre produit pour continuer.')
      return
    }
    if (step === 1 && formatMode === 'pizza' && !component.pizza_template) {
      setError('Choisissez un gabarit Pizza, ou utilisez un format personnalisé.')
      return
    }
    if (
      step === 2 &&
      component.guides.some((g) => g.tool === 'sushi') &&
      Math.max(component.width, component.height) > 2000
    ) {
      setError(
        'Sushi accepte un format de 2 000 mm maximum par côté. Revenez à « Format et papier » pour le modifier.',
      )
      return
    }
    if (step < steps.length - 1) {
      goTo(step + 1)
      return
    }
    try {
      const name = product.name.trim()
      await onCreate({
        ...product,
        name,
        variants: [{ ...variant, components: [{ ...component, name }] }],
      })
    } catch (e) {
      setError((e as Error).message)
    }
  }
  const fileMode =
    component.slots.length === 2
      ? 'separate'
      : component.slots[0].pages === 2
        ? 'combined'
        : 'recto'
  const fileLabel =
    fileMode === 'separate'
      ? 'Recto verso · 2 PDF d’une page'
      : fileMode === 'combined'
        ? 'Recto verso · 1 PDF de deux pages'
        : 'Recto seul · 1 PDF d’une page'
  const guidesLabel =
    component.guides
      .map((g) => tools.find((t) => t.id === g.tool)?.name || 'Perforations')
      .join(', ') || 'Aucun tracé supplémentaire'
  const materialLabel =
    materials.find((m) => m.id === component.material_id)?.name || 'Support à confirmer'

  return (
    <section className="print-wizard" aria-label="Assistant de création de produit">
      <ol className="print-wizard-steps" aria-label="Étapes de création">
        {steps.map((label, index) => (
          <li
            key={label}
            aria-current={index === step ? 'step' : undefined}
            data-complete={index < step || undefined}
          >
            <span className="print-wizard-step-number" aria-hidden="true">
              {index < step ? <Check size={18} /> : index + 1}
            </span>
            <span>{label}</span>
          </li>
        ))}
      </ol>
      <form onSubmit={(e) => void submit(e)}>
        <fieldset disabled={busy}>
          <div className="print-wizard-heading">
            <h2 ref={heading} tabIndex={-1}>
              {steps[step]}
            </h2>
            <Button type="button" variant="ghost" onClick={onCancel}>
              Annuler la création
            </Button>
          </div>
          {error && (
            <p className="alert error" role="alert">
              {error}
            </p>
          )}
          <div className="print-wizard-body">
            {step === 0 && (
              <>
                <p>Commencez par le nom et la catégorie. Vous choisirez le format juste après.</p>
                <label className="field">
                  <span>Nom du produit</span>
                  <input
                    required
                    maxLength={120}
                    value={product.name}
                    placeholder="Ex. Carte de visite"
                    onChange={(e) => setProduct({ ...product, name: e.target.value })}
                  />
                </label>
                <label className="field">
                  <span>Catégorie du produit</span>
                  <select
                    aria-label="Catégorie du produit"
                    value={product.category_id}
                    onChange={(e) => setProduct({ ...product, category_id: e.target.value })}
                  >
                    {categories.map((c) => (
                      <option value={c.id} key={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>
                    Description <small>(facultatif)</small>
                  </span>
                  <textarea
                    rows={3}
                    maxLength={1000}
                    value={product.description}
                    onChange={(e) => setProduct({ ...product, description: e.target.value })}
                  />
                </label>
              </>
            )}
            {step === 1 && (
              <>
                <p>Indiquez le format fini et le support de votre imprimé.</p>
                <label className="field">
                  <span>Définir le format</span>
                  <select
                    aria-label="Définir le format"
                    value={formatMode}
                    onChange={(e) => {
                      setFormatMode(e.target.value)
                      if (e.target.value === 'custom')
                        updateComponent({
                          pizza_template: null,
                          guides: component.guides.filter((g) => g.tool !== 'pizza'),
                        })
                    }}
                  >
                    <option value="custom">Format personnalisé</option>
                    <option value="pizza">Depuis un gabarit Pizza enregistré</option>
                  </select>
                </label>
                {formatMode === 'pizza' && (
                  <PizzaTemplatePicker
                    component={component}
                    source={pizzaTemplates}
                    onChange={updateComponent}
                  />
                )}
                <div className="tool-fields print-wizard-format">
                  <ComponentDimensions component={component} onChange={updateComponent} />
                </div>
                <label className="field">
                  <span>Support matière</span>
                  <select
                    aria-label="Support matière"
                    value={component.material_id}
                    onChange={(e) => updateComponent({ material_id: e.target.value })}
                  >
                    <option value="">À confirmer</option>
                    {materials.map((m) => (
                      <option value={m.id} key={m.id}>
                        {m.name}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            )}
            {step === 2 && (
              <>
                <p>
                  Définissez les fichiers attendus. Vous ajouterez vos PDF lors de la création du
                  BAT.
                </p>
                <label className="field">
                  <span>Fichiers PDF attendus</span>
                  <select
                    aria-label="Fichiers PDF attendus"
                    value={fileMode}
                    onChange={(e) =>
                      updateComponent({
                        slots:
                          e.target.value === 'separate'
                            ? [
                                { id: newId(), name: 'Recto', role: 'visual', pages: 1 },
                                { id: newId(), name: 'Verso', role: 'visual', pages: 1 },
                              ]
                            : [
                                {
                                  id: newId(),
                                  name: e.target.value === 'combined' ? 'Recto verso' : 'Recto',
                                  role: 'visual',
                                  pages: e.target.value === 'combined' ? 2 : 1,
                                },
                              ],
                      })
                    }
                  >
                    <option value="recto">Recto seul · 1 PDF d’une page</option>
                    <option value="separate">Recto verso · 2 PDF d’une page</option>
                    <option value="combined">Recto verso · 1 PDF de deux pages</option>
                  </select>
                </label>
                <VariantEditor
                  guidesOnly
                  choosePizza
                  variant={variant}
                  materials={materials}
                  finishes={[]}
                  tools={tools}
                  onChange={(next) => {
                    if (!next.components[0].pizza_template) setFormatMode('custom')
                    setProduct({ ...product, variants: [next] })
                  }}
                />
              </>
            )}
            {step === 3 && (
              <>
                <p>Relisez vos choix avant de créer le produit.</p>
                <section className="print-wizard-review">
                  <div>
                    <h3>{product.name}</h3>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => goTo(0)}
                      aria-label="Modifier le nom et la catégorie"
                    >
                      <Pencil size={16} aria-hidden="true" /> Modifier
                    </Button>
                  </div>
                  <p>{categories.find((c) => c.id === product.category_id)?.name}</p>
                  {product.description && <p>{product.description}</p>}
                </section>
                <section className="print-wizard-review">
                  <div>
                    <h3>Format et papier</h3>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => goTo(1)}
                      aria-label="Modifier le format et le papier"
                    >
                      <Pencil size={16} aria-hidden="true" /> Modifier
                    </Button>
                  </div>
                  <dl>
                    <dt>Format fini</dt>
                    <dd>
                      {component.width} × {component.height} mm
                    </dd>
                    <dt>Fond perdu</dt>
                    <dd>{component.bleed} mm par côté</dd>
                    <dt>Support</dt>
                    <dd>{materialLabel}</dd>
                    {component.pizza_template && (
                      <>
                        <dt>Gabarit Pizza</dt>
                        <dd>{component.pizza_template.name}</dd>
                      </>
                    )}
                  </dl>
                </section>
                <section className="print-wizard-review">
                  <div>
                    <h3>Fichiers et tracés</h3>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => goTo(2)}
                      aria-label="Modifier les fichiers et les tracés"
                    >
                      <Pencil size={16} aria-hidden="true" /> Modifier
                    </Button>
                  </div>
                  <dl>
                    <dt>Fichiers attendus</dt>
                    <dd>{fileLabel}</dd>
                    <dt>Tracés</dt>
                    <dd>{guidesLabel}</dd>
                  </dl>
                </section>
                <p className="field-hint">
                  Vous pourrez ensuite ajouter des finitions, des déclinaisons ou plusieurs
                  composants depuis la fiche du produit.
                </p>
                {!signedIn && (
                  <p className="field-hint">
                    Sans connexion, le produit restera temporaire et sera perdu au rechargement de
                    la page.
                  </p>
                )}
                {signedIn && otherChanges && (
                  <p className="field-hint">
                    Les autres modifications du catalogue seront aussi enregistrées.
                  </p>
                )}
              </>
            )}
          </div>
          <div className="print-wizard-footer">
            {step > 0 ? (
              <Button type="button" variant="outline" onClick={() => goTo(step - 1)}>
                <ArrowLeft size={18} aria-hidden="true" /> Précédent
              </Button>
            ) : (
              <span />
            )}
            <span>
              Étape {step + 1} sur {steps.length}
            </span>
            <Button type="submit">
              {busy ? (
                'Enregistrement…'
              ) : step === steps.length - 1 ? (
                'Créer le produit'
              ) : (
                <>
                  Continuer <ArrowRight size={18} aria-hidden="true" />
                </>
              )}
            </Button>
          </div>
        </fieldset>
      </form>
    </section>
  )
}
