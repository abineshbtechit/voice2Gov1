import React, { useState } from 'react';
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
import { GlassCard, BigCTA, TextField, Chip } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface ComplaintReviewScreenProps {
  initialTitle?: string;
  initialDescription?: string;
  onBack: () => void;
  onSubmitSuccess: (complaint: any) => void;
}

export const ComplaintReviewScreen: React.FC<ComplaintReviewScreenProps> = ({
  initialTitle = 'Water logging & Sewage Overflow on Main Road',
  initialDescription = 'Severe waterlogging near bus stop sector 4 due to clogged drainage line. Impeding pedestrian access and creating health hazards.',
  onBack,
  onSubmitSuccess,
}) => {
  const { theme, isDark } = useAppTheme();

  const [title, setTitle] = useState(initialTitle);
  const [description, setDescription] = useState(initialDescription);
  const [categoryName, setCategoryName] = useState('Sewage & Drainage');
  const [address, setAddress] = useState('Sector 4, MG Road, Ward 12');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!title.trim() || !description.trim()) {
      setError('Please provide a title and description');
      return;
    }
    setError(null);
    setLoading(true);

    try {
      // First fetch active category
      const catRes = await ApiClient.get('/categories');
      let categoryId = '507f1f77bcf86cd799439012';
      if (catRes.success && catRes.data?.items?.length > 0) {
        categoryId = catRes.data.items[0].id;
      }

      const res = await ApiClient.post('/complaints', {
        title,
        description,
        category_id: categoryId,
        location: {
          type: 'Point',
          coordinates: [80.2707, 13.0827],
        },
        address,
      });

      if (res.success && res.data) {
        onSubmitSuccess(res.data);
      } else {
        setError(res.message || 'Failed to file complaint');
      }
    } catch (e: any) {
      setError(e?.message || 'Network error while filing complaint');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.6} />

      {/* Top Header */}
      <View style={styles.topHeader}>
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
        <Text style={[styles.headerTitle, { color: theme.fg }]}>Review complaint</Text>
        <View style={{ width: 38 }} />
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {/* AI Categorized Badge */}
        <View style={{ alignItems: 'flex-start', marginBottom: 16 }}>
          <Chip tone="info">AI extracted & mapped</Chip>
        </View>

        {/* Title Field */}
        <Text style={[styles.fieldLabel, { color: theme.fgMuted }]}>Title</Text>
        <TextField value={title} onChangeText={setTitle} />

        {/* Category & Department pill */}
        <Text style={[styles.fieldLabel, { color: theme.fgMuted, marginTop: 18 }]}>
          Department & Category
        </Text>
        <GlassCard padding={16} radius={Radius.md}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Icons.water size={22} color={theme.fg} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '600', color: theme.fg }}>
                {categoryName}
              </Text>
              <Text style={{ fontSize: 12, color: theme.fgMuted, marginTop: 2 }}>
                Auto-assigned to Public Works / Water Board
              </Text>
            </View>
          </View>
        </GlassCard>

        {/* Description Field */}
        <Text style={[styles.fieldLabel, { color: theme.fgMuted, marginTop: 18 }]}>
          Detailed summary
        </Text>
        <GlassCard padding={16} radius={Radius.md}>
          <Text style={{ fontSize: 14, color: theme.fg, lineHeight: 22 }}>
            {description}
          </Text>
        </GlassCard>

        {/* Location Field */}
        <Text style={[styles.fieldLabel, { color: theme.fgMuted, marginTop: 18 }]}>
          Detected Location
        </Text>
        <GlassCard padding={16} radius={Radius.md}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Icons.pin size={22} color={theme.fg} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 15, fontWeight: '600', color: theme.fg }}>
                {address}
              </Text>
              <Text style={{ fontSize: 12, color: theme.fgMuted, marginTop: 2 }}>
                13.0827° N, 80.2707° E · Ward 12
              </Text>
            </View>
          </View>
        </GlassCard>

        {error && (
          <Text style={[styles.errorText, { color: '#E5484D' }]}>{error}</Text>
        )}
      </ScrollView>

      {/* Submit CTA */}
      <View style={styles.bottomCta}>
        <BigCTA
          onPress={handleSubmit}
          disabled={loading}
          icon={loading ? <ActivityIndicator size="small" color={theme.ctaFg} /> : <Icons.arrowRight size={18} color={theme.ctaFg} />}
        >
          {loading ? 'Submitting...' : 'File complaint'}
        </BigCTA>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    position: 'relative',
    justifyContent: 'space-between',
  },
  topHeader: {
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
    letterSpacing: -0.2,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 110,
  },
  fieldLabel: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  errorText: {
    fontSize: 13,
    marginTop: 14,
    fontWeight: '500',
  },
  bottomCta: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
});

