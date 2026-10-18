import { AccountButton } from './Account'
import './header-actions.css'

export function HeaderActions() {
  const products = new URLSearchParams(window.location.search).get('view') === 'products'
  return (
    <nav className="header-actions" aria-label="Navigation principale">
      <a
        className={`header-action${products ? '' : ' active-nav'}`}
        href="/"
        aria-current={products ? undefined : 'page'}
      >
        Tous les outils
      </a>
      <a
        className={`header-action header-products${products ? ' active-nav' : ''}`}
        href="/?view=products"
        aria-current={products ? 'page' : undefined}
      >
        Produits d’impression
      </a>
      <AccountButton />
    </nav>
  )
}
