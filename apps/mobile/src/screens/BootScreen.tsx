import React from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { colors, styles } from '../ui';

export function BootScreen() {
  return <View style={styles.boot}><Text style={styles.bootBrand}>Veylith</Text><ActivityIndicator color={colors.primary} size="small" /><Text style={styles.muted}>Restoring your session…</Text></View>;
}
