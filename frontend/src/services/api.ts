const API_BASE = "http://localhost:8000/api/v1";
const REQUEST_TIMEOUT_MS = 15000;

function fetchWithTimeout(url: string, options: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  return fetch(url, { ...options, signal: controller.signal }).finally(() =>
    clearTimeout(timeoutId)
  );
}

export interface UserResponse {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  max_clips_allowed: number;
}

export interface TokenPayload {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

export interface LoginBody {
  email: string;
  password: string;
}

export interface RegisterBody {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
}

export async function login(body: LoginBody): Promise<TokenPayload> {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail ?? "E-mail ou senha inválidos.");
    }
    return res.json();
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("Servidor não respondeu. Verifique se o backend está rodando e tente novamente.");
    }
    throw err;
  }
}

export async function register(body: RegisterBody): Promise<TokenPayload> {
  try {
    const res = await fetchWithTimeout(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      const detail = Array.isArray(data.detail) ? data.detail[0]?.msg ?? data.detail : data.detail;
      throw new Error(detail ?? "Erro ao registrar.");
    }
    return res.json();
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("Servidor não respondeu. Verifique se o backend está rodando e tente novamente.");
    }
    throw err;
  }
}
