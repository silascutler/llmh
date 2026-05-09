import { cookies } from "next/headers";

const publicBase = process.env.NEXT_PUBLIC_API_BASE_URL;
const internalBase = process.env.API_INTERNAL_BASE_URL ?? publicBase;

function requireBaseUrl(baseUrl: string | undefined) {
  if (!baseUrl) {
    throw new Error("API base URL is not configured");
  }
  return baseUrl;
}

export async function serverApi<T>(path: string, init?: RequestInit): Promise<T> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.getAll().map((cookie) => `${cookie.name}=${cookie.value}`).join("; ");

  const res = await fetch(`${requireBaseUrl(internalBase)}${path}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(cookieHeader ? { Cookie: cookieHeader } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!res.ok) {
    const error = new Error(`${res.status} ${res.statusText}`);
    (error as Error & { status?: number }).status = res.status;
    throw error;
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}
