// Get the base API URL from environment variables, defaulting to localhost for development
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Centralized helper to get full API endpoint URLs
export function getApiUrl(path: string): string {
  // Ensure path starts with a slash
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  
  // If the path already includes /api, don't duplicate it
  if (normalizedPath.startsWith('/api')) {
    return `${API_BASE_URL}${normalizedPath}`;
  }
  
  return `${API_BASE_URL}/api${normalizedPath}`;
}
