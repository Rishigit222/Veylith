export type Json = Record<string, unknown>;

export type Session = {
  accessToken: string;
  user?: User;
};

export type User = {
  id?: string;
  email?: string;
  name?: string;
  role?: string;
};

export type Overview = {
  metrics?: Record<string, number>;
  recent?: unknown[];
  scenario?: Json;
  integration?: Json;
  [key: string]: unknown;
};

export type AgentRun = {
  id?: string;
  run_id?: string;
  scenario_id?: string;
  name?: string;
  status?: string;
  outcome?: string;
  started_at?: string;
  completed_at?: string;
  summary?: string;
  [key: string]: unknown;
};

export type Notification = {
  id?: string;
  title?: string;
  message?: string;
  severity?: string;
  read?: boolean;
  created_at?: string;
  [key: string]: unknown;
};

export type Finding = {
  code?: string;
  finding_id?: string;
  event_id?: string;
  action_id?: string;
  message?: string;
  status?: string;
  [key: string]: unknown;
};

export type Scenario = {
  id: string;
  name?: string;
  description?: string;
  status?: string;
  [key: string]: unknown;
};

export type EventItem = {
  id?: string;
  kind?: string;
  label?: string;
  detail?: string;
  time?: string;
  event_id?: string;
  source?: string;
  provenance?: string;
  [key: string]: unknown;
};

export type Verification = {
  valid?: boolean;
  violations?: Finding[];
  checked_event_ids?: string[];
  first_violation_event_id?: string;
  [key: string]: unknown;
};

export type ScenarioRun = {
  scenario_id?: string;
  outcome?: string;
  events?: EventItem[];
  verification?: Verification;
  baseline?: { allowed?: boolean; reasons?: string[]; [key: string]: unknown };
  counterexample?: EventItem[];
  [key: string]: unknown;
};
