/**
 * Home Screen
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  useColorScheme,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

interface StatCard {
  label: string;
  value: string;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
}

interface QuickAction {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
}

const stats: StatCard[] = [
  { label: 'Active Tasks', value: '3', icon: 'git-branch', color: '#06b6d4' },
  { label: 'Completed Today', value: '12', icon: 'checkmark-circle', color: '#10b981' },
  { label: 'Pending Review', value: '2', icon: 'eye', color: '#f59e0b' },
  { label: 'Failed', value: '0', icon: 'close-circle', color: '#ef4444' },
];

const quickActions: QuickAction[] = [
  { label: 'New Refactor', icon: 'code-slash', color: '#8b5cf6' },
  { label: 'Add API', icon: 'add-circle', color: '#06b6d4' },
  { label: 'Fix Bug', icon: 'bug', color: '#ef4444' },
  { label: 'Voice Task', icon: 'mic', color: '#10b981' },
];

const recentTasks = [
  { id: '1', title: 'Rename email to primaryEmail', status: 'completed', time: '2 min ago', tenant: 'Acme Corp' },
  { id: '2', title: 'Add auth middleware', status: 'running', time: '5 min ago', tenant: 'TechStart' },
  { id: '3', title: 'Refactor payment module', status: 'review', time: '15 min ago', tenant: 'FinanceX' },
];

export function HomeScreen() {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === 'dark';

  const styles = createStyles(isDark);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>Good morning 👋</Text>
            <Text style={styles.userName}>John Doe</Text>
          </View>
          <TouchableOpacity style={styles.notificationBtn}>
            <Ionicons name="notifications-outline" size={24} color={isDark ? '#fff' : '#0f172a'} />
            <View style={styles.notificationBadge} />
          </TouchableOpacity>
        </View>

        {/* Stats Grid */}
        <View style={styles.statsGrid}>
          {stats.map((stat, i) => (
            <View key={i} style={styles.statCard}>
              <View style={[styles.statIcon, { backgroundColor: stat.color + '20' }]}>
                <Ionicons name={stat.icon} size={20} color={stat.color} />
              </View>
              <Text style={styles.statValue}>{stat.value}</Text>
              <Text style={styles.statLabel}>{stat.label}</Text>
            </View>
          ))}
        </View>

        {/* Quick Actions */}
        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <View style={styles.actionsGrid}>
          {quickActions.map((action, i) => (
            <TouchableOpacity key={i} style={styles.actionCard}>
              <View style={[styles.actionIcon, { backgroundColor: action.color + '20' }]}>
                <Ionicons name={action.icon} size={24} color={action.color} />
              </View>
              <Text style={styles.actionLabel}>{action.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Recent Tasks */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Recent Tasks</Text>
          <TouchableOpacity>
            <Text style={styles.seeAll}>See All</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.tasksList}>
          {recentTasks.map((task) => (
            <TouchableOpacity key={task.id} style={styles.taskCard}>
              <View style={styles.taskStatus}>
                <View style={[
                  styles.statusDot,
                  { backgroundColor: 
                    task.status === 'completed' ? '#10b981' :
                    task.status === 'running' ? '#06b6d4' : '#f59e0b'
                  }
                ]} />
              </View>
              <View style={styles.taskInfo}>
                <Text style={styles.taskTitle}>{task.title}</Text>
                <Text style={styles.taskMeta}>{task.tenant} • {task.time}</Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color="#64748b" />
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const createStyles = (isDark: boolean) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: isDark ? '#0a0a0f' : '#f8fafc',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  greeting: {
    fontSize: 14,
    color: '#64748b',
  },
  userName: {
    fontSize: 24,
    fontWeight: 'bold',
    color: isDark ? '#fff' : '#0f172a',
  },
  notificationBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: isDark ? '#1e1e2e' : '#e2e8f0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  notificationBadge: {
    position: 'absolute',
    top: 10,
    right: 10,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#ef4444',
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 12,
    gap: 8,
  },
  statCard: {
    width: '48%',
    backgroundColor: isDark ? '#12121a' : '#fff',
    borderRadius: 16,
    padding: 16,
    marginBottom: 8,
  },
  statIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  statValue: {
    fontSize: 28,
    fontWeight: 'bold',
    color: isDark ? '#fff' : '#0f172a',
  },
  statLabel: {
    fontSize: 13,
    color: '#64748b',
    marginTop: 4,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: isDark ? '#fff' : '#0f172a',
    paddingHorizontal: 20,
    marginTop: 24,
    marginBottom: 12,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingRight: 20,
  },
  seeAll: {
    fontSize: 14,
    color: '#06b6d4',
  },
  actionsGrid: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    gap: 8,
  },
  actionCard: {
    flex: 1,
    backgroundColor: isDark ? '#12121a' : '#fff',
    borderRadius: 16,
    padding: 16,
    alignItems: 'center',
  },
  actionIcon: {
    width: 48,
    height: 48,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  actionLabel: {
    fontSize: 12,
    color: isDark ? '#fff' : '#0f172a',
    textAlign: 'center',
  },
  tasksList: {
    paddingHorizontal: 20,
    gap: 8,
  },
  taskCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: isDark ? '#12121a' : '#fff',
    borderRadius: 12,
    padding: 16,
  },
  taskStatus: {
    marginRight: 12,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  taskInfo: {
    flex: 1,
  },
  taskTitle: {
    fontSize: 15,
    fontWeight: '500',
    color: isDark ? '#fff' : '#0f172a',
  },
  taskMeta: {
    fontSize: 13,
    color: '#64748b',
    marginTop: 4,
  },
});

