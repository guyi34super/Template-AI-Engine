import { cn } from '../../lib/utils'
import type { ReactNode } from 'react'

interface CardProps {
  title?: string
  description?: string
  children: ReactNode
  className?: string
  action?: ReactNode
}

export default function Card({ title, description, children, className, action }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6',
        className,
      )}
    >
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between">
          <div>
            {title && <h3 className="text-lg font-semibold text-[var(--color-text)]">{title}</h3>}
            {description && (
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">{description}</p>
            )}
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  )
}
