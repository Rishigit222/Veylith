import React, { useCallback, useEffect, useState } from 'react';
import { RefreshControl, ScrollView, Text, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { api, ApiError } from '../api';
import type { Overview } from '../types';
import type { RootStackParamList } from '../../App';
import { Button, Card, LinkButton, Pill, Screen, StateView, colors, styles } from '../ui';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function OverviewScreen() {
  const navigation = useNavigation<Nav>();
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try { setData(await api.overview()); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Unable to load overview.'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const metrics = data?.metrics || {};
  const scenario = data?.scenario as { id?: string; name?: string } | undefined;
  const hasViolations = Number(metrics.invariant_violations || 0) > 0;
  const tiles = [
    ['Runs', metrics.workflow_runs],
    ['Violations', metrics.invariant_violations],
    ['Rejected', metrics.rejected_unsafe_transitions],
    ['Legitimate', metrics.successful_legitimate_workflows],
  ];

  return <Screen title="Overview" subtitle="Operational safety posture">
    <ScrollView contentContainerStyle={styles.scrollContent} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.primary} colors={[colors.primary]} />}>
      <StateView loading={loading && !data} error={!data && error ? error : undefined} onRetry={load} />
      {data ? <>
        <View style={styles.metricGrid}>{tiles.map(([label, value]) => <Card key={String(label)} style={styles.metricCard}><Text style={styles.label}>{label}</Text><Text style={styles.value}>{String(value ?? '—')}</Text></Card>)}</View>
        <Card>
          <View style={styles.row}><Text style={styles.sectionTitle}>Critical alerts</Text><Pill label={hasViolations ? 'Review required' : 'Nominal'} tone={hasViolations ? 'danger' : 'success'} /></View>
          <Text style={styles.body}>{scenario?.name || 'Veylith is monitoring temporal authorization workflows.'}</Text>
          <Text style={[styles.muted, { marginTop: 6 }]}>{String((data.integration as { mode?: string } | undefined)?.mode || 'Connected API')}</Text>
          <Button label="Open flagship incident" onPress={() => navigation.navigate('Incident', { scenarioId: scenario?.id || 'SCN-042' })} kind="secondary" />
        </Card>
        <Text style={styles.sectionHeading}>Workspace</Text>
        <View style={styles.actionGrid}>
          <Card style={styles.actionCard}><Text style={styles.label}>Explore</Text><LinkButton label="Agent runs →" onPress={() => navigation.navigate('AgentRuns')} /></Card>
          <Card style={styles.actionCard}><Text style={styles.label}>Review</Text><LinkButton label="Repairs →" onPress={() => navigation.navigate('Repair')} /></Card>
          <Card style={styles.actionCard}><Text style={styles.label}>Stay informed</Text><LinkButton label="Notifications →" onPress={() => navigation.navigate('Notifications')} /></Card>
          <Card style={styles.actionCard}><Text style={styles.label}>Account</Text><LinkButton label="Settings →" onPress={() => navigation.navigate('Settings')} /></Card>
        </View>
      </> : null}
    </ScrollView>
  </Screen>;
}
