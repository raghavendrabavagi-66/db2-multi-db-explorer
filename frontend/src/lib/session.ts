const RC_SID_KEY = "rc_sid";

export function getRcSessionId(): string {
  let sid = sessionStorage.getItem(RC_SID_KEY);
  if (!sid) {
    sid =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `rc-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    sessionStorage.setItem(RC_SID_KEY, sid);
  }
  return sid;
}

export function setRcSessionId(sid: string): void {
  sessionStorage.setItem(RC_SID_KEY, sid);
}

export function clearRcSessionId(): void {
  sessionStorage.removeItem(RC_SID_KEY);
}

export interface ConnectCredentials {
  cmp_db2_database: string;
  cmp_db2_host: string;
  cmp_db2_port: number;
  cmp_db2_user: string;
  cmp_db2_password: string;
  cmp_az_server: string;
  cmp_az_database: string;
  cmp_az_auth: string;
  cmp_az_trust_cert: boolean;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = (await res.json()) as T & { detail?: string };
  if (!res.ok) {
    const message =
      typeof payload === "object" && payload && "detail" in payload
        ? String(payload.detail)
        : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return payload;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path);
  const payload = (await res.json()) as T & { detail?: string };
  if (!res.ok) {
    throw new Error(
      typeof payload === "object" && payload && "detail" in payload
        ? String(payload.detail)
        : `Request failed (${res.status})`,
    );
  }
  return payload;
}
