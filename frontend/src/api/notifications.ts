import { ApiClient } from './client';

export const NotificationsApi = {
  getList: (page = 1, pageSize = 30, isRead?: boolean) => {
    let url = `/notifications?page=${page}&page_size=${pageSize}`;
    if (isRead !== undefined) url += `&is_read=${isRead}`;
    return ApiClient.get(url);
  },

  getUnreadCount: () =>
    ApiClient.get('/notifications/unread-count'),

  markRead: (id: string) =>
    ApiClient.patch(`/notifications/${id}/read`),

  markAllRead: () =>
    ApiClient.patch('/notifications/read-all'),

  registerDeviceToken: (token: string, platform = 'web') =>
    ApiClient.post('/notifications/devices', { token, platform }),
};

