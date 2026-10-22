import React, { useCallback, useEffect, useState } from 'react';
import { ScrollView, Text } from 'react-native';
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { RootStackParamList } from '../../App';
import { api, ApiError } from '../api';
import type { ScenarioRun } from '../types';
import { Card, Pill, Screen, StateView, colors, styles } from '../ui';

export function IncidentScreen() {
  const route = useRoute<RouteProp<RootStackParamList, 'Incident'>>();
  const id = route.params?.scenarioId || route.params?.runId || 'SCN-042';
  const [data, setData] = useState<ScenarioRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try { setData(await api.runScenario(id)); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Unable to load incident details.'); }
    finally { setLoading(false); }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const verification = data?.verification;
  const valid = verification?.valid === true;

  return <Screen title="Incident details" subtitle={id}>
    <ScrollView contentContainerStyle={styles.scrollContent}>
      <StateView loading={loading && !data} error={!data && error ? error : undefined} onRetry={load} />
      {data ? <>
        <Card><Text style={styles.label}>Outcome</Text><Pill label={data.outcome || (valid ? 'ALLOW' : 'REJECTED')} tone={valid ? 'success' : 'danger'} /><Text style={[styles.body, { marginTop: 12 }]}>Baseline: {data.baseline?.allowed ? 'ALLOW' : 'REJECT'} · Verifier: {valid ? 'ALLOW' : 'REJECT'}</Text></Card>
        <Card><Text style={styles.sectionTitle}>Event timeline</Text>{(data.events || []).length ? data.events?.map((event, index) => <Card key={String(event.id || event.event_id || index)} style={styles.timelineCard}><Text style={styles.label}>{event.time || `Event ${index + 1}`} · {event.kind || 'EVENT'}</Text><Text style={[styles.body, { marginTop: 5 }]}>{event.label || event.detail || event.event_id || 'Observed event'}</Text><Text style={[styles.muted, { marginTop: 4 }]}>{event.detail || event.source || event.provenance || ''}</Text></Card>) : <Text style={styles.muted}>No events were returned.</Text>}</Card>
        <Card><Text style={styles.sectionTitle}>Counterexample</Text><Text style={styles.body}>{data.counterexample?.length ? `${data.counterexample.length} events preserve the first observed violation.` : 'No counterexample was returned.'}</Text></Card>
        <Card><Text style={styles.sectionTitle}>Verification results</Text>{verification?.violations?.length ? verification.violations.map((violation, index) => <Text key={String(violation.code || violation.event_id || index)} style={[styles.body, { color: colors.danger, marginBottom: 8 }]}>• {violation.message || violation.code || violation.event_id || 'Invariant violation'}</Text>) : <Text style={styles.body}>No violations returned.</Text>}{verification?.first_violation_event_id ? <Text style={[styles.muted, { marginTop: 4 }]}>First violation: {verification.first_violation_event_id}</Text> : null}</Card>
      </> : null}
    </ScrollView>
  </Screen>;
}
