const API_BASE = import.meta.env.VITE_API_PATH ?? "http://127.0.0.1:8000/api/v1";
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



export type JobStatusType = "PENDING" | "FAST_SCAN" | "WAITING_USER" | "DEEP_SCAN" | "TRACKING" | "EXTRACTING" | "COMPLETED" | "ERROR";

export interface ClipResult {
  id: string;
  file_url: string;
  start_timestamp: number;
  end_timestamp: number;
  duration: number;
}

export type Candidate = {
  id: string; 
  name: string;
  number: number;
  color_hex: string;
  image: string;
  is_target: boolean;
};

export interface JobStatus {
  job_id: string;
  status: JobStatusType;
  candidates?: Candidate[];
  clips: ClipResult[];
}

export interface ClipHistoryItem {
  id: string;
  file_url: string;
  duration: string;
}

export interface ClipHistoryGroup {
  job_id: string;
  target_number: number;
  generated_at: string;
  clips: ClipHistoryItem[];
}



export async function login(body: LoginBody): Promise<TokenPayload> {
  try {
    const res = await fetchWithTimeout(`${import.meta.env.VITE_API_PATH}/auth/login`, {
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
    if (err instanceof Error && err.name === "AbortError")
      throw new Error("Servidor não respondeu. Verifique se o backend está rodando e tente novamente.");
    throw err;
  }
}

export async function register(body: RegisterBody): Promise<TokenPayload> {
  try {
    const res = await fetchWithTimeout(`${import.meta.env.VITE_API_PATH}/auth/register`, {
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
    if (err instanceof Error && err.name === "AbortError")
      throw new Error("Servidor não respondeu. Verifique se o backend está rodando e tente novamente.");
    throw err;
  }
}



const TOKEN_KEY = "access_token";
const USER_KEY  = "user";

export function saveSession(payload: TokenPayload): void {
  localStorage.setItem(TOKEN_KEY, payload.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(payload.user));
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): UserResponse | null {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as UserResponse) : null;
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean {
  return Boolean(getToken());
}



export async function authRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  try {
    const res = await fetchWithTimeout(`${import.meta.env.VITE_API_PATH}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    });
    if (res.status === 401) {
      clearSession();
      window.location.href = "/login";
      throw new Error("Sessão expirada. Faça login novamente.");
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail ?? `Erro ${res.status}`);
    }
    return res.json() as Promise<T>;
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError")
      throw new Error("Servidor não respondeu. Verifique se o backend está rodando e tente novamente.");
    throw err;
  }
}



export async function createJob(
  video: File,
  targetNumber: number,
  startTs: number,
  endTs: number
): Promise<{ job_id: string; status: string }> {
  const token = getToken();
  const form  = new FormData();
  form.append("video", video);
  form.append("target_number", String(targetNumber));
  form.append("start_ts", String(startTs));
  form.append("end_ts", String(endTs))

  try {
    const res = await fetchWithTimeout(`${import.meta.env.VITE_API_PATH}/jobs/`, {
      method:  "POST",
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body:    form,
      // SEM Content-Type: browser define o boundary do multipart automaticamente
    });
    if (res.status === 401) {
      clearSession();
      window.location.href = "/login";
      throw new Error("Sessão expirada.");
    }
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail ?? "Erro ao iniciar análise.");
    }
    return res.json();
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError")
      throw new Error("Servidor não respondeu. Verifique se o backend está rodando e tente novamente.");
    throw err;
  }
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  return authRequest<JobStatus>(`/jobs/${jobId}`);
}

export async function listClips(): Promise<ClipHistoryGroup[]> {
  return authRequest<ClipHistoryGroup[]>("/clips/");
}

export async function downloadClip(fileUrl: string, filename: string): Promise<void> {
  const token = getToken();

  const res = await fetch(`${import.meta.env.VITE_API_PATH}${fileUrl}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok) throw new Error(`Erro ao baixar clipe: ${res.status}`);

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);

  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename.endsWith(".mp4") ? filename : `${filename}.mp4`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function requestPasswordReset(body: { email: string }): Promise<void> {
  try {
    const res = await fetchWithTimeout(`${import.meta.env.VITE_API_PATH}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail ?? "Erro ao solicitar redefinição de senha.");
    }
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError")
      throw new Error("Servidor não respondeu. Tente novamente.");
    throw err;
  }
}