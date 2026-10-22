import type { ExpoConfig } from 'expo/config';

const configuredApiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || process.env.API_BASE_URL;
const isProductionBuild = process.env.EAS_BUILD_PROFILE === 'production' || process.env.NODE_ENV === 'production';
if (isProductionBuild && !configuredApiBaseUrl) {
  throw new Error('EXPO_PUBLIC_API_BASE_URL must be set to the public HTTPS Veylith API before a production Expo build.');
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
