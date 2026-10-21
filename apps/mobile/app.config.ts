import type { ExpoConfig } from 'expo/config';

const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || process.env.API_BASE_URL || 'http://127.0.0.1:8000';

const config: ExpoConfig = {
  name: 'Veylith',
  slug: 'veylith-mobile',
  version: '0.1.0',
  orientation: 'portrait',
  scheme: 'veylith',
  userInterfaceStyle: 'light',
  extra: {
    apiBaseUrl,
    pushStatus: process.env.EXPO_PUBLIC_PUSH_ENABLED === 'true' ? 'configured' : 'disabled',
  },
};

export default config;
