import { lazy } from "react";
import { Navigate, type RouteObject } from "react-router-dom";

/** One lazy chunk per page. Vite can only split these if the import() argument
 *  is a static literal — a computed path silently bundles everything. */
const MyLeavePage = lazy(() => import("./pages/MyLeavePage"));
const ApplyLeavePage = lazy(() => import("./pages/ApplyLeavePage"));
const BalancesPage = lazy(() => import("./pages/BalancesPage"));
const ApprovalsPage = lazy(() => import("./pages/ApprovalsPage"));
const RecordsPage = lazy(() => import("./pages/RecordsPage"));
const CalendarPage = lazy(() => import("./pages/CalendarPage"));
const PolicyPage = lazy(() => import("./pages/PolicyPage"));
const SlaPage = lazy(() => import("./pages/SlaPage"));

/** Paths are RELATIVE — the shell mounts them under the manifest's basePath.
 *
 *  Every entry here has a matching nav item in the server's registry.py, and
 *  that correspondence matters: the sidebar is built server-side, so a nav item
 *  without a route here renders a link that goes nowhere. */
export const routes: RouteObject[] = [
  { index: true, element: <Navigate to="mine" replace /> },
  { path: "mine", element: <MyLeavePage /> },
  { path: "apply", element: <ApplyLeavePage /> },
  { path: "balances", element: <BalancesPage /> },
  { path: "approvals", element: <ApprovalsPage /> },
  { path: "records", element: <RecordsPage /> },
  { path: "calendar", element: <CalendarPage /> },
  { path: "policy", element: <PolicyPage /> },
  { path: "sla", element: <SlaPage /> },
];
