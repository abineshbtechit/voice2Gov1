import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  TextInput,
  Image,
  Alert,
} from 'react-native';
import { useAppTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { ApiClient } from '../../api/client';
import { ComplaintsApi } from '../../api/complaints';
import { CloudBG } from '../../components/common/Backgrounds';
import { GlassCard, Chip, BigCTA } from '../../components/common/UIComponents';
import { Waveform } from '../../components/voice/Waveform';
import { Icons } from '../../components/common/Icons';
import { Radius } from '../../theme/tokens';

interface ComplaintDetailsScreenProps {
  complaintId: string;
  onBack: () => void;
}

export const ComplaintDetailsScreen: React.FC<ComplaintDetailsScreenProps> = ({
  complaintId,
  onBack,
}) => {
  const { theme, isDark } = useAppTheme();
  const { user } = useAuth();

  const [complaint, setComplaint] = useState<any>(null);
  const [updates, setUpdates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  // Priority Breakdown
  const [priorityData, setPriorityData] = useState<any>(null);
  const [loadingPriority, setLoadingPriority] = useState(false);
  const [showPriority, setShowPriority] = useState(false);

  // Action states
  const [actionModal, setActionModal] = useState<'status' | 'note' | 'complete' | 'edit' | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<string>('PROCESSING');
  const [actionReason, setActionReason] = useState<string>('');
  const [progressNote, setProgressNote] = useState<string>('');
  const [completionSummary, setCompletionSummary] = useState<string>('');
  const [editTitle, setEditTitle] = useState<string>('');
  const [editDesc, setEditDesc] = useState<string>('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchComplaintDetails();
  }, [complaintId]);

  const fetchComplaintDetails = async () => {
    try {
      setLoading(true);
      const res = await ApiClient.get(`/complaints/${complaintId}`);
      if (res.success && res.data) {
        setComplaint(res.data);
        setEditTitle(res.data.title || '');
        setEditDesc(res.data.description || '');
      }

      const updatesRes = await ApiClient.get(`/complaints/${complaintId}/updates`);
      if (updatesRes.success && updatesRes.data?.items) {
        setUpdates(updatesRes.data.items);
      }
    } catch {
      // Fallback
    } finally {
      setLoading(false);
    }
  };

  // Fetch AI Priority breakdown
  const handleFetchPriority = async () => {
    if (showPriority) {
      setShowPriority(false);
      return;
    }
    setLoadingPriority(true);
    try {
      const res = await ComplaintsApi.getPriorityBreakdown(complaintId);
      if (res.success && res.data) {
        setPriorityData(res.data);
        setShowPriority(true);
      }
    } catch {
      // Keep closed
    } finally {
      setLoadingPriority(false);
    }
  };

  // Update Status (Staff / Admin)
  const handleUpdateStatus = async () => {
    if (!actionReason.trim()) {
      setActionMessage('Reason is required for status transition.');
      return;
    }
    setActionLoading(true);
    setActionMessage(null);
    try {
      const res = await ComplaintsApi.updateStatus(complaintId, selectedStatus, actionReason.trim());
      if (res.success) {
        setActionModal(null);
        setActionReason('');
        fetchComplaintDetails();
      } else {
        setActionMessage(res.message || 'Status transition failed.');
      }
    } catch (e: any) {
      setActionMessage(e?.message || 'Update failed.');
    } finally {
      setActionLoading(false);
    }
  };

  // Add Progress Update Note (Staff / Admin)
  const handleAddProgressNote = async () => {
    if (!progressNote.trim()) {
      setActionMessage('Please enter a note for the citizen.');
      return;
    }
    setActionLoading(true);
    setActionMessage(null);
    try {
      const res = await ComplaintsApi.addUpdate(complaintId, progressNote.trim());
      if (res.success) {
        setActionModal(null);
        setProgressNote('');
        fetchComplaintDetails();
      } else {
        setActionMessage(res.message || 'Failed to add progress note.');
      }
    } catch (e: any) {
      setActionMessage(e?.message || 'Failed to post update.');
    } finally {
      setActionLoading(false);
    }
  };

  // Mark Complete (Staff / Admin)
  const handleMarkComplete = async () => {
    if (!completionSummary.trim()) {
      setActionMessage('Please provide a completion resolution summary.');
      return;
    }
    setActionLoading(true);
    setActionMessage(null);
    try {
      const res = await ComplaintsApi.markComplete(complaintId, completionSummary.trim());
      if (res.success) {
        setActionModal(null);
        setCompletionSummary('');
        fetchComplaintDetails();
      } else {
        setActionMessage(res.message || 'Failed to complete complaint.');
      }
    } catch (e: any) {
      setActionMessage(e?.message || 'Failed to complete.');
    } finally {
      setActionLoading(false);
    }
  };

  // Edit Complaint (Citizen, SUBMITTED only)
  const handleEditComplaint = async () => {
    if (!editTitle.trim() || !editDesc.trim()) {
      setActionMessage('Title and description cannot be empty.');
      return;
    }
    setActionLoading(true);
    setActionMessage(null);
    try {
      const res = await ComplaintsApi.update(complaintId, {
        title: editTitle.trim(),
        description: editDesc.trim(),
      });
      if (res.success) {
        setActionModal(null);
        fetchComplaintDetails();
      } else {
        setActionMessage(res.message || 'Failed to update complaint.');
      }
    } catch (e: any) {
      setActionMessage(e?.message || 'Failed to update.');
    } finally {
      setActionLoading(false);
    }
  };

  // Delete image
  const handleDeleteImage = async (imageId: string) => {
    try {
      const res = await ComplaintsApi.deleteImage(complaintId, imageId);
      if (res.success) {
        fetchComplaintDetails();
      }
    } catch {
      // Ignored
    }
  };

  const getTone = (status: string) => {
    if (status === 'COMPLETED' || status === 'RESOLVED') return 'live';
    if (status === 'ONGOING' || status === 'PROCESSING') return 'pending';
    if (status === 'REJECTED') return 'urgent';
    return 'info';
  };

  const isStaffOrAdmin = user && ['organization_staff', 'organization_admin', 'admin'].includes(user.role);
  const isOwner = user && complaint && user.id === complaint.user_id;
  const canEdit = isOwner && complaint?.status === 'SUBMITTED';

  return (
    <View style={[styles.container, { backgroundColor: theme.bg }]}>
      <CloudBG isDark={isDark} opacity={0.5} />

      {/* Top Header */}
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
        <Text style={[styles.headerTitle, { color: theme.fg }]}>
          {complaint?.complaint_number || complaintId.substring(0, 8).toUpperCase()}
        </Text>
        <View style={{ width: 38 }} />
      </View>

      {loading ? (
        <View style={styles.centerLoading}>
          <ActivityIndicator size="small" color={theme.fg} />
        </View>
      ) : complaint ? (
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
          {/* Hero Card */}
          <GlassCard strong radius={Radius.xl} padding={22}>
            <View style={styles.chipRow}>
              <Chip tone={getTone(complaint.status)}>{complaint.status}</Chip>
              {complaint.priority_score && complaint.priority_score > 60 && (
                <Chip tone="urgent">High priority ({Math.round(complaint.priority_score)})</Chip>
              )}
            </View>

            <Text style={[styles.complaintTitle, { color: theme.fg }]}>{complaint.title}</Text>

            <View style={styles.metaRow}>
              <View style={styles.metaItem}>
                <Icons.building size={14} color={theme.fgMuted} />
                <Text style={[styles.metaText, { color: theme.fgMuted }]}>
                  {complaint.department?.name || 'Municipal Services'}
                </Text>
              </View>
              <View style={styles.metaItem}>
                <Icons.clock size={14} color={theme.fgMuted} />
                <Text style={[styles.metaText, { color: theme.fgMuted }]}>
                  {new Date(complaint.created_at).toLocaleDateString()}
                </Text>
              </View>
            </View>

            {/* AI Priority Breakdown Toggle */}
            <TouchableOpacity
              onPress={handleFetchPriority}
              style={[
                styles.priorityToggleBtn,
                { backgroundColor: theme.glassBg, borderColor: theme.glassBorder },
              ]}
            >
              <Text style={{ fontSize: 12, fontWeight: '600', color: theme.fg }}>
                {loadingPriority ? 'Calculating...' : showPriority ? '▲ Hide AI Priority Breakdown' : '⚡ View AI Priority Breakdown'}
              </Text>
            </TouchableOpacity>

            {/* Priority Breakdown Card */}
            {showPriority && priorityData && (
              <View style={[styles.priorityCard, { backgroundColor: theme.glassBgStrong, borderColor: theme.glassBorder }]}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: theme.fg }}>
                    AI Priority Score: {Math.round(priorityData.priority_score || 0)}/100
                  </Text>
                  <Chip tone="urgent">Active SLA</Chip>
                </View>
                <View style={{ marginTop: 8, gap: 4 }}>
                  <Text style={{ fontSize: 12, color: theme.fgMuted }}>
                    • Urgency: <Text style={{ color: theme.fg }}>{priorityData.components?.urgency || 'High'}</Text>
                  </Text>
                  <Text style={{ fontSize: 12, color: theme.fgMuted }}>
                    • Severity: <Text style={{ color: theme.fg }}>{priorityData.components?.severity || 'Standard'}</Text>
                  </Text>
                  <Text style={{ fontSize: 12, color: theme.fgMuted }}>
                    • Community Crowd Impact: <Text style={{ color: theme.fg }}>{priorityData.components?.crowd_impact || 'Moderate'}</Text>
                  </Text>
                  <Text style={{ fontSize: 12, color: theme.fgMuted }}>
                    • Target SLA: <Text style={{ color: theme.fg }}>{priorityData.sla_target_hours || 48} hours</Text>
                  </Text>
                </View>
              </View>
            )}
          </GlassCard>

          {/* Citizen Edit Button (SUBMITTED status only) */}
          {canEdit && (
            <TouchableOpacity
              onPress={() => setActionModal('edit')}
              style={[
                styles.editBtn,
                { backgroundColor: theme.glassBg, borderColor: theme.glassBorder },
              ]}
            >
              <Icons.edit size={16} color={theme.fg} />
              <Text style={{ fontSize: 13, fontWeight: '600', color: theme.fg }}>
                Edit Complaint (SUBMITTED stage)
              </Text>
            </TouchableOpacity>
          )}

          {/* Description */}
          <Text style={[styles.sectionHeading, { color: theme.fgMuted, marginTop: 22 }]}>
            Complaint description
          </Text>
          <GlassCard padding={16} radius={Radius.lg}>
            <Text style={{ fontSize: 14, color: theme.fg, lineHeight: 22 }}>
              {complaint.description}
            </Text>
          </GlassCard>

          {/* Location */}
          <Text style={[styles.sectionHeading, { color: theme.fgMuted, marginTop: 18 }]}>
            Location
          </Text>
          <GlassCard padding={16} radius={Radius.lg}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Icons.pin size={20} color={theme.fg} />
              <Text style={{ fontSize: 14, color: theme.fg, flex: 1 }}>
                {complaint.address || 'Location coordinates recorded'}
              </Text>
            </View>
          </GlassCard>

          {/* Images Gallery */}
          {complaint.images && complaint.images.length > 0 && (
            <>
              <Text style={[styles.sectionHeading, { color: theme.fgMuted, marginTop: 18 }]}>
                Evidence & Progress Photos
              </Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
                {complaint.images.map((img: any, idx: number) => (
                  <View key={img.id || idx} style={styles.imageThumbnailWrap}>
                    <Image source={{ uri: img.url }} style={styles.imageThumbnail} />
                    {isOwner && (
                      <TouchableOpacity
                        onPress={() => handleDeleteImage(img.id)}
                        style={styles.imageDeleteBtn}
                      >
                        <Icons.trash size={12} color="#FFF" />
                      </TouchableOpacity>
                    )}
                  </View>
                ))}
              </View>
            </>
          )}

          {/* Staff Workflow Actions */}
          {isStaffOrAdmin && (
            <View style={{ marginTop: 24 }}>
              <Text style={[styles.sectionHeading, { color: theme.fgMuted }]}>
                Municipal Authority Actions
              </Text>
              <View style={{ flexDirection: 'row', gap: 10, marginTop: 6 }}>
                <TouchableOpacity
                  onPress={() => setActionModal('status')}
                  style={[styles.workflowBtn, { backgroundColor: theme.glassBg, borderColor: theme.glassBorder }]}
                >
                  <Text style={{ fontSize: 12, fontWeight: '600', color: theme.fg }}>Update Status</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  onPress={() => setActionModal('note')}
                  style={[styles.workflowBtn, { backgroundColor: theme.glassBg, borderColor: theme.glassBorder }]}
                >
                  <Text style={{ fontSize: 12, fontWeight: '600', color: theme.fg }}>+ Add Note</Text>
                </TouchableOpacity>

                {complaint.status !== 'COMPLETED' && (
                  <TouchableOpacity
                    onPress={() => setActionModal('complete')}
                    style={[styles.workflowBtn, { backgroundColor: '#2FBF71' }]}
                  >
                    <Text style={{ fontSize: 12, fontWeight: '600', color: '#FFF' }}>Mark Complete</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          )}

          {/* Action Modals */}
          {actionModal && (
            <GlassCard strong padding={18} radius={Radius.xl} style={{ marginTop: 16 }}>
              {actionModal === 'status' && (
                <>
                  <Text style={{ fontSize: 16, fontWeight: '700', color: theme.fg }}>Transition Status</Text>
                  <View style={{ flexDirection: 'row', gap: 6, marginVertical: 10, flexWrap: 'wrap' }}>
                    {['ONGOING', 'PROCESSING', 'ON_HOLD', 'RESOLVED', 'REJECTED'].map((st) => (
                      <TouchableOpacity
                        key={st}
                        onPress={() => setSelectedStatus(st)}
                        style={[
                          styles.statusSelectChip,
                          {
                            backgroundColor: selectedStatus === st ? theme.ctaBg : theme.glassBg,
                            borderColor: theme.glassBorder,
                          },
                        ]}
                      >
                        <Text style={{ fontSize: 11, fontWeight: '600', color: selectedStatus === st ? theme.ctaFg : theme.fg }}>
                          {st}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                  <TextInput
                    placeholder="Enter reason for status change (required)..."
                    placeholderTextColor={theme.fgMuted}
                    value={actionReason}
                    onChangeText={setActionReason}
                    style={[styles.modalInput, { color: theme.fg, borderColor: theme.glassBorder }]}
                  />
                  {actionMessage && <Text style={{ color: '#FF4D4F', fontSize: 12, marginTop: 6 }}>{actionMessage}</Text>}
                  <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
                    <TouchableOpacity onPress={() => setActionModal(null)} style={styles.cancelBtn}>
                      <Text style={{ color: theme.fgMuted, fontWeight: '600', fontSize: 13 }}>Cancel</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={handleUpdateStatus} disabled={actionLoading} style={[styles.confirmBtn, { backgroundColor: theme.ctaBg }]}>
                      <Text style={{ color: theme.ctaFg, fontWeight: '600', fontSize: 13 }}>
                        {actionLoading ? 'Updating...' : 'Confirm Status'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                </>
              )}

              {actionModal === 'note' && (
                <>
                  <Text style={{ fontSize: 16, fontWeight: '700', color: theme.fg }}>Add Progress Note</Text>
                  <TextInput
                    placeholder="Describe progress update for citizen..."
                    placeholderTextColor={theme.fgMuted}
                    value={progressNote}
                    onChangeText={setProgressNote}
                    multiline
                    style={[styles.modalInput, { minHeight: 60, color: theme.fg, borderColor: theme.glassBorder, marginTop: 10 }]}
                  />
                  {actionMessage && <Text style={{ color: '#FF4D4F', fontSize: 12, marginTop: 6 }}>{actionMessage}</Text>}
                  <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
                    <TouchableOpacity onPress={() => setActionModal(null)} style={styles.cancelBtn}>
                      <Text style={{ color: theme.fgMuted, fontWeight: '600', fontSize: 13 }}>Cancel</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={handleAddProgressNote} disabled={actionLoading} style={[styles.confirmBtn, { backgroundColor: theme.ctaBg }]}>
                      <Text style={{ color: theme.ctaFg, fontWeight: '600', fontSize: 13 }}>
                        {actionLoading ? 'Posting...' : 'Post Progress Note'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                </>
              )}

              {actionModal === 'complete' && (
                <>
                  <Text style={{ fontSize: 16, fontWeight: '700', color: theme.fg }}>Mark as Resolved & Complete</Text>
                  <TextInput
                    placeholder="Enter resolution notes and summary..."
                    placeholderTextColor={theme.fgMuted}
                    value={completionSummary}
                    onChangeText={setCompletionSummary}
                    multiline
                    style={[styles.modalInput, { minHeight: 60, color: theme.fg, borderColor: theme.glassBorder, marginTop: 10 }]}
                  />
                  {actionMessage && <Text style={{ color: '#FF4D4F', fontSize: 12, marginTop: 6 }}>{actionMessage}</Text>}
                  <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
                    <TouchableOpacity onPress={() => setActionModal(null)} style={styles.cancelBtn}>
                      <Text style={{ color: theme.fgMuted, fontWeight: '600', fontSize: 13 }}>Cancel</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={handleMarkComplete} disabled={actionLoading} style={[styles.confirmBtn, { backgroundColor: '#2FBF71' }]}>
                      <Text style={{ color: '#FFF', fontWeight: '600', fontSize: 13 }}>
                        {actionLoading ? 'Completing...' : 'Mark Complete'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                </>
              )}

              {actionModal === 'edit' && (
                <>
                  <Text style={{ fontSize: 16, fontWeight: '700', color: theme.fg }}>Edit Complaint</Text>
                  <TextInput
                    placeholder="Title"
                    placeholderTextColor={theme.fgMuted}
                    value={editTitle}
                    onChangeText={setEditTitle}
                    style={[styles.modalInput, { color: theme.fg, borderColor: theme.glassBorder, marginTop: 10 }]}
                  />
                  <TextInput
                    placeholder="Description"
                    placeholderTextColor={theme.fgMuted}
                    value={editDesc}
                    onChangeText={setEditDesc}
                    multiline
                    style={[styles.modalInput, { minHeight: 70, color: theme.fg, borderColor: theme.glassBorder, marginTop: 8 }]}
                  />
                  {actionMessage && <Text style={{ color: '#FF4D4F', fontSize: 12, marginTop: 6 }}>{actionMessage}</Text>}
                  <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
                    <TouchableOpacity onPress={() => setActionModal(null)} style={styles.cancelBtn}>
                      <Text style={{ color: theme.fgMuted, fontWeight: '600', fontSize: 13 }}>Cancel</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={handleEditComplaint} disabled={actionLoading} style={[styles.confirmBtn, { backgroundColor: theme.ctaBg }]}>
                      <Text style={{ color: theme.ctaFg, fontWeight: '600', fontSize: 13 }}>
                        {actionLoading ? 'Saving...' : 'Save Changes'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                </>
              )}
            </GlassCard>
          )}

          {/* Timeline & Updates */}
          <Text style={[styles.sectionHeading, { color: theme.fgMuted, marginTop: 24 }]}>
            Official Lifecycle Timeline ({updates.length} updates)
          </Text>
          <GlassCard padding={16} radius={Radius.xl}>
            <View style={{ gap: 16 }}>
              {/* Submission node */}
              <View style={{ flexDirection: 'row', gap: 12 }}>
                <View style={[styles.timelineDot, { backgroundColor: '#2FBF71' }]} />
                <View style={{ flex: 1 }}>
                  <Text style={{ fontSize: 14, fontWeight: '600', color: theme.fg }}>
                    Complaint Registered
                  </Text>
                  <Text style={{ fontSize: 12, color: theme.fgMuted, marginTop: 2 }}>
                    {new Date(complaint.created_at).toLocaleString()}
                  </Text>
                </View>
              </View>

              {/* Progress updates */}
              {updates.map((upd, idx) => (
                <View key={upd.id || idx} style={{ flexDirection: 'row', gap: 12 }}>
                  <View style={[styles.timelineDot, { backgroundColor: '#3B82F6' }]} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 14, fontWeight: '600', color: theme.fg }}>
                      {upd.title || upd.update_type || 'Progress Update'}
                    </Text>
                    <Text style={{ fontSize: 13, color: theme.fg, marginTop: 2 }}>
                      {upd.message || upd.description}
                    </Text>
                    <Text style={{ fontSize: 11, color: theme.fgMuted, marginTop: 4 }}>
                      {upd.created_at ? new Date(upd.created_at).toLocaleString() : ''}
                    </Text>
                  </View>
                </View>
              ))}
            </View>
          </GlassCard>
        </ScrollView>
      ) : (
        <View style={styles.centerLoading}>
          <Text style={{ color: theme.fgMuted }}>Complaint not found</Text>
        </View>
      )}
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
  headerTitle: { fontSize: 17, fontWeight: '600', fontFamily: 'monospace' },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 110,
  },
  chipRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  complaintTitle: { fontSize: 22, fontWeight: '700', letterSpacing: -0.4, lineHeight: 28 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 16, marginTop: 14 },
  metaItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  metaText: { fontSize: 12, fontWeight: '500' },
  priorityToggleBtn: {
    marginTop: 14,
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    alignItems: 'center',
  },
  priorityCard: {
    marginTop: 10,
    padding: 12,
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
  },
  editBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 10,
    padding: 10,
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    justifyContent: 'center',
  },
  workflowBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: StyleSheet.hairlineWidth,
    alignItems: 'center',
  },
  sectionHeading: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 8,
  },
  timelineDot: { width: 10, height: 10, borderRadius: 5, marginTop: 4 },
  centerLoading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  imageThumbnailWrap: { position: 'relative', width: 72, height: 72, borderRadius: 8, overflow: 'hidden' },
  imageThumbnail: { width: '100%', height: '100%' },
  imageDeleteBtn: {
    position: 'absolute',
    top: 2,
    right: 2,
    backgroundColor: 'rgba(239, 68, 68, 0.85)',
    borderRadius: 10,
    width: 20,
    height: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalInput: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    fontSize: 13,
  },
  statusSelectChip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
    borderWidth: StyleSheet.hairlineWidth,
  },
  cancelBtn: { flex: 1, paddingVertical: 10, alignItems: 'center' },
  confirmBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, alignItems: 'center' },
});
