import type { ExpoConfig } from 'expo/config';

const configuredApiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || process.env.API_BASE_URL;
const isEasBuild = Boolean(process.env.EAS_BUILD_PROFILE);
if (isEasBuild && !configuredApiBaseUrl) {
  throw new Error('EXPO_PUBLIC_API_BASE_URL must be set before an EAS Expo build. Localhost is not a distributable API origin.');
}
if (isEasBuild && configuredApiBaseUrl) {
  let parsedUrl: URL;
  try {
    parsedUrl = new URL(configuredApiBaseUrl);
  } catch {
    throw new Error('EXPO_PUBLIC_API_BASE_URL must be a valid absolute HTTPS URL for an EAS Expo build.');
  }
  const blockedHosts = new Set(['localhost', '127.0.0.1', '0.0.0.0', '::1']);
  if (parsedUrl.protocol !== 'https:' || blockedHosts.has(parsedUrl.hostname)) {
    throw new Error('EXPO_PUBLIC_API_BASE_URL must use public HTTPS; localhost and loopback origins are rejected for EAS builds.');
  }
}
const apiBaseUrl = configuredApiBaseUrl || 'http://127.0.0.1:8000';

const config: ExpoConfig = {
  name: 'Veylith',
  slug: 'veylith-mobile',
  version: '0.1.0',
  orientation: 'portrait',
  scheme: 'veylith',
  userInterfaceStyle: 'light',
  android: { package: 'com.veylith.mobile' },
  extra: {
    apiBaseUrl,
    pushStatus: process.env.EXPO_PUBLIC_PUSH_ENABLED === 'true' ? 'configured' : 'disabled',
  },
};

export default config;
