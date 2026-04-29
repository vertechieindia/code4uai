/**
 * Notifications Screen
 */
import React, { useState } from 'react';
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

interface Notification {
  id: string;
  type: 'task_complete' | 'approval_needed' | 'error' | 'info' | 'mention';
  title: string;
  message: string;
  time: string;
  read: boolean;
}

const mockNotifications: Notification[] = [
  { id: '1', type: 'task_complete', title: 'Task Completed', message: 'Rename email to primaryEmail finished successfully', time: '2 min ago', read: false },
  { id: '2', type: 'approval_needed', title: 'Review Required', message: 'Refactor payment module ready for review (12 files)', time: '15 min ago', read: false },
  { id: '3', type: 'error', title: 'Task Failed', message: 'Fix API validation bug failed: Unable to parse schema', time: '20 min ago', read: false },
  { id: '4', type: 'mention', title: 'You were mentioned', message: '@john check the auth changes in PR #432', time: '1 hour ago', read: true },
  { id: '5', type: 'info', title: 'New Feature', message: 'Browser Agent is now available! Try automating your tests.', time: '2 hours ago', read: true },
  { id: '6', type: 'task_complete', title: 'Task Completed', message: 'Add dark mode toggle finished successfully', time: '3 hours ago', read: true },
];

const typeConfig = {
  task_complete: { icon: 'checkmark-circle' as const, color: '#10b981' },
  approval_needed: { icon: 'eye' as const, color: '#f59e0b' },
  error: { icon: 'alert-circle' as const, color: '#ef4444' },
  info: { icon: 'information-circle' as const, color: '#06b6d4' },
  mention: { icon: 'at' as const, color: '#8b5cf6' },
};

export function NotificationsScreen() {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === 'dark';
  const [notifications, setNotifications] = useState(mockNotifications);

  const styles = createStyles(isDark);

  const unreadCount = notifications.filter(n => !n.read).length;

  const markAllRead = () => {
    setNotifications(notifications.map(n => ({ ...n, read: true })));
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Notifications</Text>
        {unreadCount > 0 && (
          <TouchableOpacity onPress={markAllRead}>
            <Text style={styles.markAllRead}>Mark all read</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Unread Count */}
      {unreadCount > 0 && (
        <View style={styles.unreadBanner}>
          <Ionicons name="notifications" size={18} color="#06b6d4" />
          <Text style={styles.unreadText}>{unreadCount} unread notification{unreadCount > 1 ? 's' : ''}</Text>
        </View>
      )}

      {/* Notifications List */}
      <ScrollView showsVerticalScrollIndicator={false}>
        {notifications.map((notification) => {
          const config = typeConfig[notification.type];
          return (
            <TouchableOpacity 
              key={notification.id} 
              style={[styles.notificationCard, !notification.read && styles.unreadCard]}
            >
              <View style={[styles.iconContainer, { backgroundColor: config.color + '20' }]}>
                <Ionicons name={config.icon} size={22} color={config.color} />
              </View>
              <View style={styles.notificationContent}>
                <View style={styles.notificationHeader}>
                  <Text style={styles.notificationTitle}>{notification.title}</Text>
                  {!notification.read && <View style={styles.unreadDot} />}
                </View>
                <Text style={styles.notificationMessage}>{notification.message}</Text>
                <Text style={styles.notificationTime}>{notification.time}</Text>
              </View>
            </TouchableOpacity>
          );
        })}
        <View style={{ height: 20 }} />
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
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: isDark ? '#fff' : '#0f172a',
  },
  markAllRead: {
    fontSize: 14,
    color: '#06b6d4',
  },
  unreadBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#06b6d420',
    marginHorizontal: 20,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 12,
    gap: 10,
    marginBottom: 16,
  },
  unreadText: {
    color: '#06b6d4',
    fontSize: 14,
    fontWeight: '500',
  },
  notificationCard: {
    flexDirection: 'row',
    backgroundColor: isDark ? '#12121a' : '#fff',
    marginHorizontal: 20,
    borderRadius: 16,
    padding: 16,
    marginBottom: 10,
    gap: 14,
  },
  unreadCard: {
    borderLeftWidth: 3,
    borderLeftColor: '#06b6d4',
  },
  iconContainer: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  notificationContent: {
    flex: 1,
  },
  notificationHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  notificationTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: isDark ? '#fff' : '#0f172a',
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#06b6d4',
  },
  notificationMessage: {
    fontSize: 14,
    color: '#64748b',
    lineHeight: 20,
    marginBottom: 6,
  },
  notificationTime: {
    fontSize: 12,
    color: '#94a3b8',
  },
});

