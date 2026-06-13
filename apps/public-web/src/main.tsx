import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { Navigate, createBrowserRouter, RouterProvider, useLocation, useParams } from "react-router-dom";
import "./styles.css";
import { Layout } from "./components/Layout";
import { defaultLanguage, isLanguage, localizedPath } from "./i18n";
import { AboutPage } from "./pages/AboutPage";
import { EventDetailPage } from "./pages/EventDetailPage";
import { EventsPage } from "./pages/EventsPage";
import { RawItemDetailPage } from "./pages/RawItemDetailPage";
import { RawItemsPage } from "./pages/RawItemsPage";
import { StatusPage } from "./pages/StatusPage";
import { TagPage } from "./pages/TagPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: 1,
      refetchOnWindowFocus: false
    }
  }
});

const router = createBrowserRouter([
  { path: "/", element: <Navigate to={localizedPath(defaultLanguage, "/events")} replace /> },
  { path: "/events", element: <LegacyRedirect /> },
  { path: "/events/:eventId", element: <LegacyRedirect /> },
  { path: "/raw", element: <LegacyRedirect /> },
  { path: "/raw/:rawItemId", element: <LegacyRedirect /> },
  { path: "/tags/:tag", element: <LegacyRedirect /> },
  { path: "/about", element: <LegacyRedirect /> },
  { path: "/status", element: <LegacyRedirect /> },
  {
    path: "/:lang",
    element: <LanguageLayout />,
    children: [
      { index: true, element: <Navigate to="events" replace /> },
      { path: "events", element: <EventsPage /> },
      { path: "events/:eventId", element: <EventDetailPage /> },
      { path: "raw", element: <RawItemsPage /> },
      { path: "raw/:rawItemId", element: <RawItemDetailPage /> },
      { path: "tags/:tag", element: <TagPage /> },
      { path: "about", element: <AboutPage /> },
      { path: "status", element: <StatusPage /> }
    ]
  }
]);

function LanguageLayout() {
  const { lang } = useParams();
  if (!isLanguage(lang)) {
    return <Navigate to={localizedPath(defaultLanguage, "/events")} replace />;
  }
  return <Layout />;
}

function LegacyRedirect() {
  const location = useLocation();
  return <Navigate to={localizedPath(defaultLanguage, location.pathname, location.search)} replace />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
);
