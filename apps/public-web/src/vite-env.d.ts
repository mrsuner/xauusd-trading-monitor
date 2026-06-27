/// <reference types="vite/client" />

interface Window {
  __TICKBASE_NEWS_CONFIG__?: {
    PUBLIC_API_BASE_URL?: string;
    PUBLIC_SUPPORTED_LANGUAGES?: string | string[];
    PUBLIC_DEFAULT_LANGUAGE?: string;
    PUBLIC_GA_MEASUREMENT_ID?: string;
  };
}
