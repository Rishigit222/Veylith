import React from 'react';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { SessionProvider, useSession } from './src/session';
import { SignInScreen } from './src/screens/SignInScreen';
import { OverviewScreen } from './src/screens/OverviewScreen';
import { AgentRunsScreen } from './src/screens/AgentRunsScreen';
import { IncidentScreen } from './src/screens/IncidentScreen';
import { RepairScreen } from './src/screens/RepairScreen';
import { NotificationsScreen } from './src/screens/NotificationsScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import { ScenarioScreen } from './src/screens/ScenarioScreen';
import { BootScreen } from './src/screens/BootScreen';

export type RootStackParamList = { SignIn: undefined; Overview: undefined; AgentRuns: undefined; Incident: { runId?: string; scenarioId?: string }; Repair: undefined; Notifications: undefined; Settings: undefined; Scenario: { scenarioId: string } };
const Stack = createNativeStackNavigator<RootStackParamList>();
const theme = { ...DefaultTheme, colors: { ...DefaultTheme.colors, background: '#F3F6FA', primary: '#176B87' } };

function Routes() {
  const { user, booting } = useSession();
  if (booting) return <BootScreen />;
  return <NavigationContainer theme={theme}><Stack.Navigator screenOptions={{ headerShown: true, headerBackTitle: 'Back', headerTintColor: '#176B87', headerTitleStyle: { color: '#10213B' } }}>{user ? <><Stack.Screen name="Overview" component={OverviewScreen} options={{ title: 'Veylith' }} /><Stack.Screen name="AgentRuns" component={AgentRunsScreen} /><Stack.Screen name="Incident" component={IncidentScreen} /><Stack.Screen name="Repair" component={RepairScreen} /><Stack.Screen name="Notifications" component={NotificationsScreen} /><Stack.Screen name="Settings" component={SettingsScreen} /><Stack.Screen name="Scenario" component={ScenarioScreen} /></> : <Stack.Screen name="SignIn" component={SignInScreen} options={{ title: 'Sign in' }} />}</Stack.Navigator></NavigationContainer>;
}

export default function App() { return <SafeAreaProvider><StatusBar style="dark" /><SessionProvider><Routes /></SessionProvider></SafeAreaProvider>; }
