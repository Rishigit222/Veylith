import React from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export const colors = {
  white: '#FFFFFF',
  background: '#F8FAFC',
  surface: '#FFFFFF',
  surfaceMuted: '#F1F5F9',
  ink: '#0F172A',
  body: '#475569',
  muted: '#64748B',
  primary: '#2563EB',
  primaryStrong: '#1D4ED8',
  primarySoft: '#EFF6FF',
  success: '#059669',
  successStrong: '#047857',
  successSoft: '#ECFDF5',
  line: '#E2E8F0',
  lineStrong: '#CBD5E1',
  danger: '#DC2626',
  dangerSoft: '#FEF2F2',
  warning: '#D97706',
  warningSoft: '#FFFBEB',
};

export function Screen({ children, title, subtitle, right }: React.PropsWithChildren<{ title: string; subtitle?: string; right?: React.ReactNode }>) {
  return <SafeAreaView style={styles.screen} edges={['bottom', 'left', 'right']}><View style={styles.header}><View style={styles.headerCopy}><Text style={styles.title}>{title}</Text>{subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}</View>{right}</View>{children}</SafeAreaView>;
}

export function Card({ children, style }: React.PropsWithChildren<{ style?: object }>) { return <View style={[styles.card, style]}>{children}</View>; }

export function Button({ label, onPress, kind = 'primary', disabled = false }: { label: string; onPress: () => void; kind?: 'primary' | 'secondary' | 'danger'; disabled?: boolean }) {
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress} style={({ pressed }) => [styles.button, kind === 'secondary' && styles.secondaryButton, kind === 'danger' && styles.dangerButton, pressed && styles.pressed, disabled && styles.disabled]}><Text style={[styles.buttonText, kind === 'secondary' && styles.secondaryButtonText]}>{label}</Text></Pressable>;
}

export function LinkButton({ label, onPress }: { label: string; onPress: () => void }) {
  return <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [styles.linkButton, pressed && styles.pressed]}><Text style={styles.linkText}>{label}</Text></Pressable>;
}

export function StateView({ loading, error, empty, onRetry }: { loading?: boolean; error?: string; empty?: string; onRetry?: () => void }) {
  if (loading) return <View style={styles.state} accessibilityLiveRegion="polite"><ActivityIndicator color={colors.primary} size="small" /><Text style={styles.muted}>Loading…</Text></View>;
  if (error) return <View style={styles.state} accessibilityLiveRegion="assertive"><Text style={styles.error}>{error}</Text>{onRetry ? <Button label="Retry" onPress={onRetry} kind="secondary" /> : null}</View>;
  if (empty) return <View style={styles.state}><Text style={styles.emptyTitle}>Nothing here yet</Text><Text style={styles.muted}>{empty}</Text></View>;
  return null;
}

export function Pill({ label, tone = 'neutral' }: { label: string; tone?: 'neutral' | 'success' | 'danger' | 'warning' }) {
  return <Text style={[styles.pill, tone === 'success' && styles.successPill, tone === 'danger' && styles.dangerPill, tone === 'warning' && styles.warningPill]}>{label}</Text>;
}

export const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background, paddingHorizontal: 20 },
  header: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 18, paddingTop: 18 },
  headerCopy: { flex: 1, paddingRight: 12 },
  title: { color: colors.ink, fontSize: 29, fontWeight: '800', letterSpacing: -0.5 },
  subtitle: { color: colors.muted, fontSize: 14, lineHeight: 20, marginTop: 5 },
  card: { backgroundColor: colors.surface, borderColor: colors.line, borderRadius: 16, borderWidth: 1, marginBottom: 12, padding: 16 },
  sectionTitle: { color: colors.ink, fontSize: 17, fontWeight: '800', marginBottom: 10 },
  label: { color: colors.muted, fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase' },
  value: { color: colors.ink, fontSize: 25, fontWeight: '800', marginTop: 5 },
  body: { color: colors.body, fontSize: 15, lineHeight: 22 },
  muted: { color: colors.muted, fontSize: 14, lineHeight: 20 },
  error: { color: colors.danger, fontSize: 14, lineHeight: 20, marginBottom: 4, textAlign: 'center' },
  emptyTitle: { color: colors.ink, fontSize: 16, fontWeight: '800', marginBottom: 4 },
  state: { alignItems: 'center', justifyContent: 'center', minHeight: 150, padding: 28 },
  button: { alignItems: 'center', backgroundColor: colors.primary, borderRadius: 10, justifyContent: 'center', marginTop: 12, minHeight: 48, paddingHorizontal: 17 },
  secondaryButton: { backgroundColor: colors.primarySoft, borderColor: '#BFDBFE', borderWidth: 1 },
  dangerButton: { backgroundColor: colors.danger },
  disabled: { opacity: 0.5 },
  pressed: { opacity: 0.78 },
  buttonText: { color: colors.white, fontSize: 15, fontWeight: '800' },
  secondaryButtonText: { color: colors.primaryStrong },
  linkButton: { alignItems: 'flex-start', borderRadius: 8, justifyContent: 'center', minHeight: 44, paddingVertical: 6 },
  linkText: { color: colors.primaryStrong, fontSize: 15, fontWeight: '800' },
  row: { alignItems: 'center', flexDirection: 'row', gap: 12, justifyContent: 'space-between' },
  pill: { alignSelf: 'flex-start', backgroundColor: colors.surfaceMuted, borderRadius: 99, color: colors.body, fontSize: 11, fontWeight: '800', overflow: 'hidden', paddingHorizontal: 10, paddingVertical: 5 },
  successPill: { backgroundColor: colors.successSoft, color: colors.successStrong },
  dangerPill: { backgroundColor: colors.dangerSoft, color: colors.danger },
  warningPill: { backgroundColor: colors.warningSoft, color: colors.warning },
  input: { backgroundColor: colors.white, borderColor: colors.lineStrong, borderRadius: 10, borderWidth: 1, color: colors.ink, fontSize: 16, minHeight: 50, paddingHorizontal: 14, paddingVertical: 12 },
  signInContent: { flexGrow: 1, justifyContent: 'center', padding: 24 },
  brandBlock: { marginBottom: 24 },
  brand: { color: colors.ink, fontSize: 36, fontWeight: '900', letterSpacing: -1 },
  brandSubtitle: { color: colors.muted, fontSize: 15, lineHeight: 22, marginTop: 8 },
  formError: { color: colors.danger, fontSize: 14, lineHeight: 20, marginTop: 12 },
  signInNote: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 14, textAlign: 'center' },
  boot: { alignItems: 'center', backgroundColor: colors.background, flex: 1, justifyContent: 'center', padding: 24 },
  bootBrand: { color: colors.ink, fontSize: 30, fontWeight: '900', marginBottom: 24 },
  scrollContent: { paddingBottom: 28 },
  listContent: { paddingBottom: 28 },
  metricGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 4 },
  metricCard: { flexBasis: '47%', flexGrow: 1, minWidth: 135 },
  sectionHeading: { color: colors.ink, fontSize: 18, fontWeight: '800', marginBottom: 10, marginTop: 6 },
  actionGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  actionCard: { flexBasis: '47%', flexGrow: 1, minWidth: 145, marginBottom: 0 },
  decisionRow: { flexDirection: 'row', gap: 10, marginTop: 4 },
  decisionButton: { flex: 1 },
  timelineCard: { backgroundColor: colors.surfaceMuted, borderColor: colors.line, borderRadius: 12, marginBottom: 8, padding: 12 },
  divider: { borderBottomColor: colors.line, borderBottomWidth: 1 },
});
