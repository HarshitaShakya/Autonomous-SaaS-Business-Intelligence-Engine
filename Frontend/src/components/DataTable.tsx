import { useMemo, useState, type ReactNode } from 'react'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { Skeleton, cx } from './ui'

export type Column<T> = {
  key: string
  header: ReactNode
  render: (row: T) => ReactNode
  sortValue?: (row: T) => number | string
  align?: 'left' | 'right'
  width?: string
  mono?: boolean
}

export default function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  rowLabel,
  loading,
  empty,
  defaultSort,
  caption,
  dense,
}: {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  onRowClick?: (row: T) => void
  rowLabel?: (row: T) => string
  loading?: boolean
  empty?: ReactNode
  defaultSort?: { key: string; dir: 'asc' | 'desc' }
  caption: string
  dense?: boolean
}) {
  const [sort, setSort] = useState(defaultSort)
  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    if (!col?.sortValue) return rows
    const get = col.sortValue
    return [...rows].sort((a, b) => {
      const va = get(a)
      const vb = get(b)
      const r = va < vb ? -1 : va > vb ? 1 : 0
      return sort.dir === 'asc' ? r : -r
    })
  }, [rows, sort, columns])

  const toggle = (key: string) => {
    setSort((s) => (s?.key === key ? { key, dir: s.dir === 'desc' ? 'asc' : 'desc' } : { key, dir: 'desc' }))
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line">
            {columns.map((c) => {
              const active = sort?.key === c.key
              return (
                <th
                  key={c.key}
                  scope="col"
                  style={{ width: c.width }}
                  aria-sort={active ? (sort!.dir === 'asc' ? 'ascending' : 'descending') : c.sortValue ? 'none' : undefined}
                  className={cx('h-10 px-4 text-xs font-medium whitespace-nowrap text-fg-2', c.align === 'right' ? 'text-right' : 'text-left')}
                >
                  {c.sortValue ? (
                    <button type="button" onClick={() => toggle(c.key)} className={cx('inline-flex items-center gap-1 rounded hover:text-fg', active && 'text-fg')}>
                      {c.header}
                      {active ? sort!.dir === 'asc' ? <ArrowUp size={12} aria-hidden /> : <ArrowDown size={12} aria-hidden /> : <ArrowUpDown size={12} aria-hidden className="opacity-50" />}
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 5 }, (_, i) => (
                <tr key={i} className="border-b border-line last:border-0">
                  {columns.map((c) => (
                    <td key={c.key} className="px-4 py-3">
                      <Skeleton className="h-4" style={{ width: `${50 + ((i * 17 + c.key.length * 7) % 40)}%` }} />
                    </td>
                  ))}
                </tr>
              ))
            : sorted.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if (e.target !== e.currentTarget) return
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            onRowClick(row)
                          }
                        }
                      : undefined
                  }
                  tabIndex={onRowClick ? 0 : undefined}
                  aria-label={onRowClick && rowLabel ? rowLabel(row) : undefined}
                  className={cx('border-b border-line last:border-0', onRowClick && 'cursor-pointer hover:bg-raised/60 focus-visible:bg-raised/60')}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={cx('px-4 text-fg', dense ? 'py-2' : 'py-3', c.align === 'right' && 'num text-right', c.mono && 'font-mono text-xs')}>
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
        </tbody>
      </table>
      {!loading && rows.length === 0 && empty}
    </div>
  )
}
