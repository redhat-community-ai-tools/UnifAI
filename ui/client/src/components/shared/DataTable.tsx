import * as React from 'react'
import {
  ColumnDef,
  ColumnFiltersState,
  filterFns as defaultFilterFns,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  SortingFn,
  SortingState,
  useReactTable,
} from '@tanstack/react-table'
import { cn } from '@/lib/utils'
import {
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
} from 'lucide-react'

// Radix/shadcn UI components for inputs & selects
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select'

import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '../ui/table'

// ─── 1. SORT HELPERS ───────────────────────────────────────────────────────

const numericSort: SortingFn<any> = (rowA, rowB, columnId) => {
  const parse = (val: unknown) => {
    if (typeof val === 'number') return val
    const n = parseFloat(String(val).replace(/,/g, ''))
    return isNaN(n) ? NaN : n
  }
  const a = parse(rowA.getValue(columnId))
  const b = parse(rowB.getValue(columnId))
  if (isNaN(a) && isNaN(b)) return 0
  if (isNaN(a)) return 1
  if (isNaN(b)) return -1
  return a - b
}

const alphanumericSort: SortingFn<any> = (rowA, rowB, columnId) => {
  const rawA = rowA.getValue(columnId)
  const rawB = rowB.getValue(columnId)
  if (rawA == null && rawB == null) return 0
  if (rawA == null) return 1
  if (rawB == null) return -1
  return String(rawA).localeCompare(String(rawB), undefined, {
    numeric: true,
    sensitivity: 'base',
  })
}

// ─── 2. FILTER HELPERS ─────────────────────────────────────────────────────

const filterFns = {
  stripCommasIncludes: (row: any, columnId: string, filterValue: string) => {
    const cell = String(row.getValue(columnId)).replace(/,/g, '')
    return cell.includes(filterValue.replace(/,/g, ''))
  },
  ...defaultFilterFns,
}

// ─── 3. META & TYPES ───────────────────────────────────────────────────────

type DataTableColumnMeta = {
  align?: 'left' | 'center' | 'right'
  filterType?: 'text' | 'select'
  filterOptions?: string[]
}

export type DataTableColumn<T> = ColumnDef<T, any> & {
  meta?: DataTableColumnMeta
}

interface DataTableProps<T extends object> {
  columns: DataTableColumn<T>[]
  data: T[]
  enableSorting?: boolean
  enableGlobalFilter?: boolean
  enableColumnFilters?: boolean
  enablePagination?: boolean
  initialState?: Partial<{
    sorting: SortingState
    globalFilter: string
    columnFilters: ColumnFiltersState
    pagination: { pageIndex: number; pageSize: number }
  }>
  onSortingChange?: (updater: SortingState) => void
  expendedRow?: any;
  renderExpandedRow?: (row: T) => React.ReactNode
}

export function DataTable<T extends object>({
  columns,
  data,
  enableSorting = true,
  enableGlobalFilter = false,
  enableColumnFilters = true,
  enablePagination = true,
  initialState,
  onSortingChange,
  expendedRow,
  renderExpandedRow
}: DataTableProps<T>) {
  // ─── State Hooks
  const [sorting, setSorting] = React.useState<SortingState>(
    initialState?.sorting ?? []
  )
  const [globalFilter, setGlobalFilter] = React.useState(
    initialState?.globalFilter ?? ''
  )
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>(
    initialState?.columnFilters ?? []
  )
  const [pagination, setPagination] = React.useState({
    pageIndex: initialState?.pagination?.pageIndex ?? 0,
    pageSize: initialState?.pagination?.pageSize ?? 10,
  })

  // ─── Auto‐assign sortingFns
  const processedColumns = React.useMemo(() => {
    return columns.map(col => {
      if (col.enableSorting === false) return col
      if (col.sortingFn) return col
      const key = (col as any).accessorKey
      if (typeof key !== 'string') {
        return { ...col, sortingFn: alphanumericSort }
      }
      const sample = data.find(r => (r as any)[key] != null)?.[key as keyof T]
      const isNum =
        sample != null &&
        !isNaN(parseFloat(String(sample).replace(/[^0-9.-]/g, '')))
      return { ...col, sortingFn: isNum ? numericSort : alphanumericSort }
    })
  }, [columns, data])

  // ─── TanStack Table instance
  const table = useReactTable({
    data,
    columns: processedColumns,
    filterFns,
    state: {
      sorting: enableSorting ? sorting : [],
      globalFilter: enableGlobalFilter ? globalFilter : undefined,
      columnFilters: enableColumnFilters ? columnFilters : [],
      pagination: enablePagination ? pagination : undefined,
    },
    enableSorting,
    enableGlobalFilter,
    enableColumnFilters,
    enableMultiSort: true,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: enableColumnFilters
      ? getFilteredRowModel()
      : undefined,
    getSortedRowModel: enableSorting ? getSortedRowModel() : undefined,
    getPaginationRowModel: enablePagination
      ? getPaginationRowModel()
      : undefined,
    onSortingChange: u => {
      setSorting(u)
      if (onSortingChange) {
        const next = typeof u === 'function' ? u(sorting) : u
        onSortingChange(next)
      }
    },
    onGlobalFilterChange: setGlobalFilter,
    onColumnFiltersChange: setColumnFilters,
    onPaginationChange: setPagination,
    initialState: {
      sorting: initialState?.sorting ?? [],
      globalFilter: initialState?.globalFilter ?? '',
      columnFilters: initialState?.columnFilters ?? [],
      pagination: initialState?.pagination ?? { pageIndex: 0, pageSize: 10 },
    },
  })

  return (
    <div className="w-full">
      {/* Global Filter */}
      {enableGlobalFilter && (
        <div className="mb-4 flex items-center space-x-2">
          <Input
            value={table.getState().globalFilter ?? ''}
            onChange={e => table.setGlobalFilter(e.target.value)}
            placeholder="Search all columns..."
            className="input-dark-theme filter-input w-full"
          />
        </div>
      )}

      <Table>
        <TableHeader>
          {table.getHeaderGroups().map(hg => (
            <React.Fragment key={hg.id}>
              {/* Column Headers */}
              <TableRow>
                {hg.headers.map(header => {
                  const canSort = enableSorting && header.column.getCanSort()
                  const isSorted = header.column.getIsSorted()
                  const align = (header.column.columnDef.meta as any)?.align

                  return (
                    <TableHead
                      key={header.id}
                      className={cn(
                        align === 'center'     ? 'text-center' :
                        align === 'right'      ? 'text-right' : 'text-left',
                        canSort && 'cursor-pointer select-none hover:text-foreground transition-colors'
                      )}
                      onClick={
                        canSort
                          ? () => header.column.toggleSorting(undefined, true)
                          : undefined
                      }
                    >
                      <div className="inline-flex items-center">
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                        {canSort && (
                          <span className="ml-1 flex-shrink-0">
                            {isSorted === 'asc' ? (
                              <ChevronUp className="h-4 w-4 text-primary" />
                            ) : isSorted === 'desc' ? (
                              <ChevronDown className="h-4 w-4 text-primary" />
                            ) : (
                              <ChevronsUpDown className="h-4 w-4 text-muted-foreground" />
                            )}
                          </span>
                        )}
                      </div>
                    </TableHead>
                  )
                })}
              </TableRow>

              {/* Per-Column Filters */}
              {enableColumnFilters && (
                <TableRow className="items-center">
                  {hg.headers.map(header => {
                    const canFilter = header.column.getCanFilter()
                    const { filterType = 'text', filterOptions, align } =
                      (header.column.columnDef.meta ?? {}) as DataTableColumnMeta

                    if (!canFilter) {
                      return <TableCell key={header.id + '-filter'} />
                    }

                    return (
                      <TableCell
                        key={header.id + '-filter'}
                        className={cn(
                          'py-3',
                          align === 'center' ? 'justify-center' :
                            align === 'right' ? 'justify-end' : 'justify-start'
                        )}
                      >
                        {filterType === 'select' && filterOptions ? (
                          <Select
                            value={(header.column.getFilterValue() as string) ?? '__CLEAR__'}
                            onValueChange={val => {
                              header.column.setFilterValue(
                                val === '__CLEAR__' ? undefined : val
                              )
                            }}
                          >
                            <SelectTrigger className="select-dark-theme filter-input w-full h-8 bg-background border-border text-foreground">
                              <SelectValue placeholder="All" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="__CLEAR__">All</SelectItem>
                              {filterOptions.map(opt => (
                                <SelectItem key={opt} value={opt}>
                                  {opt}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <Input
                            type="text"
                            value={(header.column.getFilterValue() as string) ?? ''}
                            onChange={e =>
                              header.column.setFilterValue(e.target.value)
                            }
                            placeholder="Filter…"
                            className="input-dark-theme filter-input w-full h-8 bg-background border-border text-foreground"
                          />
                        )}
                      </TableCell>
                    )
                  })}
                </TableRow>
              )}
            </React.Fragment>
          ))}
        </TableHeader>

        <TableBody>
          {table.getRowModel().rows.length ? (
            table.getRowModel().rows.map((row, index) => {
  const doc = row.original as Document;

  return (
    <React.Fragment key={row.id}>
      <TableRow
        className={cn(
          "animate-stagger-in border-b border-border/50 hover:bg-muted/50 hover:-translate-y-0.5 hover:shadow-lg transition-all duration-300",
          index < 6 && `delay-[${index * 100}ms]`
        )}
      >
        {row.getVisibleCells().map(cell => {
          const align = (cell.column.columnDef.meta as any)?.align;
          return (
            <TableCell
              key={cell.id}
              className={cn(
                "text-foreground",
                align === 'center' ? 'text-center' :
                  align === 'right' ? 'text-right' : undefined
              )}
            >
              {flexRender(cell.column.columnDef.cell, cell.getContext())}
            </TableCell>
          );
        })}
      </TableRow>

      {expendedRow === row.original && (
        <TableRow className="bg-muted/40 transition-all duration-300">
          <TableCell colSpan={row.getVisibleCells().length}>
            {renderExpandedRow?.(row.original)}
          </TableCell>
        </TableRow>
      )}

    </React.Fragment>
  );
})

          ) : (
            <TableRow>
              <TableCell colSpan={columns.length} className="text-center py-4 text-muted-foreground">
                No data to display.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Pagination */}
      {enablePagination && (
        <div className="flex items-center justify-between py-4">
          <span className="text-sm text-muted-foreground">
            Page <strong>{table.getState().pagination.pageIndex + 1} of {table.getPageCount()}</strong>
            {' '}(documents{' '}
            {table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1}-
            {Math.min(
              (table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize,
              table.getFilteredRowModel().rows.length
            )}
            {' '}out of {table.getFilteredRowModel().rows.length})
          </span>
          <div className="flex items-center space-x-2">
            <button
              className="btn-animated px-3 py-1 border border-border text-muted-foreground rounded-lg hover:bg-muted hover:text-foreground transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              Previous
            </button>
            <button
              className="btn-animated px-3 py-1 border border-border text-foreground rounded-lg hover:bg-muted transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}