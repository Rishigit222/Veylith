import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { AgentRun, Finding, Json, Notification, Overview, Scenario, ScenarioRun, Session, User } from './types';

const TOKEN_KEY = 'chronicle_guard_access_token';
const configuredBaseUrl = Constants.expoConfig?.extra?.apiBaseUrl as string | undefined;
export const API_BASE_URL = (configuredBaseUrl || process.env.EXPO_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

export class ApiError extends Error {
  status?: number;
  offline: boolean;

  constructor(message: string, status?: number, offline = false) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.offline = offline;
  }
}

async function token(): Promise<string | null> {
  return AsyncStorage.getItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const accessToken = await token();
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...(options.headers || {}),
      },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status})`;
      throw new ApiError(detail, response.status);
    }
    return body as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('Offline: unable to reach the Veylith API. Check your connection and API URL.', undefined, true);
  }
}

function listFrom<T>(body: unknown, keys: string[]): T[] {
  if (Array.isArray(body)) return body as T[];
  if (body && typeof body === 'object') {
    for (const key of keys) {
      const value = (body as Json)[key];
      if (Array.isArray(value)) return value as T[];
    }
  }
  return [];
}

export const api = {
  async login(email: string, password: string): Promise<Session> {
    const body = await request<Json>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
    const accessToken = String(body.access_token || body.token || body.session_token || '');
    if (!accessToken) throw new ApiError('The login response did not include a session token.');
    await AsyncStorage.setItem(TOKEN_KEY, accessToken);
    return { accessToken, user: (body.user || body.account) as User | undefined };
  },
  async me(): Promise<User> { return request<User>('/api/auth/me'); },
  async logout(): Promise<void> { await AsyncStorage.removeItem(TOKEN_KEY); },
  async hasSession(): Promise<boolean> { return Boolean(await token()); },
  async overview(): Promise<Overview> { return request<Overview>('/api/chronicle/overview'); },
  async agentRuns(): Promise<AgentRun[]> { return listFrom<AgentRun>(await request<unknown>('/api/chronicle/agent-runs'), ['runs', 'items', 'agent_runs']); },
  async notifications(): Promise<Notification[]> { return listFrom<Notification>(await request<unknown>('/api/chronicle/notifications'), ['notifications', 'items']); },
  async repairs(): Promise<Finding[]> { return listFrom<Finding>(await request<unknown>('/api/chronicle/repairs'), ['findings', 'repairs', 'items']); },
  async decideRepair(findingId: string, decision: 'approve' | 'reject'): Promise<Json> {
    return request<Json>(`/api/chronicle/repairs/${encodeURIComponent(findingId)}/decision`, { method: 'POST', body: JSON.stringify({ decision }) });
  },
  async scenarios(): Promise<Scenario[]> { return listFrom<Scenario>(await request<unknown>('/api/chronicle/scenarios'), ['scenarios', 'items']); },
  async runScenario(id: string): Promise<ScenarioRun> {
    return request<ScenarioRun>(`/api/chronicle/scenarios/${encodeURIComponent(id)}/run`, { method: 'POST', body: JSON.stringify({ scenario_id: id }) });
  },
};
