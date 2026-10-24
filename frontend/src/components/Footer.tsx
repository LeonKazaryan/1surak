export function Footer() {
  return (
    <footer className="mt-auto border-t border-border bg-white py-5">
      <div className="mx-auto max-w-6xl px-5 text-center">
        <p className="text-xs text-muted-foreground">
          Прототип для О! Хакатона 2026: бронирование и оплата имитируются.
        </p>
        <p className="mt-1 text-[11px] text-faint">© {new Date().getFullYear()} 1surak · команда beshparmak</p>
      </div>
    </footer>
  )
}
