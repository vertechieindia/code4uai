/**
 * Tasks Screen
 */
import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  useColorScheme,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';

interface Task {
  id: string;
  title: string;
  description: string;
  type: 'refactor' | 'add_api' | 'fix_bug' | 'generate';
  status: 'queued' | 'running' | 'completed' | 'failed' | 'review';
  tenant: string;
  files: number;
  time: string;
  duration: string;
}

const mockTasks: Task[] = [
  { id: '1', title: 'Rename email to primaryEmail', description: 'Update field name across all services', type: 'refactor', status: 'completed', tenant: 'Acme Corp', files: 8, time: '2 min ago', duration: '12s' },
  { id: '2', title: 'Add authentication middleware', description: 'Implement JWT validation for API routes', type: 'add_api', status: 'running', tenant: 'TechStart', files: 3, time: '5 min ago', duration: '45s' },
  { id: '3', title: 'Refactor payment module', description: 'Update payment processor integration', type: 'refactor', status: 'review', tenant: 'FinanceX', files: 12, time: '15 min ago', duration: '1m 23s' },
  { id: '4', title: 'Fix API validation bug', description: 'Correct validation in patient endpoint', type: 'fix_bug', status: 'failed', tenant: 'HealthTech', files: 0, time: '20 min ago', duration: '8s' },
  { id: '5', title: 'Add dark mode toggle', description: 'Implement theme switching in settings', type: 'generate', status: 'completed', tenant: 'Acme Corp', files: 4, time: '25 min ago', duration: '34s' },
];

const statusConfig = {
  queued: { color: '#64748b', label: 'Queued', icon: 'time-outline' as const },
  running: { color: '#06b6d4', label: 'Running', icon: 'sync' as const },
  completed: { color: '#10b981', label: 'Completed', icon: 'checkmark-circle' as const },
  failed: { color: '#ef4444', label: 'Failed', icon: 'close-circle' as const },
  review: { color: '#f59e0b', label: 'Review', icon: 'eye' as const },
};

const typeConfig = {
  refactor: { color: '#8b5cf6', icon: 'code-slash' as const },
  add_api: { color: '#06b6d4', icon: 'add-circle' as const },
  fix_bug: { color: '#ef4444', icon: 'bug' as const },
  generate: { color: '#10b981', icon: 'flash' as const },
};

const filters = ['All', 'Running', 'Completed', 'Review', 'Failed'];

export function TasksScreen() {
  const colorScheme = useColorScheme();
  const isDark = colorScheme === 'dark';
  const navigation = useNavigation();
  const [activeFilter, setActiveFilter] = useState('All');
  const [search, setSearch] = useState('');

  const styles = createStyles(isDark);

  const filteredTasks = mockTasks.filter(task => {
    const matchesSearch = task.title.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = activeFilter === 'All' || task.status.toLowerCase() === activeFilter.toLowerCase();
    return matchesSearch && matchesFilter;
  });

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Agent Tasks</Text>
        <TouchableOpacity style={styles.addBtn}>
          <Ionicons name="add" size={24} color="#fff" />
        </TouchableOpacity>
      </View>

      {/* Search */}
      <View style={styles.searchContainer}>
        <Ionicons name="search" size={20} color="#64748b" />
        <TextInput
          style={styles.searchInput}
          placeholder="Search tasks..."
          placeholderTextColor="#64748b"
          value={search}
          onChangeText={setSearch}
        />
      </View>

      {/* Filters */}
      <ScrollView 
        horizontal 
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.filtersContainer}
      >
        {filters.map((filter) => (
          <TouchableOpacity
            key={filter}
            style={[styles.filterBtn, activeFilter === filter && styles.filterBtnActive]}
            onPress={() => setActiveFilter(filter)}
          >
            <Text style={[styles.filterText, activeFilter === filter && styles.filterTextActive]}>
              {filter}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Tasks List */}
      <ScrollView showsVerticalScrollIndicator={false} style={styles.tasksList}>
        {filteredTasks.map((task) => (
          <TouchableOpacity 
            key={task.id} 
            style={styles.taskCard}
            onPress={() => navigation.navigate('TaskDetail' as never, { task } as never)}
          >
            <View style={styles.taskHeader}>
              <View style={[styles.typeIcon, { backgroundColor: typeConfig[task.type].color + '20' }]}>
                <Ionicons name={typeConfig[task.type].icon} size={18} color={typeConfig[task.type].color} />
              </View>
              <View style={[styles.statusBadge, { backgroundColor: statusConfig[task.status].color + '20' }]}>
                <Ionicons name={statusConfig[task.status].icon} size={12} color={statusConfig[task.status].color} />
                <Text style={[styles.statusText, { color: statusConfig[task.status].color }]}>
                  {statusConfig[task.status].label}
                </Text>
              </View>
            </View>

            <Text style={styles.taskTitle}>{task.title}</Text>
            <Text style={styles.taskDescription}>{task.description}</Text>

            <View style={styles.taskFooter}>
              <Text style={styles.taskMeta}>{task.tenant}</Text>
              <Text style={styles.taskMeta}>{task.files} files</Text>
              <Text style={styles.taskMeta}>{task.duration}</Text>
              <Text style={styles.taskMeta}>{task.time}</Text>
            </View>
          </TouchableOpacity>
        ))}
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
  addBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#06b6d4',
    alignItems: 'center',
    justifyContent: 'center',
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: isDark ? '#12121a' : '#fff',
    marginHorizontal: 20,
    borderRadius: 12,
    paddingHorizontal: 16,
    gap: 12,
  },
  searchInput: {
    flex: 1,
    height: 48,
    color: isDark ? '#fff' : '#0f172a',
    fontSize: 16,
  },
  filtersContainer: {
    paddingHorizontal: 20,
    paddingVertical: 16,
    gap: 8,
  },
  filterBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: isDark ? '#12121a' : '#fff',
    marginRight: 8,
  },
  filterBtnActive: {
    backgroundColor: '#06b6d4',
  },
  filterText: {
    fontSize: 14,
    color: isDark ? '#94a3b8' : '#64748b',
  },
  filterTextActive: {
    color: '#fff',
    fontWeight: '600',
  },
  tasksList: {
    flex: 1,
    paddingHorizontal: 20,
  },
  taskCard: {
    backgroundColor: isDark ? '#12121a' : '#fff',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
  },
  taskHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  typeIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '500',
  },
  taskTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: isDark ? '#fff' : '#0f172a',
    marginBottom: 4,
  },
  taskDescription: {
    fontSize: 14,
    color: '#64748b',
    marginBottom: 12,
  },
  taskFooter: {
    flexDirection: 'row',
    gap: 12,
  },
  taskMeta: {
    fontSize: 12,
    color: '#64748b',
  },
});

