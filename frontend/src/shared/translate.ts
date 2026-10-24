// __() for the SPAs, with Frappe's positional placeholders: __('Signed by {0}', [name]).
// The boot payload fills the messages map for the user's language; a missing string falls back to
// its source text.
let messages: Record<string, string> = {}

export function setMessages(next: Record<string, string>): void {
  messages = next
}

export function __(source: string, replace: Array<string | number> = []): string {
  const text = messages[source] ?? source
  return text.replace(/\{(\d+)\}/g, (match, index: string) => {
    const value = replace[Number(index)]
    return value === undefined ? match : String(value)
  })
}
