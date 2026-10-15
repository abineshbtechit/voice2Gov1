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
import { ApiClient } from '../../api/client';
import { CloudBG } from '../../components/common/Backgrounds';
import { GlassCard, BigCTA } from '../../components/common/UIComponents';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface AdminSettingsScreenProps {
  onBack: () => void;
}

export const AdminSettingsScreen: React.FC<AdminSettingsScreenProps> = ({ onBack }) => {
  const { theme, isDark } = useAppTheme();

  const [settings, setSettings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>('');
  const [updating, setUpdating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const res = await ApiClient.get('/admin/settings');
      if (res.success && Array.isArray(res.data)) {
        setSettings(res.data);
      }
    } catch {
      // Fallback
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSetting = async (key: string) => {
    setUpdating(true);
    setMessage(null);
    try {
      let parsedValue: any = editValue;
      try {
        parsedValue = JSON.parse(editValue);
      } catch {
        // Keep string if not valid JSON
      }

      const res = await ApiClient.put(`/admin/settings/${encodeURIComponent(key)}`, {
        value: parsedValue,
      });

      if (res.success) {
        setMessage(`Setting "${key}" updated successfully.`);
        setEditingKey(null);
        fetchSettings();
      } else {
        setMessage(res.message || 'Failed to update setting.');
      }
    } catch (e: any) {
      setMessage(e?.message || 'Update failed.');
    } finally {
      setUpdating(false);
    }
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.5} />

      {/* Header */}
      <View style={styles.topHeader}>
        <TouchableOpacity
          onPress={onBack}
          style={[
            styles.backBtn,
            { backgroundColor: theme.glassBg, borderColor: theme.glassBorder },
          ]}
        >
          <Icons.arrowLeft size={18} color={theme.fg} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: theme.fg }]}>System Settings</Text>
        <View style={{ width: 38 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <Text style={[styles.subtitle, { color: theme.fgMuted }]}>
          Configure core civic dispatch rules, SLA thresholds, and priority weights.
        </Text>

        {message && (
          <GlassCard padding={12} radius={Radius.md} style={{ marginTop: 12 }}>
            <Text style={{ fontSize: 13, color: theme.fg, fontWeight: '500' }}>{message}</Text>
          </GlassCard>
        )}

        {loading ? (
          <View style={{ paddingVertical: 40, alignItems: 'center' }}>
            <ActivityIndicator size="small" color={theme.fg} />
          </View>
        ) : settings.length === 0 ? (
          <View style={{ paddingVertical: 40, alignItems: 'center' }}>
            <Text style={{ color: theme.fgMuted }}>No system settings found.</Text>
          </View>
        ) : (
          <View style={{ marginTop: 16, gap: 12 }}>
            {settings.map((item) => {
              const isEditing = editingKey === item.key;
              const valueStr =
                typeof item.value === 'object' ? JSON.stringify(item.value, null, 2) : String(item.value);

              return (
                <GlassCard key={item.key} padding={16} radius={Radius.lg}>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Text style={{ fontSize: 14, fontWeight: '700', color: theme.fg, fontFamily: 'monospace' }}>
                      {item.key}
                    </Text>
                    <TouchableOpacity
                      onPress={() => {
                        if (isEditing) {
                          setEditingKey(null);
                        } else {
                          setEditingKey(item.key);
                          setEditValue(valueStr);
                        }
                      }}
                    >
                      <Text style={{ fontSize: 13, color: theme.fg, fontWeight: '600' }}>
                        {isEditing ? 'Cancel' : 'Edit'}
                      </Text>
                    </TouchableOpacity>
                  </View>

                  {item.description && (
                    <Text style={{ fontSize: 12, color: theme.fgMuted, marginTop: 4 }}>
                      {item.description}
                    </Text>
                  )}

                  {isEditing ? (
                    <View style={{ marginTop: 12 }}>
                      <TextInput
                        value={editValue}
                        onChangeText={setEditValue}
                        multiline
                        style={[
                          styles.editInput,
                          { color: theme.fg, borderColor: theme.glassBorder, backgroundColor: theme.glassBg },
                        ]}
                      />
                      <TouchableOpacity
                        onPress={() => handleSaveSetting(item.key)}
                        disabled={updating}
                        style={[styles.saveBtn, { backgroundColor: theme.ctaBg }]}
                      >
                        <Text style={{ color: theme.ctaFg, fontWeight: '600', fontSize: 13 }}>
                          {updating ? 'Saving...' : 'Save Setting'}
                        </Text>
                      </TouchableOpacity>
                    </View>
                  ) : (
                    <View
                      style={{
                        marginTop: 10,
                        backgroundColor: theme.glassBg,
                        padding: 10,
                        borderRadius: 8,
                      }}
                    >
                      <Text style={{ fontSize: 12, fontFamily: 'monospace', color: theme.fg }}>
                        {valueStr}
                      </Text>
                    </View>
                  )}
                </GlassCard>
              );
            })}
          </View>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1 },
  topHeader: {
    marginTop: 54,
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
  headerTitle: { fontSize: 17, fontWeight: '700' },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 40,
  },
  subtitle: { fontSize: 13, lineHeight: 18 },
  editInput: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    fontSize: 13,
    fontFamily: 'monospace',
    minHeight: 70,
  },
  saveBtn: {
    marginTop: 10,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
});
