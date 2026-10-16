import React from 'react'
import ReactDOM from 'react-dom/client'
import '@fontsource-variable/nunito'
import '@fontsource/lilita-one/latin-400.css'
import './style.css'
import Studio from './Studio'
import './candy.css'
import './pdf-preview.css'
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Studio />
  </React.StrictMode>,
)
