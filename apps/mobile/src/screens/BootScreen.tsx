import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { colors } from '../ui';
export function BootScreen() { return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F3F6FA' }}><ActivityIndicator color={colors.primary} /></View>; }
