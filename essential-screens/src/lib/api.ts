const CONFIGURED_BACKEND_URL = import.meta.env.VITE_BACKEND_URL
const LOCAL_BACKEND_URL = 'http://localhost:8000'
const RENDER_BACKEND_URL = 'https://nutrisnap-backend.onrender.com'

function normalizeUrl(url: string | undefined): string | undefined {
  const trimmed = url?.trim().replace(/\/+$/, '')
  return trimmed || undefined
}

function getRenderSiblingBackendUrl(): string | undefined {
  if (typeof window === 'undefined' || !window.location.hostname.endsWith('.onrender.com')) {
    return undefined
  }

  const backendHost = window.location.hostname
    .replace(/-frontend(?=\.onrender\.com$)/, '-backend')
    .replace(/frontend(?=\.onrender\.com$)/, 'backend')

  if (backendHost === window.location.hostname) return undefined
  return `${window.location.protocol}//${backendHost}`
}

function getBackendUrls(): string[] {
  const urls = [
    normalizeUrl(CONFIGURED_BACKEND_URL),
    normalizeUrl(getRenderSiblingBackendUrl()),
    RENDER_BACKEND_URL,
    LOCAL_BACKEND_URL,
  ].filter((url): url is string => Boolean(url))

  return Array.from(new Set(urls))
}

async function getApiError(res: Response): Promise<string> {
  const text = await res.text()

  try {
    const data = JSON.parse(text)
    if (typeof data.detail === 'string') return data.detail
    if (data.detail) return JSON.stringify(data.detail)
  } catch {
    // Fall through to the raw response text.
  }

  return text || `${res.status} ${res.statusText}`
}

async function requestJson(path: string, init?: RequestInit) {
  const backendUrls = getBackendUrls()
  let lastError: Error | undefined

  for (let index = 0; index < backendUrls.length; index += 1) {
    const baseUrl = backendUrls[index]
    const canTryNext = index < backendUrls.length - 1

    let res: Response
    try {
      res = await fetch(`${baseUrl}${path}`, init)
    } catch (error: any) {
      lastError = error instanceof Error ? error : new Error(String(error))
      if (canTryNext) continue
      throw lastError
    }

    if (!res.ok) {
      const error = new Error(await getApiError(res))
      if (res.status === 404 && canTryNext) {
        lastError = error
        continue
      }
      throw error
    }

    try {
      return await res.json()
    } catch {
      lastError = new Error(`Invalid backend response from ${baseUrl}`)
      if (canTryNext) continue
      throw lastError
    }
  }

  throw lastError || new Error('Backend request failed')
}

async function resizeImage(file: File, maxWidth = 1200, quality = 0.7): Promise<Blob> {
  // Load image
  const imgBitmap = await createImageBitmap(file)

  const ratio = imgBitmap.width / imgBitmap.height
  const width = Math.min(maxWidth, imgBitmap.width)
  const height = Math.round(width / ratio)

  const canvas = new OffscreenCanvas(width, height)
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas not supported')
  ctx.drawImage(imgBitmap, 0, 0, width, height)

  // Convert to JPEG blob (smaller than PNG)
  const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality })
  return blob
}

export async function analyzeImage(file: File, userId = 'demo_user') {
  // Resize/compress on the client to reduce upload latency
  let uploadBlob: Blob
  try {
    uploadBlob = await resizeImage(file, 1200, 0.7)
  } catch (e) {
    // Fallback to original file if resizing fails
    uploadBlob = file
  }

  const form = new FormData()
  // Ensure filename and type are preserved
  form.append('file', uploadBlob, file.name.replace(/\.[^.]+$/, '.jpg'))
  form.append('user_id', userId)

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30000) // 30s

  try {
    return await requestJson(`/analyze?user_id=${encodeURIComponent(userId)}`, {
      method: 'POST',
      body: form,
      signal: controller.signal,
    })
  } finally {
    clearTimeout(timeout)
  }
}

export async function getHistory(userId: string) {
  return requestJson(`/history/${encodeURIComponent(userId)}`)
}

export async function getCoach(userId: string) {
  return requestJson(`/coach/${encodeURIComponent(userId)}`)
}

export async function chat(userId: string, message: string) {
  return requestJson(`/chat/${encodeURIComponent(userId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
}

export async function getChats(userId: string) {
  return requestJson(`/chats/${encodeURIComponent(userId)}`)
}

export async function voiceChat(userId: string, file: File) {
  const form = new FormData()
  form.append('file', file)
  return requestJson(`/voice_chat/${encodeURIComponent(userId)}`, {
    method: 'POST',
    body: form,
  })
}

export async function register(userData: any) {
  return requestJson('/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(userData),
  })
}

export async function login(credentials: any) {
  return requestJson('/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })
}
