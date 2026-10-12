import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { ApiClient } from '../../api/client';
import { CloudBG } from '../../components/common/Backgrounds';
import { GlassCard } from '../../components/common/UIComponents';
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

  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCategories();
  }, []);

  const fetchCategories = async () => {
    try {
      setLoading(true);
      const res = await ApiClient.get('/categories');
      if (res.success && res.data?.items) {
        setCategories(res.data.items);
      } else {
        // Fallback default civic categories if empty
        setCategories([
          { id: '1', name: 'Water & Sewage', severity_level: 4, openCount: 12 },
          { id: '2', name: 'Roads & Potholes', severity_level: 3, openCount: 34 },
          { id: '3', name: 'Streetlights & Power', severity_level: 3, openCount: 8 },
          { id: '4', name: 'Sanitation & Garbage', severity_level: 2, openCount: 21 },
          { id: '5', name: 'Environment & Trees', severity_level: 2, openCount: 6 },
          { id: '6', name: 'Public Infrastructure', severity_level: 4, openCount: 15 },
        ]);
      }
    } catch {
      setCategories([
        { id: '1', name: 'Water & Sewage', severity_level: 4, openCount: 12 },
        { id: '2', name: 'Roads & Potholes', severity_level: 3, openCount: 34 },
        { id: '3', name: 'Streetlights & Power', severity_level: 3, openCount: 8 },
        { id: '4', name: 'Sanitation & Garbage', severity_level: 2, openCount: 21 },
      ]);
    } finally {
      setLoading(false);
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

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.5} />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={onBack}
          style={[
            styles.backBtn,
            {
              backgroundColor: theme.glassBg,
              borderColor: theme.glassBorder,
            },
          ]}
        >
          <Icons.arrowLeft size={18} color={theme.fg} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: theme.fg }]}>Categories</Text>
        <View style={{ width: 38 }} />
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        <Text style={[styles.title, { color: theme.fg }]}>
          What's the issue{'\n'}about?
        </Text>
        <Text style={[styles.sub, { color: theme.fgMuted }]}>
          Choose a civic department category or let AI auto-categorize.
        </Text>

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
                <View style={{ marginBottom: 16 }}>{getCategoryIcon(c.name)}</View>
                <View>
                  <Text style={[styles.categoryName, { color: theme.fg }]}>
                    {c.name}
                  </Text>
                  <Text style={[styles.categoryCount, { color: theme.fgMuted }]}>
                    Severity {c.severity_level || 3} · Priority Active
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
  container: {
    flex: 1,
    position: 'relative',
  },
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
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 40,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    letterSpacing: -0.8,
    lineHeight: 32,
  },
  sub: {
    fontSize: 14,
    marginTop: 8,
    marginBottom: 24,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  categoryCard: {
    width: '48%',
    minHeight: 130,
    padding: 18,
    borderRadius: Radius.xl,
    justifyContent: 'space-between',
    borderWidth: StyleSheet.hairlineWidth,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 14,
    elevation: 3,
  },
  categoryName: {
    fontSize: 15,
    fontWeight: '600',
    letterSpacing: -0.2,
  },
  categoryCount: {
    fontSize: 11,
    marginTop: 3,
    fontWeight: '500',
  },
});

