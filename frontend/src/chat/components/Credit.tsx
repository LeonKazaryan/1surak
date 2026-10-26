import { cn } from '@/components/ui/utils'

/** «Данные предоставлены сервисом Яндекс.Расписания»: the terms want it right next to the data, as large and
 * in the same colour as the text around it, with a link to the service. */
export function Credit({ credit, className }: { credit: { text: string; link: string }; className?: string }) {
  return (
    <a
      href={credit.link}
      target="_blank"
      rel="noopener noreferrer"
      className={cn('block text-[12px] text-muted-foreground underline-offset-2 hover:underline', className)}
    >
      {credit.text}
    </a>
  )
}
