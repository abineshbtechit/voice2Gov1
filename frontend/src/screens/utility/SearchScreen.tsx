import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { ApiClient } from '../../api/client';
import { CloudBG } from '../../components/common/Backgrounds';
import { GlassCard, Chip } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface SearchScreenProps {
  onClose: () => void;
  onSelectComplaint: (id: string) => void;
  onVoiceSearch?: () => void;
}

export const SearchScreen: React.FC<SearchScreenProps> = ({
  onClose,
  onSelectComplaint,
  onVoiceSearch,
}) => {
  const { theme, isDark } = useAppTheme();

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (text: string) => {
    setQuery(text);
    if (!text.trim()) {
      setResults([]);
      return;
    }

    try {
      setLoading(true);
      const res = await ApiClient.get(`/search?q=${encodeURIComponent(text)}`);
      if (res.success && res.data?.items) {
        setResults(res.data.items);
      }
    } catch {
      // Empty fallback
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.5} />

      {/* Top Bar with Cancel */}
      <View style={styles.topBar}>
        <View style={{ flex: 1 }} />
        <TouchableOpacity onPress={onClose}>
          <Text style={[styles.cancelText, { color: theme.fg }]}>Cancel</Text>
        </TouchableOpacity>
      </View>

      {/* Spotlight Search Floating Input */}
      <View style={styles.searchBarWrapper}>
        <View
          style={[
            styles.searchBar,
            {
              backgroundColor: theme.glassBgStrong,
              borderColor: theme.glassBorder,
            },
          ]}
        >
          <Icons.search size={20} color={theme.fg} />
          <TextInput
            placeholder="Search complaints, categories, locations..."
            placeholderTextColor={theme.fgFaint}
            value={query}
            onChangeText={handleSearch}
            autoFocus
            style={[styles.searchInput, { color: theme.fg }]}
          />
          {onVoiceSearch && (
            <TouchableOpacity
              onPress={onVoiceSearch}
              style={[
                styles.micBtn,
                { backgroundColor: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)' },
              ]}
            >
              <Icons.mic size={18} color={theme.fg} />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Quick Category Chips */}
      {!query && (
        <View style={styles.quickChipsWrapper}>
          <Text style={[styles.chipsHeading, { color: theme.fgMuted }]}>
            Popular searches
          </Text>
          <View style={styles.chipsRow}>
            {['Water logging', 'Broken streetlight', 'Pothole', 'Sewage line'].map(
              (tag) => (
                <Chip
                  key={tag}
                  tone="neutral"
                  onPress={() => handleSearch(tag)}
                  style={{ marginRight: 8, marginBottom: 8 }}
                >
                  {tag}
                </Chip>
              )
            )}
          </View>
        </View>
      )}

      {/* Search Results */}
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.resultsScroll}
      >
        {loading ? (
          <View style={{ paddingTop: 40, alignItems: 'center' }}>
            <ActivityIndicator size="small" color={theme.fg} />
          </View>
        ) : results.length > 0 ? (
          results.map((item) => (
            <GlassCard
              key={item.id}
              padding={16}
              radius={Radius.lg}
              style={{ marginBottom: 10 }}
            >
              <TouchableOpacity onPress={() => onSelectComplaint(item.id)}>
                <Text style={{ fontSize: 16, fontWeight: '600', color: theme.fg }}>
                  {item.title}
                </Text>
                <Text style={{ fontSize: 13, color: theme.fgMuted, marginTop: 4 }}>
                  {item.department?.name || 'Department'} · {item.address}
                </Text>
              </TouchableOpacity>
            </GlassCard>
          ))
        ) : query ? (
          <View style={{ alignItems: 'center', paddingTop: 40 }}>
            <Icons.search size={48} color={theme.fgMuted} />
            <Text style={{ fontSize: 17, fontWeight: '600', color: theme.fg, marginTop: 12 }}>
              Nothing found.
            </Text>
            <Text style={{ fontSize: 13, color: theme.fgMuted, marginTop: 4 }}>
              Try searching with a broader civic keyword.
            </Text>
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    position: 'relative',
  },
  topBar: {
    marginTop: 64,
    paddingHorizontal: 20,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cancelText: {
    fontSize: 15,
    fontWeight: '600',
  },
  searchBarWrapper: {
    paddingHorizontal: 20,
    marginTop: 14,
  },
  searchBar: {
    height: 56,
    borderRadius: Radius.xl,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderWidth: StyleSheet.hairlineWidth,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.15,
    shadowRadius: 18,
    elevation: 4,
  },
  searchInput: {
    flex: 1,
    fontSize: 16,
    fontWeight: '500',
    padding: 0,
  },
  micBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  quickChipsWrapper: {
    paddingHorizontal: 20,
    marginTop: 24,
  },
  chipsHeading: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginBottom: 10,
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  resultsScroll: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 40,
  },
});

