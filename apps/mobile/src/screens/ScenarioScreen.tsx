import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, Text } from 'react-native';
import { useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { RootStackParamList } from '../../App';
import { api, ApiError } from '../api';
import type { ScenarioRun } from '../types';
import { Card, Pill, Screen, StateView, styles } from '../ui';

export function ScenarioScreen() {
  const route = useRoute<RouteProp<RootStackParamList, 'Scenario'>>();
  const [data, setData] = useState<ScenarioRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try { setData(await api.runScenario(route.params.scenarioId)); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Unable to run scenario.'); }
    finally { setLoading(false); }
  }, [route.params.scenarioId]);

  useEffect(() => { load(); }, [load]);

  return <Screen title="Scenario timeline" subtitle={route.params.scenarioId}>
    <StateView loading={loading && !data} error={!data && error ? error : undefined} onRetry={load} />
    {data ? <>
      <Card><Text style={styles.sectionTitle}>Verification</Text><Pill label={data.verification?.valid ? 'VALID' : 'VIOLATION'} tone={data.verification?.valid ? 'success' : 'danger'} /><Text style={[styles.body, { marginTop: 10 }]}>{data.verification?.violations?.map((v) => v.message || v.code || 'Violation').join('\n') || 'No violations returned.'}</Text></Card>
      <FlatList data={data.events || []} keyExtractor={(event, index) => String(event.id || event.event_id || index)} contentContainerStyle={styles.listContent} renderItem={({ item, index }) => <Card><Text style={styles.label}>{item.time || `Step ${index + 1}`} · {item.kind || 'EVENT'}</Text><Text style={[styles.sectionTitle, { marginTop: 6 }]}>{item.label || 'Observed event'}</Text><Text style={styles.body}>{item.detail || ''}</Text></Card>} />
    </> : null}
  </Screen>;
}
