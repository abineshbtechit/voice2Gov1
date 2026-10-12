import { ApiClient } from './client';

export interface CreateComplaintPayload {
  title: string;
  description: string;
  category_id: string;
  location: {
    type: 'Point';
    coordinates: [number, number]; // [lng, lat]
  };
  address: string;
}

export const ComplaintsApi = {
  create: (payload: CreateComplaintPayload) =>
    ApiClient.post('/complaints', payload),

  getMy: (page = 1, pageSize = 20, status?: string) => {
    let url = `/complaints/my?page=${page}&page_size=${pageSize}`;
    if (status) url += `&status=${status}`;
    return ApiClient.get(url);
  },

  getById: (id: string) =>
    ApiClient.get(`/complaints/${id}`),

  update: (id: string, payload: Partial<CreateComplaintPayload>) =>
    ApiClient.put(`/complaints/${id}`, payload),

  delete: (id: string) =>
    ApiClient.delete(`/complaints/${id}`),

  getImages: (id: string) =>
    ApiClient.get(`/complaints/${id}/images`),

  deleteImage: (id: string, imageId: string) =>
    ApiClient.delete(`/complaints/${id}/images/${imageId}`),

  getPriorityBreakdown: (id: string) =>
    ApiClient.get(`/complaints/${id}/priority`),

  getUpdates: (id: string) =>
    ApiClient.get(`/complaints/${id}/updates`),

  addUpdate: (id: string, message: string, images?: string[]) =>
    ApiClient.post(`/complaints/${id}/updates`, { message, images }),

  updateStatus: (id: string, status: string, reason?: string) =>
    ApiClient.patch(`/complaints/${id}/status`, { status, reason }),

  markComplete: (id: string, completionSummary: string, images?: string[]) =>
    ApiClient.patch(`/complaints/${id}/complete`, {
      completion_summary: completionSummary,
      images,
    }),

  assignStaff: (id: string, assignedToId: string) =>
    ApiClient.patch(`/complaints/${id}/assign`, { assigned_to: assignedToId }),
};

