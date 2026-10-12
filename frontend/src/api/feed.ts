import { ApiClient } from './client';

export interface FeedQuery {
  page?: number;
  pageSize?: number;
  sort?: 'recent' | 'popular' | 'priority' | 'nearby';
  status?: string;
  categoryId?: string;
  organizationId?: string;
  lat?: number;
  lng?: number;
  radiusKm?: number;
}

export const FeedApi = {
  getFeed: (query: FeedQuery = {}) => {
    const params = new URLSearchParams();
    if (query.page) params.append('page', String(query.page));
    if (query.pageSize) params.append('page_size', String(query.pageSize));
    if (query.sort) params.append('sort', query.sort);
    if (query.status) params.append('status', query.status);
    if (query.categoryId) params.append('category_id', query.categoryId);
    if (query.organizationId) params.append('organization_id', query.organizationId);
    if (query.lat !== undefined) params.append('lat', String(query.lat));
    if (query.lng !== undefined) params.append('lng', String(query.lng));
    if (query.radiusKm !== undefined) params.append('radius_km', String(query.radiusKm));

    return ApiClient.get(`/feed?${params.toString()}`);
  },

  like: (complaintId: string) =>
    ApiClient.post(`/complaints/${complaintId}/like`),

  unlike: (complaintId: string) =>
    ApiClient.delete(`/complaints/${complaintId}/like`),

  getLikeStatus: (complaintId: string) =>
    ApiClient.get(`/complaints/${complaintId}/like-status`),

  getLikes: (complaintId: string) =>
    ApiClient.get(`/complaints/${complaintId}/likes`),
};

