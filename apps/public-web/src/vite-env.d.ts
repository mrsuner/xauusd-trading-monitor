/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PUBLIC_SUPPORTED_LANGUAGES?: string;
  readonly VITE_PUBLIC_DEFAULT_LANGUAGE?: string;
  readonly VITE_PUBLIC_SUPPORT_URLS?: string;
  readonly VITE_ACCOUNT_API_BASE_URL?: string;
  readonly VITE_ACCOUNT_DASHBOARD_URL?: string;
  readonly VITE_FIREBASE_API_KEY?: string;
  readonly VITE_FIREBASE_AUTH_DOMAIN?: string;
  readonly VITE_FIREBASE_PROJECT_ID?: string;
  readonly VITE_FIREBASE_MESSAGING_SENDER_ID?: string;
  readonly VITE_FIREBASE_APP_ID?: string;
  readonly VITE_FIREBASE_VAPID_KEY?: string;
}

interface Window {
  __TICKBASE_NEWS_CONFIG__?: {
    PUBLIC_API_BASE_URL?: string;
    PUBLIC_SUPPORTED_LANGUAGES?: string | string[];
    PUBLIC_DEFAULT_LANGUAGE?: string;
    PUBLIC_SUPPORT_URLS?: string;
    PUBLIC_GA_MEASUREMENT_ID?: string;
    ACCOUNT_API_BASE_URL?: string;
    ACCOUNT_DASHBOARD_URL?: string;
    FIREBASE_API_KEY?: string;
    FIREBASE_AUTH_DOMAIN?: string;
    FIREBASE_PROJECT_ID?: string;
    FIREBASE_MESSAGING_SENDER_ID?: string;
    FIREBASE_APP_ID?: string;
    FIREBASE_VAPID_KEY?: string;
  };
}
