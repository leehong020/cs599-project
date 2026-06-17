export interface GoogleAuthStatus {
  connected: boolean;
  needs_reconnect: boolean;
  oauth_configured: boolean;
  email: string | null;
  display_name: string | null;
  scopes: string[];
  message: string | null;
}

// 前端只跳转到后端 OAuth 入口。Google Client Secret 只存在后端 `.env`，
// 不能写进前端代码，也不能通过接口返回给浏览器。
export function startGoogleLogin(): void {
  window.location.href = "/api/auth/google/login";
}

export async function fetchGoogleStatus(): Promise<GoogleAuthStatus> {
  const response = await fetch("/api/auth/google/status");

  if (!response.ok) {
    throw new Error(`Google status failed with ${response.status}`);
  }

  return response.json() as Promise<GoogleAuthStatus>;
}

export async function disconnectGoogle(): Promise<void> {
  const response = await fetch("/api/auth/google/disconnect", {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`Google disconnect failed with ${response.status}`);
  }
}
