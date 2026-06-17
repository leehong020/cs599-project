export interface HealthResponse {
  status: string;
  environment: string;
}

// 阶段 1 用健康检查证明 Vite 代理和 FastAPI 都可用。后续聊天流、
// OAuth 和设置接口继续沿用这种“类型化响应包装”的方式。
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch("/api/health");

  if (!response.ok) {
    throw new Error(`Health check failed with ${response.status}`);
  }

  return response.json() as Promise<HealthResponse>;
}
