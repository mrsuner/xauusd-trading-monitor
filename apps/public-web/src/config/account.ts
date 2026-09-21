const runtimeConfig = window.__TICKBASE_NEWS_CONFIG__ ?? {};

export const accountDashboardUrl =
  runtimeConfig.ACCOUNT_DASHBOARD_URL || import.meta.env.VITE_ACCOUNT_DASHBOARD_URL || "";
