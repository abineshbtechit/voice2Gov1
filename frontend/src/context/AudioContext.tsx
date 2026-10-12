import React, { createContext, useContext, useState, useRef, useEffect } from 'react';
import { Platform } from 'react-native';

interface AudioContextProps {
  isRecording: boolean;
  recordingSeconds: number;
  liveAudioLevel: number;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<{ duration: number }>;
  pauseRecording: () => void;
  resumeRecording: () => void;
}

const AudioContext = createContext<AudioContextProps>({
  isRecording: false,
  recordingSeconds: 0,
  liveAudioLevel: 0,
  startRecording: async () => {},
  stopRecording: async () => ({ duration: 0 }),
  pauseRecording: () => {},
  resumeRecording: () => {},
});

export const AudioProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [liveAudioLevel, setLiveAudioLevel] = useState(0.4);

  const timerRef = useRef<any>(null);
  const mediaRecorderRef = useRef<any>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const startRecording = async () => {
    setIsRecording(true);
    setRecordingSeconds(0);

    if (Platform.OS === 'web' && typeof navigator !== 'undefined' && navigator.mediaDevices) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // @ts-ignore
        mediaRecorderRef.current = new window.MediaRecorder(stream);
        mediaRecorderRef.current.start();
      } catch (e) {
        console.warn('Microphone permission or API not available on web:', e);
      }
    }

    timerRef.current = setInterval(() => {
      setRecordingSeconds((prev) => prev + 1);
      // Simulate natural microphone amplitude fluctuation
      setLiveAudioLevel(0.3 + Math.random() * 0.6);
    }, 1000);
  };

  const stopRecording = async () => {
    setIsRecording(false);
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (Platform.OS === 'web' && mediaRecorderRef.current) {
      try {
        mediaRecorderRef.current.stop();
      } catch {}
    }

    const duration = recordingSeconds;
    return { duration };
  };

  const pauseRecording = () => {
    setIsRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);
  };

  const resumeRecording = () => {
    setIsRecording(true);
    timerRef.current = setInterval(() => {
      setRecordingSeconds((prev) => prev + 1);
      setLiveAudioLevel(0.3 + Math.random() * 0.6);
    }, 1000);
  };

  return (
    <AudioContext.Provider
      value={{
        isRecording,
        recordingSeconds,
        liveAudioLevel,
        startRecording,
        stopRecording,
        pauseRecording,
        resumeRecording,
      }}
    >
      {children}
    </AudioContext.Provider>
  );
};

export const useAudio = () => useContext(AudioContext);

