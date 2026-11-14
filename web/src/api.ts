export type Sentence = { text: string; uses: string[] };
export type Remark = { author: string; text: string; uses: string[]; to_agent: boolean };
export type Section = {
  id: string;
  title: string;
  kind: string;
  state: "draft" | "in_review" | "changes_requested" | "approved";
  version: string;
  sentences: Sentence[];
  comments: Remark[];
};
export type Place = { doc_id: string; locator: string | null };
export type Input = {
  label: string;
  text: string;
  flagged: boolean;
  attribute: string;
  citations: Place[];
};
export type Memo = {
  run: string;
  scenario: string;
  as_of: string;
  approved: boolean;
  sections: Section[];
  inputs: Record<string, Input>;
};
export type Citation = { doc_id: string; locator: string | null; quote: string };
export type Found = {
  id: string;
  value: string;
  status: string;
  method: string;
  author: string;
  stated_for: string | null;
  citations: Citation[];
};
export type Fact = {
  name: string;
  label: string;
  settled: string | null;
  settled_fact: string | null;
  reasons: string[];
  in_conflict: string[];
  facts: Found[];
};
export type Source = {
  doc_id: string;
  locator: string;
  cell: string | null;
  form: string;
  type: string | null;
  date: string | null;
  text: string;
};
export type Change = {
  section: string;
  rewritten: boolean;
  values: { name: string; before: string | null; after: string | null }[];
  removed: string[];
  added: string[];
};
export type Proposal = { id: string; section: string; refused: string[]; sentences: string[] };
export type Table = { heading: string; header: string[]; rows: string[][] };
export type Evals = { experiments?: Table[]; report?: Table[]; cases?: Table[] };
export type Run = { run: string; scenario: string; as_of: string };

export class Refused extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, body?: unknown): Promise<T> {
  const reply = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!reply.ok) {
    const detail = await reply.json().catch(() => ({ detail: reply.statusText }));
    const message = typeof detail.detail === "string" ? detail.detail : "The request was refused.";
    throw new Refused(reply.status, message);
  }
  return (await reply.json()) as T;
}

const enc = encodeURIComponent;

export const api = {
  runs: () => call<Run[]>("/runs"),
  evals: () => call<Evals>("/evals"),
  memo: (run: string) => call<Memo>(`/runs/${enc(run)}/memo`),
  fact: (run: string, name: string) => call<Fact>(`/runs/${enc(run)}/facts/${enc(name)}`),
  source: (run: string, place: Place) =>
    call<Source>(`/runs/${enc(run)}/sources/${enc(place.doc_id)}/${enc(place.locator ?? "p1")}`),
  fileUrl: (run: string, docId: string) => `/api/runs/${enc(run)}/files/${enc(docId)}`,
  edit: (run: string, body: { name: string; value: string; unit: string; reason: string; author: string }) =>
    call<{ changes: Change[]; memo: Memo }>(`/runs/${enc(run)}/edits`, body),
  approve: (run: string, section: string, author: string) =>
    call<Memo>(`/runs/${enc(run)}/sections/${enc(section)}/approve`, { author }),
  requestChanges: (run: string, section: string, author: string, reason: string) =>
    call<Memo>(`/runs/${enc(run)}/sections/${enc(section)}/request-changes`, { author, reason }),
  comment: (run: string, section: string, author: string, text: string, toAgent: boolean) =>
    call<{ proposal: Proposal | null; memo: Memo }>(`/runs/${enc(run)}/sections/${enc(section)}/comments`, {
      author,
      text,
      uses: [],
      to_agent: toAgent,
    }),
  accept: (run: string, proposal: string, author: string) =>
    call<Memo>(`/runs/${enc(run)}/proposals/${enc(proposal)}/accept`, { author }),
};
