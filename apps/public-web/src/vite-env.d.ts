/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PUBLIC_SUPPORTED_LANGUAGES?: string;
  readonly VITE_PUBLIC_DEFAULT_LANGUAGE?: string;
}

interface Window {
  __TICKBASE_NEWS_CONFIG__?: {
    PUBLIC_API_BASE_URL?: string;
    PUBLIC_SUPPORTED_LANGUAGES?: string | string[];
    PUBLIC_DEFAULT_LANGUAGE?: string;
    PUBLIC_GA_MEASUREMENT_ID?: string;
  };
}
