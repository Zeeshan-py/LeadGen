"use client";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "production" ? "" : "http://localhost:8000");

const unsafeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export function getCookie(name: string) {
  if (typeof document === "undefined") {
    return "";
  }
  const prefix = `${name}=`;
  return (
    document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith(prefix))
      ?.slice(prefix.length) ?? ""
  );
}

export async function apiFetch(path: string, init?: RequestInit, retryAuth = true) {
  const method = (init?.method ?? "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type") && init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (unsafeMethods.has(method)) {
    const csrf = getCookie("leadforge_csrf");
    if (csrf) {
      headers.set("X-CSRF-Token", csrf);
    }
  }

  const response = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    credentials: "include",
    ...init,
    headers,
  });

  if (response.status !== 401 || !retryAuth || path.startsWith("/auth/")) {
    return response;
  }

  const refreshed = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": getCookie("leadforge_csrf"),
    },
  });

  if (!refreshed.ok) {
    window.dispatchEvent(new CustomEvent("leadforge:auth-required"));
    return response;
  }

  window.dispatchEvent(new CustomEvent("leadforge:auth-refreshed"));
  return apiFetch(path, init, false);
}
