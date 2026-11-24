// Helper to get Authorization headers with Bearer token
export function getAuthHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const token = localStorage.getItem('access_token');
  const headers: Record<string, string> = { ...extraHeaders };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// Wrapper around fetch that automatically includes the Bearer JWT token
export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const headers = getAuthHeaders(options.headers as Record<string, string> || {});
  return fetch(url, {
    ...options,
    headers,
  });
}
