import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, Text, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { api, ApiError } from '../api';
import type { Overview } from '../types';
import type { RootStackParamList } from '../../App';
import { Button, Card, Pill, Screen, StateView, styles } from '../ui';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function OverviewScreen() {
  const navigation = useNavigation<Nav>();
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setData(await api.overview()); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Unable to load overview.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const metrics = data?.metrics || {};
  const scenario = data?.scenario as { id?: string; name?: string } | undefined;
  return <Screen title="Overview" subtitle="Operational safety posture"><ScrollView refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}>
    <StateView loading={loading && !data} error={!data && error ? error : undefined} onRetry={load} />
    {data ? <>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>{[['Runs', metrics.workflow_runs], ['Violations', metrics.invariant_violations], ['Rejected', metrics.rejected_unsafe_transitions], ['Legitimate', metrics.successful_legitimate_workflows]].map(([label, value]) => <Card key={String(label)} style={{ width: '47%' }}><Text style={styles.label}>{label}</Text><Text style={styles.value}>{String(value ?? '—')}</Text></Card>)}</View>
      <Card><View style={styles.row}><Text style={styles.sectionTitle}>Critical alerts</Text><Pill label={Number(metrics.invariant_violations || 0) > 0 ? 'Review required' : 'Nominal'} tone={Number(metrics.invariant_violations || 0) > 0 ? 'danger' : 'success'} /></View><Text style={styles.body}>{scenario?.name || 'Veylith is monitoring temporal authorization workflows.'}</Text><Text style={styles.muted}>{String((data.integration as { mode?: string } | undefined)?.mode || 'Connected API')}</Text><Button label="Open flagship incident" onPress={() => navigation.navigate('Incident', { scenarioId: scenario?.id || 'SCN-042' })} kind="secondary" /><View style={styles.row}><Card style={{ flex: 1, marginTop: 14 }}><Text style={styles.label}>Explore</Text><Text onPress={() => navigation.navigate('AgentRuns')} style={{ color: '#176B87', fontWeight: '800', marginTop: 6 }}>Agent runs →</Text></Card><Card style={{ flex: 1, marginTop: 14 }}><Text style={styles.label}>Review</Text><Text onPress={() => navigation.navigate('Repair')} style={{ color: '#176B87', fontWeight: '800', marginTop: 6 }}>Repairs →</Text></Card></View><View style={styles.row}><Card style={{ flex: 1 }}><Text onPress={() => navigation.navigate('Notifications')} style={{ color: '#176B87', fontWeight: '800' }}>Notifications →</Text></Card><Card style={{ flex: 1 }}><Text onPress={() => navigation.navigate('Settings')} style={{ color: '#176B87', fontWeight: '800' }}>Settings →</Text></Card></View></Card>
    </> : null}
  </ScrollView></Screen>;
}
