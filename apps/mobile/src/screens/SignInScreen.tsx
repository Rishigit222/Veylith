import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, Text, TextInput, View } from 'react-native';
import { useSession } from '../session';
import { ApiError } from '../api';
import { Button, Card, colors, styles } from '../ui';

export function SignInScreen() {
  const { signIn } = useSession();
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  async function submit() { setError(''); setLoading(true); try { await signIn(email.trim(), password); } catch (e) { setError(e instanceof ApiError ? e.message : 'Sign-in failed. Please try again.'); } finally { setLoading(false); } }
  return <KeyboardAvoidingView style={{ flex: 1, backgroundColor: colors.background }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: 'center', padding: 24 }}><Text style={{ fontSize: 34, fontWeight: '900', color: colors.ink }}>Veylith</Text><Text style={{ color: colors.muted, marginTop: 8, marginBottom: 22 }}>Temporal safety assurance for autonomous agents.</Text><Card><Text style={styles.sectionTitle}>Sign in</Text><Text style={styles.label}>Email</Text><TextInput autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} style={styles.input} placeholder="you@example.com" /><Text style={[styles.label, { marginTop: 14 }]}>Password</Text><TextInput secureTextEntry value={password} onChangeText={setPassword} style={styles.input} placeholder="Your password" />{error ? <Text style={{ color: colors.danger, marginTop: 12 }}>{error}</Text> : null}<Button label={loading ? 'Signing in…' : 'Sign in'} onPress={submit} disabled={loading || !email || !password} /></Card><Text style={{ color: colors.muted, fontSize: 12, textAlign: 'center' }}>API session only · credentials are never bundled with the app</Text></ScrollView></KeyboardAvoidingView>;
}
