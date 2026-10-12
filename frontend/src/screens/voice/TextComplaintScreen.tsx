import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { ApiClient } from '../../api/client';
import { MeshBG } from '../../components/common/Backgrounds';
import { GlassCard, BigCTA } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface TextComplaintScreenProps {
  onBack: () => void;
  onSubmitSuccess: (complaint: any) => void;
}

export const TextComplaintScreen: React.FC<TextComplaintScreenProps> = ({
  onBack,
  onSubmitSuccess,
}) => {
  const { theme, isDark } = useAppTheme();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!title.trim() || !description.trim()) {
      setError('Please provide a title and detailed description');
      return;
    }
    setError(null);
    setLoading(true);

    try {
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
        address: 'Sector 4, MG Road, Ward 12',
      });

      if (res.success && res.data) {
        onSubmitSuccess(res.data);
      } else {
        setError(res.message || 'Failed to file complaint');
      }
    } catch (e: any) {
      setError(e?.message || 'Network error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <MeshBG isDark={isDark} />

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
        <Text style={[styles.headerTitle, { color: theme.fg }]}>Text complaint</Text>
        <Text style={[styles.draftBadge, { color: theme.fgMuted }]}>Draft</Text>
      </View>

      <View style={styles.body}>
        {/* Editor Glass Card */}
        <GlassCard strong radius={Radius.xl} padding={20} style={{ flex: 1 }}>
          <TextInput
            placeholder="Complaint title..."
            placeholderTextColor={theme.fgFaint}
            value={title}
            onChangeText={setTitle}
            style={[styles.titleInput, { color: theme.fg }]}
          />
          <TextInput
            placeholder="Describe the issue in detail (location, frequency, severity)..."
            placeholderTextColor={theme.fgFaint}
            value={description}
            onChangeText={setDescription}
            multiline
            style={[styles.descInput, { color: theme.fg }]}
          />

          <View style={styles.cardFooter}>
            <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                <Icons.pin size={16} color={theme.fgMuted} />
                <Text style={{ fontSize: 12, color: theme.fgMuted }}>Sector 4</Text>
              </View>
            </View>
            <Text style={{ fontSize: 12, color: theme.fgMuted, fontFamily: 'monospace' }}>
              {description.length} / 1000
            </Text>
          </View>
        </GlassCard>

        {/* AI Suggestion Box */}
        <GlassCard padding={14} radius={Radius.md} style={{ marginVertical: 12 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
            <Icons.sparkle size={22} color="#4C8DFF" />
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 11, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', color: theme.fgMuted }}>
                AI Categorization
              </Text>
              <Text style={{ fontSize: 13, fontWeight: '600', color: theme.fg, marginTop: 2 }}>
                Sanitation · Public Works · Auto Department Routing
              </Text>
            </View>
          </View>
        </GlassCard>

        {error && (
          <Text style={[styles.errorText, { color: '#E5484D' }]}>{error}</Text>
        )}

        {/* Submit CTA */}
        <BigCTA
          onPress={handleSubmit}
          disabled={loading || !title || !description}
          icon={loading ? <ActivityIndicator size="small" color={theme.ctaFg} /> : <Icons.arrowRight size={18} color={theme.ctaFg} />}
        >
          {loading ? 'Submitting...' : 'Submit complaint'}
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
  draftBadge: {
    fontSize: 14,
    fontWeight: '600',
  },
  body: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 40,
  },
  titleInput: {
    fontSize: 20,
    fontWeight: '700',
    letterSpacing: -0.4,
    marginBottom: 12,
    padding: 0,
  },
  descInput: {
    fontSize: 15,
    lineHeight: 22,
    letterSpacing: -0.1,
    flex: 1,
    textAlignVertical: 'top',
    padding: 0,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 12,
  },
  errorText: {
    fontSize: 13,
    marginBottom: 12,
    fontWeight: '500',
  },
});

