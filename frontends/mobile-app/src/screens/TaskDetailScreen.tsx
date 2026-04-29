/**
 * Task Detail Screen
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
import { useNavigation, useRoute } from '@react-navigation/native';

const statusConfig = {
  queued: { color: '#64748b', label: 'Queued' },
  running: { color: '#06b6d4', label: 'Running' },
  completed: { color: '#10b981', label: 'Completed' },
  failed: { color: '#ef4444', label: 'Failed' },
  review: { color: '#f59e0b', label: 'Awaiting Review' },
};

const mockFiles = [
  { path: 'src/models/user.py', changes: '+15 / -8' },
  { path: 'src/api/routes/users.py', changes: '+23 / -12' },
  { path: 'src/schemas/user.py', changes: '+5 / -5' },
  { path: 'tests/test_user.py', changes: '+42 / -0' },
];

const mockTimeline = [
  { state: 'INIT', time: '10:32:15', status: 'completed' },
  { state: 'IMPACT_ANALYZED', time: '10:32:18', status: 'completed' },
  { state: 'PLAN_GENERATED', time: '10:32:22', status: 'completed' },
  { state: 'CONTRACT_VALIDATED', time: '10:32:25', status: 'completed' },
  { state: 'CODE_GENERATED', time: '10:32:42', status: 'completed' },
  { state: 'VERIFIED', time: '10:32:45', status: 'completed' },
  { state: 'READY_FOR_REVIEW', time: '10:32:45', status: 'current' },
];

export function TaskDetailScreen() {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === 'dark';
  const navigation = useNavigation();
  const route = useRoute();
  const task = (route.params as any)?.task || {};

  const styles = createStyles(isDark);
  const status = statusConfig[task.status as keyof typeof statusConfig] || statusConfig.queued;

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={isDark ? '#fff' : '#0f172a'} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Task Details</Text>
        <TouchableOpacity>
          <Ionicons name="ellipsis-horizontal" size={24} color={isDark ? '#fff' : '#0f172a'} />
        </TouchableOpacity>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Status Card */}
        <View style={styles.statusCard}>
          <View style={[styles.statusBadge, { backgroundColor: status.color + '20' }]}>
            <Text style={[styles.statusText, { color: status.color }]}>{status.label}</Text>
          </View>
          <Text style={styles.taskTitle}>{task.title || 'Task Title'}</Text>
          <Text style={styles.taskDescription}>{task.description || 'Task description'}</Text>
          
          <View style={styles.metaRow}>
            <View style={styles.metaItem}>
              <Ionicons name="business-outline" size={16} color="#64748b" />
              <Text style={styles.metaText}>{task.tenant || 'Tenant'}</Text>
            </View>
            <View style={styles.metaItem}>
              <Ionicons name="time-outline" size={16} color="#64748b" />
              <Text style={styles.metaText}>{task.duration || '0s'}</Text>
            </View>
            <View style={styles.metaItem}>
              <Ionicons name="document-outline" size={16} color="#64748b" />
              <Text style={styles.metaText}>{task.files || 0} files</Text>
            </View>
          </View>
        </View>

        {/* State Timeline */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Execution Timeline</Text>
          <View style={styles.timeline}>
            {mockTimeline.map((item, i) => (
              <View key={i} style={styles.timelineItem}>
                <View style={styles.timelineLeft}>
                  <View style={[
                    styles.timelineDot,
                    { backgroundColor: 
                      item.status === 'completed' ? '#10b981' :
                      item.status === 'current' ? '#06b6d4' : '#64748b'
                    }
                  ]} />
                  {i < mockTimeline.length - 1 && <View style={styles.timelineLine} />}
                </View>
                <View style={styles.timelineContent}>
                  <Text style={styles.timelineState}>{item.state}</Text>
                  <Text style={styles.timelineTime}>{item.time}</Text>
                </View>
              </View>
            ))}
          </View>
        </View>

        {/* Changed Files */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Changed Files</Text>
          {mockFiles.map((file, i) => (
            <View key={i} style={styles.fileItem}>
              <Ionicons name="document-text-outline" size={18} color="#06b6d4" />
              <View style={styles.fileInfo}>
                <Text style={styles.filePath}>{file.path}</Text>
                <Text style={styles.fileChanges}>{file.changes}</Text>
              </View>
            </View>
          ))}
        </View>

        {/* Actions */}
        {task.status === 'review' && (
          <View style={styles.actions}>
            <TouchableOpacity style={styles.rejectBtn}>
              <Ionicons name="close" size={20} color="#ef4444" />
              <Text style={styles.rejectText}>Reject</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.approveBtn}>
              <Ionicons name="checkmark" size={20} color="#fff" />
              <Text style={styles.approveText}>Approve & Apply</Text>
            </TouchableOpacity>
          </View>
        )}

        {task.status === 'failed' && (
          <TouchableOpacity style={styles.retryBtn}>
            <Ionicons name="refresh" size={20} color="#fff" />
            <Text style={styles.approveText}>Retry Task</Text>
          </TouchableOpacity>
        )}

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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: isDark ? '#1e1e2e' : '#e2e8f0',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: isDark ? '#fff' : '#0f172a',
  },
  statusCard: {
    backgroundColor: isDark ? '#12121a' : '#fff',
    marginHorizontal: 20,
    borderRadius: 20,
    padding: 20,
    marginBottom: 20,
  },
  statusBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    marginBottom: 12,
  },
  statusText: {
    fontSize: 13,
    fontWeight: '600',
  },
  taskTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: isDark ? '#fff' : '#0f172a',
    marginBottom: 8,
  },
  taskDescription: {
    fontSize: 15,
    color: '#64748b',
    marginBottom: 16,
    lineHeight: 22,
  },
  metaRow: {
    flexDirection: 'row',
    gap: 20,
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  metaText: {
    fontSize: 13,
    color: '#64748b',
  },
  section: {
    marginHorizontal: 20,
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: isDark ? '#fff' : '#0f172a',
    marginBottom: 16,
  },
  timeline: {
    paddingLeft: 4,
  },
  timelineItem: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  timelineLeft: {
    alignItems: 'center',
    marginRight: 16,
  },
  timelineDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    zIndex: 1,
  },
  timelineLine: {
    width: 2,
    flex: 1,
    backgroundColor: isDark ? '#1e1e2e' : '#e2e8f0',
    marginVertical: 4,
  },
  timelineContent: {
    flex: 1,
    backgroundColor: isDark ? '#12121a' : '#fff',
    padding: 12,
    borderRadius: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  timelineState: {
    fontSize: 14,
    fontWeight: '500',
    color: isDark ? '#fff' : '#0f172a',
  },
  timelineTime: {
    fontSize: 12,
    color: '#64748b',
    fontFamily: 'monospace',
  },
  fileItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: isDark ? '#12121a' : '#fff',
    padding: 14,
    borderRadius: 12,
    marginBottom: 8,
    gap: 12,
  },
  fileInfo: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  filePath: {
    fontSize: 13,
    color: isDark ? '#fff' : '#0f172a',
    fontFamily: 'monospace',
  },
  fileChanges: {
    fontSize: 12,
    color: '#10b981',
    fontFamily: 'monospace',
  },
  actions: {
    flexDirection: 'row',
    marginHorizontal: 20,
    gap: 12,
  },
  rejectBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#ef444420',
    paddingVertical: 16,
    borderRadius: 14,
    gap: 8,
  },
  rejectText: {
    color: '#ef4444',
    fontSize: 16,
    fontWeight: '600',
  },
  approveBtn: {
    flex: 2,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#10b981',
    paddingVertical: 16,
    borderRadius: 14,
    gap: 8,
  },
  approveText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f59e0b',
    marginHorizontal: 20,
    paddingVertical: 16,
    borderRadius: 14,
    gap: 8,
  },
});

