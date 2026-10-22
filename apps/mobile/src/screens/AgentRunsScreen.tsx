import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, Pressable, Text } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RootStackParamList } from '../../App';
import { api, ApiError } from '../api';
import type { AgentRun } from '../types';
import { Card, Pill, Screen, StateView, styles } from '../ui';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function AgentRunsScreen() {
  const navigation = useNavigation<Nav>();
  const [items, setItems] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try { setItems(await api.agentRuns()); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Unable to load agent runs.'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  return <Screen title="Agent runs" subtitle="Recent verification workflows">
    <StateView loading={loading && !items.length} error={!items.length && error ? error : undefined} empty={!loading && !error && !items.length ? 'No agent runs have been recorded.' : undefined} onRetry={load} />
    <FlatList data={items} keyExtractor={(item, index) => String(item.id || item.run_id || index)} contentContainerStyle={styles.listContent} onRefresh={load} refreshing={loading} renderItem={({ item }) => {
      const outcome = String(item.outcome || item.status || 'UNKNOWN');
      const rejected = outcome.toLowerCase().includes('reject') || outcome.toLowerCase().includes('fail');
      return <Pressable accessibilityRole="button" accessibilityLabel={`Open ${item.name || item.scenario_id || 'agent run'}`} onPress={() => navigation.navigate('Incident', { runId: item.id || item.run_id, scenarioId: item.scenario_id })} style={({ pressed }) => pressed && styles.pressed}>
        <Card><Text style={styles.sectionTitle}>{item.name || item.scenario_id || item.run_id || 'Agent run'}</Text><Text style={styles.body}>{item.summary || 'Open run details for events and verification.'}</Text><Text style={[styles.muted, { marginTop: 8 }]}>{item.started_at || 'Time unavailable'}</Text><Pill label={outcome} tone={rejected ? 'danger' : 'success'} /></Card>
      </Pressable>;
    }} />
  </Screen>;
}
