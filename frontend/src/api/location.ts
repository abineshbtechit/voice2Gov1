import { ApiClient } from './client';

export const LocationApi = {
  reverseGeocode: (lat: number, lng: number) =>
    ApiClient.get(`/location/reverse?lat=${lat}&lng=${lng}`),
};

