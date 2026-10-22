import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useSession } from '../session';
import { ApiError } from '../api';
import { Button, Card, colors, styles } from '../ui';

export function SignInScreen() {
  const { signIn } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit() {
    setError('');
    setLoading(true);
    try { await signIn(email.trim(), password); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Sign-in failed. Please try again.'); }
    finally { setLoading(false); }
  }

  return <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={['bottom', 'left', 'right']}><KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.signInContent}>
      <View style={styles.brandBlock}><Text style={styles.brand}>Veylith</Text><Text style={styles.brandSubtitle}>Temporal safety assurance for autonomous agents.</Text></View>
      <Card><Text style={styles.sectionTitle}>Sign in</Text><Text style={styles.label}>Email</Text><TextInput accessibilityLabel="Email" autoCapitalize="none" autoComplete="email" keyboardType="email-address" returnKeyType="next" value={email} onChangeText={setEmail} style={[styles.input, { marginTop: 6 }]} placeholder="you@example.com" placeholderTextColor={colors.muted} /><Text style={[styles.label, { marginTop: 16 }]}>Password</Text><TextInput accessibilityLabel="Password" autoComplete="password" secureTextEntry returnKeyType="go" onSubmitEditing={submit} value={password} onChangeText={setPassword} style={[styles.input, { marginTop: 6 }]} placeholder="Your password" placeholderTextColor={colors.muted} />{error ? <Text accessibilityLiveRegion="assertive" style={styles.formError}>{error}</Text> : null}<Button label={loading ? 'Signing in…' : 'Sign in'} onPress={submit} disabled={loading || !email.trim() || !password} /></Card>
      <Text style={styles.signInNote}>API session only · credentials are never bundled with the app</Text>
    </ScrollView>
  </KeyboardAvoidingView></SafeAreaView>;
}
