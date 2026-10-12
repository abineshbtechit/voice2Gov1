import { Platform } from 'react-native';

export class AudioRecorderBridge {
  private static isRecording = false;

  static async requestMicrophonePermission(): Promise<boolean> {
    if (Platform.OS === 'web') {
      try {
        if (typeof navigator !== 'undefined' && navigator.mediaDevices) {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          // Stop stream immediately after checking permission
          stream.getTracks().forEach((track) => track.stop());
          return true;
        }
      } catch {
        return false;
      }
    }
    return true;
  }

  static isCurrentlyRecording(): boolean {
    return this.isRecording;
  }

  static setRecordingState(state: boolean) {
    this.isRecording = state;
  }
}

