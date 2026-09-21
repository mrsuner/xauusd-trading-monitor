import type { AccountSession, LoginInput, RegisterInput } from "./models";
import { mapAccountSession } from "./models";

const runtimeConfig = window.__TICKBASE_NEWS_CONFIG__ ?? {};
const accountApiBaseUrl =
  runtimeConfig.ACCOUNT_API_BASE_URL || import.meta.env.VITE_ACCOUNT_API_BASE_URL || "";

const mutatingMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let csrfToken: string | null = null;

export class AccountApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields?: Record<string, string[]>
  ) {
    super(message);
    this.name = "AccountApiError";
  }
}

export async function getAccountSession(): Promise<AccountSession> {
  const body = await accountRequest<{
    data: Parameters<typeof mapAccountSession>[0];
  }>("/me/news");
  return mapAccountSession(body.data);
}

export async function login(input: LoginInput): Promise<AccountSession> {
  await accountRequest("/auth/web/login", { method: "POST", body: input });
  return getAccountSession();
}

export async function register(input: RegisterInput): Promise<AccountSession> {
  await accountRequest("/auth/web/register", {
    method: "POST",
    body: {
      name: input.name,
      email: input.email,
      password: input.password,
      password_confirmation: input.passwordConfirmation
    }
  });
  return getAccountSession();
}

export async function logout(): Promise<void> {
  await accountRequest("/auth/web/logout", { method: "POST" });
  csrfToken = null;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
}

export async function accountRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!accountApiBaseUrl) {
    throw new AccountApiError(500, "account_api_not_configured", "ACCOUNT_API_BASE_URL is not configured.");
  }

  const method = (options.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (mutatingMethods.has(method)) {
    headers["X-CSRF-TOKEN"] = await ensureCsrfToken();
  }

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  const response = await fetch(`${accountApiBaseUrl.replace(/\/$/, "")}${path}`, {
    method,
    headers,
    body,
    credentials: "include"
  });

  if (response.status === 204) return null as T;
  const payload = await parseJson(response);
  if (!response.ok) {
    if (response.status === 419) csrfToken = null;
    const error = payload as {
      error?: string;
      message?: string;
      errors?: Record<string, string[]>;
      fields?: Record<string, string[]>;
    } | null;
    throw new AccountApiError(
      response.status,
      error?.error ?? "request_failed",
      error?.message ?? "Account request failed.",
      error?.errors ?? error?.fields
    );
  }

  return payload as T;
}

async function ensureCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  if (!accountApiBaseUrl) {
    throw new AccountApiError(500, "account_api_not_configured", "ACCOUNT_API_BASE_URL is not configured.");
  }

  const response = await fetch(`${accountApiBaseUrl.replace(/\/$/, "")}/auth/web/csrf-token`, {
    credentials: "include",
    headers: { Accept: "application/json" }
  });
  const payload = (await parseJson(response)) as { data?: { csrf_token?: string }; message?: string } | null;
  if (!response.ok || !payload?.data?.csrf_token) {
    throw new AccountApiError(
      response.status || 500,
      "csrf_unavailable",
      payload?.message ?? "CSRF protection is unavailable."
    );
  }

  csrfToken = payload.data.csrf_token;
  return csrfToken;
}

async function parseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}
