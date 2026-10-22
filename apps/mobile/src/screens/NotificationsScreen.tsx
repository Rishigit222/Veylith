import React, { useCallback, useEffect, useState } from 'react';
import { FlatList, Text } from 'react-native';
import { api, ApiError } from '../api';
import type { Notification } from '../types';
import { Card, Pill, Screen, StateView, styles } from '../ui';

export function NotificationsScreen() {
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try { setItems(await api.notifications()); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Unable to load notifications.'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  return <Screen title="Notifications" subtitle="Local notification center">
    <StateView loading={loading && !items.length} error={!items.length && error ? error : undefined} empty={!loading && !error && !items.length ? 'No notifications.' : undefined} onRetry={load} />
    <FlatList data={items} keyExtractor={(item, index) => String(item.id || index)} contentContainerStyle={styles.listContent} onRefresh={load} refreshing={loading} renderItem={({ item }) => {
      const severity = String(item.severity || 'INFO');
      const critical = severity.toLowerCase().includes('critical') || severity.toLowerCase().includes('error');
      return <Card><Text style={styles.sectionTitle}>{item.title || 'Veylith alert'}</Text><Pill label={severity} tone={critical ? 'danger' : 'neutral'} /><Text style={[styles.body, { marginTop: 10 }]}>{item.message || 'No additional details.'}</Text><Text style={[styles.muted, { marginTop: 8 }]}>{item.created_at || ''}</Text></Card>;
    }} />
  </Screen>;
}
