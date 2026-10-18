import { useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'

export function SettingsSection({
  title,
  summary,
  defaultOpen = false,
  children,
}: {
  title: string
  summary?: string
  defaultOpen?: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <details
      className="settings-section"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <span>
          <span className="settings-section-title">{title}</span>
          {summary && <small>{summary}</small>}
        </span>
        <ChevronDown size={18} aria-hidden="true" />
      </summary>
      <div className="settings-section-body">{children}</div>
    </details>
  )
}
