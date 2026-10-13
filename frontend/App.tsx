import React, { useState, useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { ThemeProvider, useAppTheme } from './src/context/ThemeContext';
import { AuthProvider, useAuth } from './src/context/AuthContext';

// Screens
import { SplashScreen } from './src/screens/foundation/SplashScreen';
import { OnboardingScreen } from './src/screens/foundation/OnboardingScreen';
import { AuthWelcomeScreen } from './src/screens/auth/AuthWelcomeScreen';
import { LoginScreen } from './src/screens/auth/LoginScreen';
import { RegisterScreen } from './src/screens/auth/RegisterScreen';
import { OTPVerificationScreen } from './src/screens/auth/OTPVerificationScreen';
import { HomeScreen } from './src/screens/home/HomeScreen';
import { VoiceComplaintScreen } from './src/screens/voice/VoiceComplaintScreen';
import { AIProcessingScreen } from './src/screens/voice/AIProcessingScreen';
import { ComplaintReviewScreen } from './src/screens/voice/ComplaintReviewScreen';
import { TextComplaintScreen } from './src/screens/voice/TextComplaintScreen';
import { ComplaintSubmittedScreen } from './src/screens/voice/ComplaintSubmittedScreen';
import { ComplaintListScreen } from './src/screens/complaints/ComplaintListScreen';
import { ComplaintDetailsScreen } from './src/screens/complaints/ComplaintDetailsScreen';
import { CommunityFeedScreen } from './src/screens/complaints/CommunityFeedScreen';
import { NotificationsScreen } from './src/screens/utility/NotificationsScreen';
import { SearchScreen } from './src/screens/utility/SearchScreen';
import { CategoriesScreen } from './src/screens/utility/CategoriesScreen';
import { ProfileScreen } from './src/screens/utility/ProfileScreen';
import { OrgDashboardScreen } from './src/screens/org/OrgDashboardScreen';
import { AdminDashboardScreen } from './src/screens/admin/AdminDashboardScreen';
import { AdminUsersScreen } from './src/screens/admin/AdminUsersScreen';
import { StateScreen } from './src/screens/states/StateScreen';

// Navigation Components
import { BottomNav, TabKey } from './src/components/common/BottomNav';

type AppScreen =
  | 'splash'
  | 'onboarding'
  | 'welcome'
  | 'login'
  | 'register'
  | 'otp_verification'
  | 'home'
  | 'voice_record'
  | 'text_complaint'
  | 'ai_processing'
  | 'complaint_review'
  | 'complaint_submitted'
  | 'complaints'
  | 'complaint_detail'
  | 'feed'
  | 'search'
  | 'categories'
  | 'notifications'
  | 'profile'
  | 'org_dashboard'
  | 'admin_dashboard'
  | 'admin_users'
  | 'offline_state';

function MainApp() {
  const { theme, isDark } = useAppTheme();
  const { user, isAuthenticated } = useAuth();

  const [currentScreen, setCurrentScreen] = useState<AppScreen>(
    isAuthenticated ? 'home' : 'welcome'
  );
  const [submittedComplaint, setSubmittedComplaint] = useState<any>(null);
  const [selectedComplaintId, setSelectedComplaintId] = useState<string | null>(null);
  const [verificationData, setVerificationData] = useState<{
    identifier: string;
    email?: string;
    phone?: string;
    fullName?: string;
  } | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('home');

  // Sync auth state
  useEffect(() => {
    if (!isAuthenticated) {
      if (!['welcome', 'login', 'register', 'onboarding', 'otp_verification'].includes(currentScreen)) {
        setCurrentScreen('welcome');
      }
    }
  }, [isAuthenticated]);

  // Handle Tab Navigation
  const handleTabPress = (tab: TabKey) => {
    setActiveTab(tab);
    if (tab === 'home') setCurrentScreen('home');
    if (tab === 'complaints') setCurrentScreen('complaints');
    if (tab === 'voice') setCurrentScreen('voice_record');
    if (tab === 'notifications') setCurrentScreen('notifications');
    if (tab === 'feed') setCurrentScreen('feed');
  };

  return (
    <View style={[styles.root, { backgroundColor: theme.bg }]}>
      <StatusBar style={isDark ? 'light' : 'dark'} />

      {/* Screen Router */}
      <View style={styles.screenContainer}>
        {/* Auth Screens */}
        {currentScreen === 'welcome' && (
          <AuthWelcomeScreen
            onStartRegister={() => setCurrentScreen('register')}
            onStartLogin={() => setCurrentScreen('login')}
          />
        )}

        {currentScreen === 'login' && (
          <LoginScreen
            onBack={() => setCurrentScreen('welcome')}
            onSuccess={() => setCurrentScreen('home')}
            onNavigateToVerification={(data) => {
              setVerificationData(data);
              setCurrentScreen('otp_verification');
            }}
          />
        )}

        {currentScreen === 'register' && (
          <RegisterScreen
            onBack={() => setCurrentScreen('welcome')}
            onSuccess={() => setCurrentScreen('home')}
            onNavigateToVerification={(data) => {
              setVerificationData(data);
              setCurrentScreen('otp_verification');
            }}
          />
        )}

        {currentScreen === 'otp_verification' && (
          <OTPVerificationScreen
            identifier={verificationData?.identifier || ''}
            email={verificationData?.email}
            phone={verificationData?.phone}
            fullName={verificationData?.fullName}
            onBack={() => setCurrentScreen('welcome')}
            onSuccess={() => {
              setActiveTab('home');
              setCurrentScreen('home');
            }}
          />
        )}

        {currentScreen === 'onboarding' && (
          <OnboardingScreen onComplete={() => setCurrentScreen('welcome')} />
        )}
        {currentScreen === 'home' && (
          <HomeScreen
            onStartVoice={() => setCurrentScreen('voice_record')}
            onStartText={() => setCurrentScreen('text_complaint')}
            onViewComplaints={() => {
              setActiveTab('complaints');
              setCurrentScreen('complaints');
            }}
            onOpenNotifications={() => {
              setActiveTab('notifications');
              setCurrentScreen('notifications');
            }}
            onSelectComplaint={(id) => {
              setSelectedComplaintId(id);
              setCurrentScreen('complaint_detail');
            }}
            onOpenProfile={() => setCurrentScreen('profile')}
          />
        )}

        {currentScreen === 'voice_record' && (
          <VoiceComplaintScreen
            onCancel={() => {
              setActiveTab('home');
              setCurrentScreen('home');
            }}
            onProceedToAIReview={() => setCurrentScreen('ai_processing')}
          />
        )}

        {currentScreen === 'text_complaint' && (
          <TextComplaintScreen
            onBack={() => {
              setActiveTab('home');
              setCurrentScreen('home');
            }}
            onSubmitSuccess={(complaint) => {
              setSubmittedComplaint(complaint);
              setSelectedComplaintId(complaint.id);
              setCurrentScreen('complaint_submitted');
            }}
          />
        )}

        {currentScreen === 'ai_processing' && (
          <AIProcessingScreen
            onComplete={() => setCurrentScreen('complaint_review')}
          />
        )}

        {currentScreen === 'complaint_review' && (
          <ComplaintReviewScreen
            onBack={() => setCurrentScreen('home')}
            onSubmitSuccess={(complaint) => {
              setSubmittedComplaint(complaint);
              setSelectedComplaintId(complaint.id);
              setCurrentScreen('complaint_submitted');
            }}
          />
        )}

        {currentScreen === 'complaint_submitted' && (
          <ComplaintSubmittedScreen
            complaintId={submittedComplaint?.id || 'GRV-2841'}
            onTrackProgress={() => {
              setActiveTab('complaints');
              setCurrentScreen('complaint_detail');
            }}
            onReturnHome={() => {
              setActiveTab('home');
              setCurrentScreen('home');
            }}
          />
        )}

        {currentScreen === 'complaints' && (
          <ComplaintListScreen
            onSelectComplaint={(id) => {
              setSelectedComplaintId(id);
              setCurrentScreen('complaint_detail');
            }}
            onNewComplaint={() => setCurrentScreen('voice_record')}
          />
        )}

        {currentScreen === 'complaint_detail' && selectedComplaintId && (
          <ComplaintDetailsScreen
            complaintId={selectedComplaintId}
            onBack={() => {
              if (activeTab === 'feed') setCurrentScreen('feed');
              else if (activeTab === 'home') setCurrentScreen('home');
              else setCurrentScreen('complaints');
            }}
          />
        )}

        {currentScreen === 'feed' && (
          <CommunityFeedScreen
            onSelectComplaint={(id) => {
              setSelectedComplaintId(id);
              setCurrentScreen('complaint_detail');
            }}
          />
        )}

        {currentScreen === 'search' && (
          <SearchScreen
            onClose={() => setCurrentScreen('home')}
            onSelectComplaint={(id) => {
              setSelectedComplaintId(id);
              setCurrentScreen('complaint_detail');
            }}
            onVoiceSearch={() => setCurrentScreen('voice_record')}
          />
        )}

        {currentScreen === 'categories' && (
          <CategoriesScreen
            onBack={() => setCurrentScreen('home')}
            onSelectCategory={() => setCurrentScreen('text_complaint')}
          />
        )}

        {currentScreen === 'notifications' && (
          <NotificationsScreen
            onBack={() => {
              setActiveTab('home');
              setCurrentScreen('home');
            }}
            onSelectComplaint={(id) => {
              setSelectedComplaintId(id);
              setCurrentScreen('complaint_detail');
            }}
          />
        )}

        {currentScreen === 'profile' && (
          <ProfileScreen
            onBack={() => {
              setActiveTab('home');
              setCurrentScreen('home');
            }}
          />
        )}

        {currentScreen === 'org_dashboard' && (
          <OrgDashboardScreen
            onSelectComplaint={(id) => {
              setSelectedComplaintId(id);
              setCurrentScreen('complaint_detail');
            }}
          />
        )}

        {currentScreen === 'admin_dashboard' && (
          <AdminDashboardScreen
            onBack={() => setCurrentScreen('home')}
            onViewUsers={() => setCurrentScreen('admin_users')}
          />
        )}

        {currentScreen === 'admin_users' && (
          <AdminUsersScreen onBack={() => setCurrentScreen('admin_dashboard')} />
        )}
      </View>

      {/* Floating Bottom Nav shown on top-level tabs */}
      {['home', 'complaints', 'notifications', 'feed'].includes(currentScreen) && (
        <BottomNav
          activeTab={activeTab}
          onTabPress={handleTabPress}
          unreadCount={2}
        />
      )}
    </View>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <MainApp />
      </AuthProvider>
    </ThemeProvider>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  screenContainer: {
    flex: 1,
  },
});
