import type { Ticket } from "../types/ticket";

export const mockTickets: Ticket[] = [
  {
    id: "INC-1024",
    title: "Portfolio Reporting access issue",
    description:
      "I can authenticate but receive HTTP 403 when opening Portfolio Reporting.",
    created_at: "2026-09-09T08:42:00+02:00",
    requester_id: "USR-3017",
    department: "Asset Management",
    service: "Portfolio Reporting",
    status: "new",
  },
  {
    id: "INC-1025",
    title: "Corporate VPN unavailable",
    description:
      "I cannot connect to the corporate VPN since this morning. The client keeps timing out after sign-in.",
    created_at: "2026-09-09T09:18:00+02:00",
    requester_id: "USR-1845",
    department: "Finance",
    service: "VPN",
    status: "new",
  },
  {
    id: "REQ-1026",
    title: "Software installation request",
    description:
      "Please install approved PDF software on my workstation for a client documentation review.",
    created_at: "2026-09-09T10:03:00+02:00",
    requester_id: "USR-2280",
    department: "Operations",
    service: "Workplace",
    status: "new",
  },
  {
    id: "INC-1027",
    title: "Password reset loop",
    description:
      "My password reset completes successfully, but the identity portal asks me to reset it again on the next login.",
    created_at: "2026-09-09T10:37:00+02:00",
    requester_id: "USR-4142",
    department: "Group Functions",
    service: "Identity",
    status: "in_progress",
  },
];
