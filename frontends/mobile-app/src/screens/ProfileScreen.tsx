/**
 * Profile Screen
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  useColorScheme,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

interface MenuItem {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value?: string;
  hasToggle?: boolean;
  toggleValue?: boolean;
  danger?: boolean;
}

const accountMenuItems: MenuItem[] = [
  { icon: 'business-outline', label: 'Organization', value: 'Acme Corp' },
  { icon: 'mail-outline', label: 'Email', value: 'john@acme.com' },
  { icon: 'key-outline', label: 'API Key', value: '••••••••X7mK' },
  { icon: 'server-outline', label: 'Server URL', value: 'api.code4u.ai' },
];

const preferencesItems: MenuItem[] = [
  { icon: 'notifications-outline', label: 'Push Notifications', hasToggle: true, toggleValue: true },
  { icon: 'moon-outline', label: 'Dark Mode', hasToggle: true, toggleValue: true },
  { icon: 'flash-outline', label: 'Auto-approve Safe Changes', hasToggle: true, toggleValue: false },
  { icon: 'volume-high-outline', label: 'Sound Effects', hasToggle: true, toggleValue: true },
];

const supportItems: MenuItem[] = [
  { icon: 'help-circle-outline', label: 'Help Center' },
  { icon: 'document-text-outline', label: 'Documentation' },
  { icon: 'chatbubble-outline', label: 'Contact Support' },
  { icon: 'star-outline', label: 'Rate the App' },
];

const stats = [
  { label: 'Tasks Run', value: '1,234' },
  { label: 'Success Rate', value: '98.7%' },
  { label: 'Files Changed', value: '8,456' },
];

export function ProfileScreen() {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === 'dark';

  const styles = createStyles(isDark);

  const renderMenuItem = (item: MenuItem, index: number, isLast: boolean) => (
    <TouchableOpacity key={index} style={[styles.menuItem, isLast && styles.menuItemLast]}>
      <View style={styles.menuItemLeft}>
        <Ionicons name={item.icon} size={22} color={item.danger ? '#ef4444' : '#64748b'} />
        <Text style={[styles.menuItemLabel, item.danger && styles.dangerText]}>{item.label}</Text>
      </View>
      {item.value && <Text style={styles.menuItemValue}>{item.value}</Text>}
      {item.hasToggle && (
        <Switch
          value={item.toggleValue}
          trackColor={{ false: '#64748b', true: '#06b6d4' }}
          thumbColor="#fff"
        />
      )}
      {!item.value && !item.hasToggle && (
        <Ionicons name="chevron-forward" size={20} color="#64748b" />
      )}
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Profile Header */}
        <View style={styles.profileHeader}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>JD</Text>
          </View>
          <Text style={styles.userName}>John Doe</Text>
          <Text style={styles.userRole}>Senior Engineer • Acme Corp</Text>
          <TouchableOpacity style={styles.editBtn}>
            <Text style={styles.editBtnText}>Edit Profile</Text>
          </TouchableOpacity>
        </View>

        {/* Stats */}
        <View style={styles.statsContainer}>
          {stats.map((stat, i) => (
            <View key={i} style={styles.statItem}>
              <Text style={styles.statValue}>{stat.value}</Text>
              <Text style={styles.statLabel}>{stat.label}</Text>
            </View>
          ))}
        </View>

        {/* Account Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Account</Text>
          <View style={styles.menuContainer}>
            {accountMenuItems.map((item, i) => renderMenuItem(item, i, i === accountMenuItems.length - 1))}
          </View>
        </View>

        {/* Preferences Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Preferences</Text>
          <View style={styles.menuContainer}>
            {preferencesItems.map((item, i) => renderMenuItem(item, i, i === preferencesItems.length - 1))}
          </View>
        </View>

        {/* Support Section */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Support</Text>
          <View style={styles.menuContainer}>
            {supportItems.map((item, i) => renderMenuItem(item, i, i === supportItems.length - 1))}
          </View>
        </View>

        {/* Logout */}
        <TouchableOpacity style={styles.logoutBtn}>
          <Ionicons name="log-out-outline" size={22} color="#ef4444" />
          <Text style={styles.logoutText}>Log Out</Text>
        </TouchableOpacity>

        {/* Version */}
        <Text style={styles.version}>code4u.ai Mobile v1.0.0</Text>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const createStyles = (isDark: boolean) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: isDark ? '#0a0a0f' : '#f8fafc',
  },
  profileHeader: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#06b6d4',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  avatarText: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  userName: {
    fontSize: 22,
    fontWeight: 'bold',
    color: isDark ? '#fff' : '#0f172a',
    marginBottom: 4,
  },
  userRole: {
    fontSize: 14,
    color: '#64748b',
    marginBottom: 16,
  },
  editBtn: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#06b6d4',
  },
  editBtnText: {
    color: '#06b6d4',
    fontSize: 14,
    fontWeight: '600',
  },
  statsContainer: {
    flexDirection: 'row',
    backgroundColor: isDark ? '#12121a' : '#fff',
    marginHorizontal: 20,
    borderRadius: 16,
    padding: 20,
    marginBottom: 24,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 20,
    fontWeight: 'bold',
    color: isDark ? '#fff' : '#0f172a',
  },
  statLabel: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 4,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#64748b',
    paddingHorizontal: 20,
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  menuContainer: {
    backgroundColor: isDark ? '#12121a' : '#fff',
    marginHorizontal: 20,
    borderRadius: 16,
    overflow: 'hidden',
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: isDark ? '#1e1e2e' : '#f1f5f9',
  },
  menuItemLast: {
    borderBottomWidth: 0,
  },
  menuItemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  menuItemLabel: {
    fontSize: 15,
    color: isDark ? '#fff' : '#0f172a',
  },
  menuItemValue: {
    fontSize: 14,
    color: '#64748b',
  },
  dangerText: {
    color: '#ef4444',
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#ef444420',
    marginHorizontal: 20,
    paddingVertical: 14,
    borderRadius: 14,
    gap: 8,
  },
  logoutText: {
    color: '#ef4444',
    fontSize: 16,
    fontWeight: '600',
  },
  version: {
    textAlign: 'center',
    color: '#64748b',
    fontSize: 12,
    marginTop: 24,
  },
});

