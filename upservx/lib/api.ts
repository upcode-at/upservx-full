export function apiUrl(path: string): string {
  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location
    const scheme = protocol.startsWith("http") ? protocol : "http:"
    return `${scheme}//${hostname}:8000${path}`
  }
  return `http://localhost:8000${path}`
}

export function wsUrl(path: string): string {
  if (typeof window !== "undefined") {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:"
    return `${wsProtocol}//${window.location.hostname}:8000${path}`
  }
  return `ws://localhost:8000${path}`
}
