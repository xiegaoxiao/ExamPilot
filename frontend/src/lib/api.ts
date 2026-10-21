export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: `请求失败 (${response.status})` }));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail),
    );
  }
  return response.json() as Promise<T>;
}
export function post<T>(path: string, data: unknown = {}): Promise<T> {
  return api<T>(path, { method: "POST", body: JSON.stringify(data) });
}
export const errorText = (error: unknown) =>
  error instanceof Error ? error.message : "操作失败，请稍后重试";
export function query(
  values: Record<string, string | number | undefined | null>,
): string {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "")
      params.set(key, String(value));
  });
  return params.size ? `?${params}` : "";
}
