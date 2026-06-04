import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./styles.css";
import "./i18n";
import { Layout } from "./components/Layout";
import { Alerts } from "./pages/Alerts";
import { EventDetail } from "./pages/EventDetail";
import { Events } from "./pages/Events";
import { Overview } from "./pages/Overview";
import { Processing } from "./pages/Processing";
import { Sources } from "./pages/Sources";
import { Timeline } from "./pages/Timeline";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      retry: 1,
      refetchOnWindowFocus: false
    }
  }
});

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Overview /> },
      { path: "timeline", element: <Timeline /> },
      { path: "events", element: <Events /> },
      { path: "events/:eventId", element: <EventDetail /> },
      { path: "sources", element: <Sources /> },
      { path: "processing", element: <Processing /> },
      { path: "alerts", element: <Alerts /> }
    ]
  }
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
);
