import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  TextInput,
  Alert,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { ApiClient } from '../../api/client';
import { CloudBG } from '../../components/common/Backgrounds';
import { GlassCard, BigCTA } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface CategoriesScreenProps {
  onBack: () => void;
  onSelectCategory: (categoryId: string, categoryName: string) => void;
}

export const CategoriesScreen: React.FC<CategoriesScreenProps> = ({
  onBack,
  onSelectCategory,
}) => {
  const { theme, isDark } = useAppTheme();
  const { user } = useAuth();

  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Admin Create Category modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newCatName, setNewCatName] = useState('');
  const [newCatCode, setNewCatCode] = useState('');
  const [newCatDesc, setNewCatDesc] = useState('');
  const [newCatSeverity, setNewCatSeverity] = useState('3');
  const [newCatSla, setNewCatSla] = useState('48');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    fetchCategories();
  }, []);

  const fetchCategories = async () => {
    try {
      setLoading(true);
      const res = await ApiClient.get('/categories');
      const catList = Array.isArray(res.data) ? res.data : (res.data?.items || []);
      if (res.success && catList.length > 0) {
        setCategories(catList);
      } else {
        setCategories([
          { id: '1', name: 'Water & Sewage', severity_level: 4 },
          { id: '2', name: 'Roads & Potholes', severity_level: 3 },
          { id: '3', name: 'Streetlights & Power', severity_level: 3 },
          { id: '4', name: 'Sanitation & Garbage', severity_level: 2 },
          { id: '5', name: 'Environment & Trees', severity_level: 2 },
          { id: '6', name: 'Public Infrastructure', severity_level: 4 },
        ]);
      }
    } catch {
      setCategories([
        { id: '1', name: 'Water & Sewage', severity_level: 4 },
        { id: '2', name: 'Roads & Potholes', severity_level: 3 },
        { id: '3', name: 'Streetlights & Power', severity_level: 3 },
        { id: '4', name: 'Sanitation & Garbage', severity_level: 2 },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCategory = async () => {
    if (!newCatName.trim() || !newCatCode.trim()) {
      setCreateError('Name and unique category code are required.');
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const res = await ApiClient.post('/admin/categories', {
        name: newCatName.trim(),
        code: newCatCode.trim().toUpperCase(),
        description: newCatDesc.trim() || undefined,
        severity_level: parseInt(newCatSeverity, 10) || 3,
        sla_hours: parseInt(newCatSla, 10) || 48,
      });

      if (res.success) {
        setShowCreateModal(false);
        setNewCatName('');
        setNewCatCode('');
        setNewCatDesc('');
        fetchCategories();
      } else {
        setCreateError(res.message || 'Failed to create category.');
      }
    } catch (e: any) {
      setCreateError(e?.message || 'Failed to create category.');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteCategory = async (id: string, name: string) => {
    try {
      const res = await ApiClient.delete(`/admin/categories/${id}`);
      if (res.success) {
        fetchCategories();
      }
    } catch {
      // Ignored
    }
  };

  const getCategoryIcon = (name: string) => {
    const lower = name.toLowerCase();
    if (lower.includes('water') || lower.includes('sewage')) return <Icons.water size={28} color={theme.fg} />;
    if (lower.includes('road') || lower.includes('pothole')) return <Icons.road size={28} color={theme.fg} />;
    if (lower.includes('light') || lower.includes('power')) return <Icons.bulb size={28} color={theme.fg} />;
    if (lower.includes('sanitation') || lower.includes('garbage')) return <Icons.trash size={28} color={theme.fg} />;
    return <Icons.building size={28} color={theme.fg} />;
  };

  const isAdmin = user?.role === 'admin';

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.5} />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={onBack}
          style={[
            styles.backBtn,
            { backgroundColor: theme.glassBg, borderColor: theme.glassBorder },
          ]}
        >
          <Icons.arrowLeft size={18} color={theme.fg} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: theme.fg }]}>Categories</Text>
        <View style={{ width: 38 }} />
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <View>
            <Text style={[styles.title, { color: theme.fg }]}>
              What's the issue{'\n'}about?
            </Text>
            <Text style={[styles.sub, { color: theme.fgMuted }]}>
              Choose a civic department category or let AI auto-categorize.
            </Text>
          </View>

          {/* Admin Create Category CTA */}
          {isAdmin && (
            <TouchableOpacity
              onPress={() => setShowCreateModal(!showCreateModal)}
              style={[
                styles.addCatBtn,
                { backgroundColor: theme.ctaBg },
              ]}
            >
              <Text style={{ color: theme.ctaFg, fontWeight: '700', fontSize: 12 }}>
                {showCreateModal ? 'Close' : '+ Add'}
              </Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Admin Create Category Modal Form */}
        {showCreateModal && (
          <GlassCard strong padding={16} radius={Radius.lg} style={{ marginTop: 16 }}>
            <Text style={{ fontSize: 16, fontWeight: '700', color: theme.fg }}>
              Create New Complaint Category
            </Text>
            <TextInput
              placeholder="Category Name (e.g., Street Dogs & Animals)"
              placeholderTextColor={theme.fgMuted}
              value={newCatName}
              onChangeText={setNewCatName}
              style={[styles.input, { color: theme.fg, borderColor: theme.glassBorder, marginTop: 10 }]}
            />
            <TextInput
              placeholder="Code (e.g., ANIMAL_CONTROL)"
              placeholderTextColor={theme.fgMuted}
              value={newCatCode}
              onChangeText={setNewCatCode}
              autoCapitalize="characters"
              style={[styles.input, { color: theme.fg, borderColor: theme.glassBorder, marginTop: 8 }]}
            />
            <TextInput
              placeholder="Description (optional)"
              placeholderTextColor={theme.fgMuted}
              value={newCatDesc}
              onChangeText={setNewCatDesc}
              style={[styles.input, { color: theme.fg, borderColor: theme.glassBorder, marginTop: 8 }]}
            />
            <View style={{ flexDirection: 'row', gap: 10, marginTop: 8 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 11, color: theme.fgMuted, marginBottom: 4 }}>Severity (1-5)</Text>
                <TextInput
                  placeholder="3"
                  placeholderTextColor={theme.fgMuted}
                  value={newCatSeverity}
                  onChangeText={setNewCatSeverity}
                  keyboardType="numeric"
                  style={[styles.input, { color: theme.fg, borderColor: theme.glassBorder }]}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 11, color: theme.fgMuted, marginBottom: 4 }}>SLA (Hours)</Text>
                <TextInput
                  placeholder="48"
                  placeholderTextColor={theme.fgMuted}
                  value={newCatSla}
                  onChangeText={setNewCatSla}
                  keyboardType="numeric"
                  style={[styles.input, { color: theme.fg, borderColor: theme.glassBorder }]}
                />
              </View>
            </View>

            {createError && (
              <Text style={{ color: '#FF4D4F', fontSize: 12, marginTop: 6 }}>{createError}</Text>
            )}

            <TouchableOpacity
              onPress={handleCreateCategory}
              disabled={creating}
              style={[styles.submitCatBtn, { backgroundColor: theme.ctaBg, marginTop: 12 }]}
            >
              <Text style={{ color: theme.ctaFg, fontWeight: '700', fontSize: 13 }}>
                {creating ? 'Creating...' : 'Save Category'}
              </Text>
            </TouchableOpacity>
          </GlassCard>
        )}

        {loading ? (
          <View style={{ paddingTop: 40, alignItems: 'center' }}>
            <ActivityIndicator size="small" color={theme.fg} />
          </View>
        ) : (
          <View style={styles.grid}>
            {categories.map((c) => (
              <TouchableOpacity
                key={c.id}
                onPress={() => onSelectCategory(c.id, c.name)}
                style={[
                  styles.categoryCard,
                  {
                    backgroundColor: theme.glassBgStrong,
                    borderColor: theme.glassBorder,
                  },
                ]}
              >
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <View style={{ marginBottom: 16 }}>{getCategoryIcon(c.name)}</View>
                  {isAdmin && (
                    <TouchableOpacity
                      onPress={(e) => {
                        e.stopPropagation();
                        handleDeleteCategory(c.id, c.name);
                      }}
                      style={styles.deleteCatBtn}
                    >
                      <Icons.trash size={14} color="#EF4444" />
                    </TouchableOpacity>
                  )}
                </View>

                <View>
                  <Text style={[styles.categoryName, { color: theme.fg }]}>
                    {c.name}
                  </Text>
                  <Text style={[styles.categoryCount, { color: theme.fgMuted }]}>
                    Severity {c.severity_level || 3} · {c.code || 'Active'}
                  </Text>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, position: 'relative' },
  header: {
    marginTop: 64,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  backBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: StyleSheet.hairlineWidth,
  },
  headerTitle: { fontSize: 17, fontWeight: '600' },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 60,
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: -0.8,
    lineHeight: 36,
  },
  sub: {
    fontSize: 14,
    marginTop: 6,
    lineHeight: 20,
  },
  addCatBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginTop: 24,
  },
  categoryCard: {
    width: '48%',
    borderRadius: Radius.lg,
    padding: 16,
    borderWidth: StyleSheet.hairlineWidth,
    justifyContent: 'space-between',
    minHeight: 140,
  },
  categoryName: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: -0.2,
  },
  categoryCount: {
    fontSize: 12,
    marginTop: 4,
  },
  deleteCatBtn: {
    padding: 4,
  },
  input: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    fontSize: 13,
  },
  submitCatBtn: {
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
});
