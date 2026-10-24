import { Fragment, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeftIcon } from '@heroicons/react/20/solid'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { SidebarTrigger } from '@/components/ui/sidebar'

export interface Crumb {
  label: string
  href?: string
  pending?: boolean
}

interface PageHeaderProps {
  breadcrumb: Crumb[]
  headerRight?: ReactNode
}

export function PageHeader({ breadcrumb, headerRight }: PageHeaderProps) {
  const parent = [...breadcrumb].reverse().find((c) => c.href)
  const current = breadcrumb.at(-1)

  return (
    <header className="z-30 flex h-14 shrink-0 items-center gap-2 px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-1 data-[orientation=vertical]:h-4" />

      {parent ? (
        <Link
          to={parent.href!}
          className="flex min-w-0 items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground md:hidden"
        >
          <ChevronLeftIcon className="h-4 w-4 shrink-0" />
          <span className="truncate">{parent.label}</span>
        </Link>
      ) : (
        <span className="truncate text-sm font-medium text-foreground md:hidden">{current?.label}</span>
      )}

      <Breadcrumb className="hidden min-w-0 md:block">
        <BreadcrumbList className="flex-nowrap">
          {breadcrumb.map((crumb, i) => {
            const last = i === breadcrumb.length - 1
            return (
              <Fragment key={`${crumb.label}-${i}`}>
                <BreadcrumbItem className={last ? 'min-w-0' : undefined}>
                  {crumb.pending ? (
                    <>
                      <div data-testid="title-skeleton" aria-hidden className="skeleton-reveal">
                        <Skeleton className="h-4 w-40" />
                      </div>
                      <span role="status" className="sr-only">
                        Загрузка
                      </span>
                    </>
                  ) : last || !crumb.href ? (
                    <BreadcrumbPage className="truncate">{crumb.label}</BreadcrumbPage>
                  ) : (
                    <BreadcrumbLink asChild>
                      <Link to={crumb.href}>{crumb.label}</Link>
                    </BreadcrumbLink>
                  )}
                </BreadcrumbItem>
                {!last && <BreadcrumbSeparator />}
              </Fragment>
            )
          })}
        </BreadcrumbList>
      </Breadcrumb>
      {headerRight && <div className="ml-auto flex shrink-0 items-center gap-2">{headerRight}</div>}
    </header>
  )
}
