import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface ConfirmDeleteDialogProps {
  chatTitle: string | null
  open: boolean
  onCancel: () => void
  onConfirm: () => void
}

export function ConfirmDeleteDialog({ chatTitle, open, onCancel, onConfirm }: ConfirmDeleteDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => !next && onCancel()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Удалить поездку?</DialogTitle>
          <DialogDescription>
            {chatTitle ? `«${chatTitle}» будет удалена навсегда.` : 'Эта поездка будет удалена навсегда.'}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Отмена
          </Button>
          <Button variant="destructive" onClick={onConfirm}>
            Удалить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
