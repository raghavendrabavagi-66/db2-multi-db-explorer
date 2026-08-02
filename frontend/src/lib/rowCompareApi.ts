import { apiGet, apiPost, ConnectCredentials, getRcSessionId } from "./session";

export interface ApiOk {
  ok: boolean;
  message?: string;
  error?: string;
}

export interface ComparisonMetrics {
  tables_source: number;
  matched: number;
  mismatched: number;
  missing: number;
  rows_label: string;
}

export interface RunComparisonResponse extends ApiOk {
  metrics?: ComparisonMetrics;
  tbody_html?: string;
  tbody_views?: Record<string, string>;
  table_count?: number;
}

export async function testDb2(body: {
  database: string;
  host: string;
  port: number;
  username: string;
  password: string;
}): Promise<ApiOk> {
  return apiPost<ApiOk>("/api/rc/test-db2", body);
}

export async function listAzureDatabases(body: {
  server: string;
  auth_method: string;
  trust_server_certificate: boolean;
}): Promise<ApiOk & { databases?: string[] }> {
  return apiPost("/api/rc/list-azure-databases", body);
}

export async function saveConnect(body: {
  rc_sid: string;
  database: string;
  host: string;
  port: number;
  username: string;
  password: string;
  server: string;
  az_database: string;
  auth_method: string;
  trust_server_certificate: boolean;
}): Promise<ApiOk> {
  return apiPost<ApiOk>("/api/rc/save-connect", body);
}

export async function fetchConnect(
  rcSid: string,
): Promise<ApiOk & { credentials?: ConnectCredentials }> {
  return apiGet(`/api/rc/connect/${encodeURIComponent(rcSid)}`);
}

export async function runComparison(body: {
  rc_sid: string;
  target_table_mode: string;
}): Promise<RunComparisonResponse> {
  return apiPost<RunComparisonResponse>("/api/rc/run-comparison", body);
}

export function buildSavePayload(
  rcSid: string,
  db2: {
    database: string;
    host: string;
    port: number;
    username: string;
    password: string;
  },
  azure: {
    server: string;
    database: string;
    auth_method: string;
    trust_server_certificate: boolean;
  },
) {
  return {
    rc_sid: rcSid,
    database: db2.database,
    host: db2.host,
    port: db2.port,
    username: db2.username,
    password: db2.password,
    server: azure.server,
    az_database: azure.database,
    auth_method: azure.auth_method,
    trust_server_certificate: azure.trust_server_certificate,
  };
}

export { getRcSessionId };
