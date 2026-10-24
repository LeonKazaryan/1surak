export function readSidebarOpen(): boolean {
  const match = document.cookie.match(/(?:^|;\s*)sidebar_state=([^;]+)/)
  return match ? match[1] === 'true' : true
}
