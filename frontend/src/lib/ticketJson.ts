import type { JiraComment, JiraUser, LinkedIssue, Ticket } from "../types/ticket";

type UnknownRecord = Record<string, unknown>;

const KEY_ALIASES: Record<string, string[]> = {
  issue_id: ["issue_id", "Issue ID", "Issue Id", "id"],
  issue_key: ["issue_key", "Issue Key", "key"],
  work_type: ["work_type", "Work type", "Work Type"],
  request_type: ["request_type", "Request type", "Request Type"],
  summary: ["summary", "Summary"],
  description: ["description", "Description"],
  affected_business_or_it_services: ["affected_business_or_it_services", "Affected Business or IT Services", "Affected Business Or IT Services"],
  business_entity: ["business_entity", "Business Entity"],
  business_critical_for_entity: ["business_critical_for_entity", "Business Critical for Entity"],
  service_teams: ["service_teams", "Service Team(s)", "Service Teams"],
  reporter: ["reporter", "Reporter"],
  assignee: ["assignee", "Assignee"],
  priority: ["priority", "Priority"],
  urgency: ["urgency", "Urgency"],
  impact: ["impact", "Impact"],
  severity: ["severity", "Severity"],
  created_date: ["created_date", "Created date", "Created Date"],
  status: ["status", "Status"],
  linked_issues: ["linked_issues", "Linked issues", "Linked Issues"],
  resolution: ["resolution", "Resolution"],
  due_date: ["due_date", "Due date", "Due Date"],
  all_comments: ["all_comments", "All Comments", "All comments"],
};

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function pick(record: UnknownRecord, aliases: string[]): unknown {
  for (const key of aliases) {
    if (key in record) return record[key];
  }
  return undefined;
}

function scalar(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    if (value.length === 0) return null;
    const joined = value.map((item) => scalar(item)).filter(Boolean).join(", ");
    return joined || null;
  }
  if (isRecord(value)) {
    const candidate = value.display_name ?? value.name ?? value.value ?? value.key ?? value.id;
    return scalar(candidate);
  }
  return null;
}

function stringArray(value: unknown): string[] {
  if (value === null || value === undefined) return [];
  if (Array.isArray(value)) return value.map((item) => scalar(item)).filter((item): item is string => Boolean(item));
  const one = scalar(value);
  return one ? [one] : [];
}

function nullableBoolean(value: unknown): boolean | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "boolean") return value;
  if (Array.isArray(value) && value.length === 0) return null;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["true", "yes", "1"].includes(normalized)) return true;
    if (["false", "no", "0"].includes(normalized)) return false;
  }
  return null;
}

function user(value: unknown): JiraUser | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "string") return { id: value, display_name: value };
  if (isRecord(value)) {
    const id = scalar(value.id ?? value.account_id ?? value.key ?? value.name) ?? "UNKNOWN";
    const displayName = scalar(value.display_name ?? value.displayName ?? value.name ?? value.id) ?? id;
    return { id, display_name: displayName };
  }
  return null;
}

function linkedIssues(value: unknown): LinkedIssue[] {
  if (!Array.isArray(value)) return [];
  return value.map((item, index) => {
    if (typeof item === "string") {
      return { relation: "related to", issue_key: item, summary: "Linked issue", status: null };
    }
    if (isRecord(item)) {
      return {
        relation: scalar(item.relation ?? item.type ?? item.relationship) ?? "related to",
        issue_key: scalar(item.issue_key ?? item.key ?? item.issueKey ?? item.id) ?? `LINK-${index + 1}`,
        summary: scalar(item.summary ?? item.title) ?? "Linked issue",
        status: scalar(item.status),
      };
    }
    return { relation: "related to", issue_key: `LINK-${index + 1}`, summary: "Linked issue", status: null };
  });
}

function inferSemanticRole(body: string): JiraComment["semantic_role"] {
  const text = body.toLowerCase();
  if (/still|continues|failed|not resolved|doesn't work|does not work/.test(text)) return "result";
  if (/unlocked|reset|verified|checked|updated|restarted|assigned/.test(text)) return "action";
  return "comment";
}

function comments(value: unknown, ticketKey: string): JiraComment[] {
  if (!Array.isArray(value)) return [];
  return value.map((item, index) => {
    if (typeof item === "string") {
      const split = item.match(/^([^:]{1,80}):\s*(.*)$/s);
      const authorName = split?.[1]?.trim() || "Unknown author";
      const body = split?.[2]?.trim() || item;
      return {
        id: `${ticketKey}-comment-${index + 1}`,
        author: { id: authorName, display_name: authorName },
        body,
        created_at: "",
        visibility: null,
        semantic_role: inferSemanticRole(body),
      };
    }
    if (isRecord(item)) {
      const author = user(item.author ?? item.reporter ?? item.user) ?? { id: "UNKNOWN", display_name: "Unknown author" };
      const body = scalar(item.body ?? item.comment ?? item.text) ?? "";
      const visibilityRaw = scalar(item.visibility);
      return {
        id: scalar(item.id) ?? `${ticketKey}-comment-${index + 1}`,
        author,
        body,
        created_at: scalar(item.created_at ?? item.created ?? item.date) ?? "",
        visibility: visibilityRaw === "public" || visibilityRaw === "internal" ? visibilityRaw : null,
        semantic_role: (scalar(item.semantic_role) as JiraComment["semantic_role"]) ?? inferSemanticRole(body),
      };
    }
    return {
      id: `${ticketKey}-comment-${index + 1}`,
      author: { id: "UNKNOWN", display_name: "Unknown author" },
      body: String(item),
      created_at: "",
      visibility: null,
      semantic_role: "comment",
    };
  });
}

function normalizeTicket(record: UnknownRecord, index: number): Ticket {
  const get = (key: keyof typeof KEY_ALIASES) => pick(record, KEY_ALIASES[key]!);
  const issueKey = scalar(get("issue_key")) ?? `TICKET-${index + 1}`;
  const issueId = scalar(get("issue_id")) ?? issueKey;
  const summary = scalar(get("summary")) ?? "Untitled ticket";
  const created = scalar(get("created_date")) ?? "";
  const status = scalar(get("status")) ?? "Not recorded";

  return {
    issue_id: issueId,
    issue_key: issueKey,
    work_type: scalar(get("work_type")),
    request_type: scalar(get("request_type")),
    summary,
    description: scalar(get("description")),
    affected_business_or_it_services: stringArray(get("affected_business_or_it_services")),
    business_entity: scalar(get("business_entity")),
    business_critical_for_entity: nullableBoolean(get("business_critical_for_entity")),
    service_teams: stringArray(get("service_teams")),
    reporter: user(get("reporter")),
    assignee: user(get("assignee")),
    priority: scalar(get("priority")),
    urgency: scalar(get("urgency")),
    impact: scalar(get("impact")),
    severity: scalar(get("severity")),
    created_date: created,
    status,
    linked_issues: linkedIssues(get("linked_issues")),
    resolution: scalar(get("resolution")),
    due_date: scalar(get("due_date")),
    all_comments: comments(get("all_comments"), issueKey),
    raw: record,
  };
}

function looksLikeTicket(record: UnknownRecord): boolean {
  return Boolean(
    pick(record, KEY_ALIASES.issue_key!) ||
      pick(record, KEY_ALIASES.issue_id!) ||
      pick(record, KEY_ALIASES.summary!) ||
      pick(record, KEY_ALIASES.description!),
  );
}

export function extractTicketRecords(payload: unknown): UnknownRecord[] {
  if (Array.isArray(payload)) return payload.filter(isRecord);
  if (!isRecord(payload)) return [];
  if (looksLikeTicket(payload)) return [payload];

  for (const key of ["tickets", "issues", "data", "items", "results"]) {
    const candidate = payload[key];
    if (Array.isArray(candidate)) return candidate.filter(isRecord);
    if (isRecord(candidate) && looksLikeTicket(candidate)) return [candidate];
  }

  const nestedArrays = Object.values(payload).find((value) => Array.isArray(value) && value.some(isRecord));
  if (Array.isArray(nestedArrays)) return nestedArrays.filter(isRecord);
  return [];
}

export function parseTicketJson(payload: unknown): Ticket[] {
  return extractTicketRecords(payload).map(normalizeTicket);
}
