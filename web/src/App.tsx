import { useCallback, useEffect, useState } from "react";
import { api, Refused } from "./api";
import type { Change, Citation, Fact, Memo, Proposal, Run, Section, Source } from "./api";
import { PdfPage } from "./PdfPage";
import { around } from "./text";

const STATE_LABEL: Record<Section["state"], string> = {
  draft: "Nothing to review",
  in_review: "To review",
  changes_requested: "Changes requested",
  approved: "Approved",
};

const STATUS_LABEL: Record<string, string> = {
  verified: "Found at its source",
  unverified: "Not found at its source",
  rejected: "Replaced",
  set_aside: "Stated for another case",
  candidate: "Not checked",
};

function factName(input: string): string {
  return input.split("#")[0] ?? input;
}

function explain(error: unknown): string {
  if (error instanceof Refused && error.status === 409) {
    return (
      "This demo replays recorded model calls and this action needs a new one. " +
      'Recorded: on the Champagnole file, setting the owner to "Commune de Champagnole", ' +
      'then asking the site section to "Regroupez la référence cadastrale et la contenance dans une seule phrase."'
    );
  }
  return error instanceof Error ? error.message : "The request failed.";
}

export function App() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [run, setRun] = useState<string>("");
  const [memo, setMemo] = useState<Memo | null>(null);
  const [author, setAuthor] = useState("reviewer");
  const [picked, setPicked] = useState<{ section: string; index: number } | null>(null);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [cited, setCited] = useState<Citation | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [changes, setChanges] = useState<Change[] | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [problem, setProblem] = useState<string>("");

  useEffect(() => {
    api
      .runs()
      .then((found) => {
        setRuns(found);
        setRun(found[0]?.run ?? "");
      })
      .catch((error) => setProblem(explain(error)));
  }, []);

  useEffect(() => {
    if (!run) return;
    setMemo(null);
    setPicked(null);
    setFacts([]);
    setCited(null);
    setSource(null);
    setChanges(null);
    setProposal(null);
    setProblem("");
    api
      .memo(run)
      .then(setMemo)
      .catch((error) => setProblem(explain(error)));
  }, [run]);

  const loadFacts = useCallback(
    async (uses: string[]) => {
      const names = [...new Set(uses.map(factName))];
      const found = await Promise.all(names.map((name) => api.fact(run, name)));
      setFacts(found);
      const settled = found[0]?.facts.find((fact) => fact.id === found[0]?.settled_fact);
      const first = settled?.citations[0] ?? found[0]?.facts[0]?.citations[0] ?? null;
      setCited(first);
    },
    [run],
  );

  useEffect(() => {
    if (!cited || !run) {
      setSource(null);
      return;
    }
    api
      .source(run, cited)
      .then(setSource)
      .catch(() => setSource(null));
  }, [cited, run]);

  const pick = (section: Section, index: number) => {
    setPicked({ section: section.id, index });
    setChanges(null);
    setProblem("");
    loadFacts(section.sentences[index]?.uses ?? []).catch((error) => setProblem(explain(error)));
  };

  const act = async (action: () => Promise<void>) => {
    setProblem("");
    try {
      await action();
    } catch (error) {
      setProblem(explain(error));
    }
  };

  const setValue = (name: string, value: string, unit: string, reason: string) =>
    act(async () => {
      const answer = await api.edit(run, { name, value, unit, reason, author });
      setMemo(answer.memo);
      setChanges(answer.changes);
      setPicked(null);
      setFacts([await api.fact(run, name)]);
    });

  if (!memo) {
    return (
      <main className="loading">
        <p>{problem || "Opening the file…"}</p>
      </main>
    );
  }

  const toReview = memo.sections.filter((s) => s.state === "in_review" || s.state === "changes_requested");

  return (
    <div className="desk">
      <header className="bar">
        <h1>Haussmann review</h1>
        <label>
          File
          <select value={run} onChange={(event) => setRun(event.target.value)}>
            {runs.map((found) => (
              <option key={found.run} value={found.run}>
                {found.scenario.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <label>
          Reviewing as
          <input value={author} onChange={(event) => setAuthor(event.target.value)} />
        </label>
        <p className={memo.approved ? "verdict approved" : "verdict"}>
          {memo.approved
            ? "Every section is approved"
            : `${toReview.length} of ${memo.sections.filter((s) => s.state !== "draft").length} sections left to review`}
        </p>
      </header>

      <article className="memo" lang="fr">
        <h2>Note de faisabilité</h2>
        <p className="quiet">Date de revue : {memo.as_of}</p>
        {memo.sections.map((section) => (
          <section key={section.id} className={`section ${section.state}`}>
            <div className="margin">
              <span className={`stamp ${section.state}`}>{STATE_LABEL[section.state]}</span>
            </div>
            <div className="body">
              <h3>{section.title}</h3>
              {section.sentences.length === 0 ? (
                <p className="quiet">Aucun élément.</p>
              ) : (
                <p className={section.kind === "listing" ? "listing" : undefined}>
                  {section.sentences.map((sentence, index) => {
                    const on = picked?.section === section.id && picked.index === index;
                    const flagged = sentence.uses.some((name) => memo.inputs[name]?.flagged);
                    return (
                      <span
                        key={index}
                        role="button"
                        tabIndex={0}
                        className={`sentence${on ? " on" : ""}${flagged ? " flagged" : ""}`}
                        aria-pressed={on}
                        onClick={() => pick(section, index)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            pick(section, index);
                          }
                        }}
                      >
                        {sentence.text}{" "}
                      </span>
                    );
                  })}
                </p>
              )}
              {section.comments.map((remark, index) => (
                <p key={index} className="remark" lang="und">
                  <strong>{remark.author}</strong> {remark.text}
                </p>
              ))}
              {section.state !== "draft" && (
                <SectionActions
                  section={section}
                  proposal={proposal?.section === section.id ? proposal : null}
                  onApprove={() => act(async () => setMemo(await api.approve(run, section.id, author)))}
                  onRequest={(reason) =>
                    act(async () => setMemo(await api.requestChanges(run, section.id, author, reason)))
                  }
                  onAsk={(text) =>
                    act(async () => {
                      const answer = await api.comment(run, section.id, author, text, true);
                      setMemo(answer.memo);
                      setProposal(answer.proposal);
                    })
                  }
                  onAccept={() =>
                    act(async () => {
                      if (!proposal) return;
                      setMemo(await api.accept(run, proposal.id, author));
                      setProposal(null);
                    })
                  }
                  onDiscard={() => setProposal(null)}
                />
              )}
            </div>
          </section>
        ))}
      </article>

      <aside className="evidence">
        {problem && (
          <p className="problem" role="alert">
            {problem}
          </p>
        )}
        {changes && <Changes changes={changes} memo={memo} />}
        {facts.length === 0 && !changes && (
          <div className="empty">
            <h2>Evidence</h2>
            <p>Select a sentence of the memo to see the facts it states and where each one comes from.</p>
          </div>
        )}
        {facts.map((fact) => (
          <FactCard key={fact.name} fact={fact} cited={cited} onCite={setCited} onSet={setValue} />
        ))}
        {source && cited && <SourceView run={run} source={source} cited={cited} />}
      </aside>
    </div>
  );
}

function SectionActions(props: {
  section: Section;
  proposal: Proposal | null;
  onApprove: () => void;
  onRequest: (reason: string) => void;
  onAsk: (text: string) => void;
  onAccept: () => void;
  onDiscard: () => void;
}) {
  const [open, setOpen] = useState<"" | "request" | "ask">("");
  const [text, setText] = useState("");
  const { section, proposal } = props;
  const send = () => {
    if (!text.trim()) return;
    if (open === "request") props.onRequest(text);
    else props.onAsk(text);
    setText("");
    setOpen("");
  };
  return (
    <div className="actions" lang="en">
      <div className="row">
        <button type="button" disabled={section.state === "approved"} onClick={props.onApprove}>
          {section.state === "approved" ? "Approved" : "Approve section"}
        </button>
        <button type="button" className="plain" onClick={() => setOpen(open === "request" ? "" : "request")}>
          Request changes
        </button>
        {section.kind === "prose" && (
          <button type="button" className="plain" onClick={() => setOpen(open === "ask" ? "" : "ask")}>
            Ask for a rewording
          </button>
        )}
      </div>
      {open && (
        <div className="row">
          <input
            autoFocus
            value={text}
            placeholder={open === "request" ? "What has to change?" : "How should it read? (in French)"}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && send()}
          />
          <button type="button" onClick={send}>
            {open === "request" ? "Request changes" : "Ask"}
          </button>
        </div>
      )}
      {proposal && (
        <div className="proposal">
          {proposal.refused.length > 0 ? (
            <>
              <p>The proposed rewording broke a rule of the memo and was not kept.</p>
              <ul>
                {proposal.refused.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <button type="button" className="plain" onClick={props.onDiscard}>
                Close
              </button>
            </>
          ) : (
            <>
              <p>Proposed rewording. No value was changed: values are printed from the facts.</p>
              <blockquote lang="fr">{proposal.sentences.join(" ")}</blockquote>
              <div className="row">
                <button type="button" onClick={props.onAccept}>
                  Accept rewording
                </button>
                <button type="button" className="plain" onClick={props.onDiscard}>
                  Keep the current text
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function FactCard(props: {
  fact: Fact;
  cited: Citation | null;
  onCite: (citation: Citation) => void;
  onSet: (name: string, value: string, unit: string, reason: string) => void;
}) {
  const { fact, cited } = props;
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [unit, setUnit] = useState("");
  const [reason, setReason] = useState("");
  const disputed = fact.in_conflict.length > 0;
  return (
    <section className="fact">
      <h2 lang="fr">{fact.label}</h2>
      <p className="settled" lang="fr">
        {fact.settled ?? "Aucune valeur retenue"}
      </p>
      {fact.reasons.length > 0 && <p className="why">{fact.reasons.join("; ")}</p>}
      <ul className="found">
        {fact.facts.map((found) => {
          const chosen = found.id === fact.settled_fact;
          return (
            <li key={found.id} className={chosen ? "chosen" : found.status}>
              <p>
                <span className="value" lang="fr">
                  {found.value}
                </span>
                <span className="standing">
                  {chosen
                    ? "Kept"
                    : disputed && fact.in_conflict.includes(found.id)
                      ? "Other side of the disagreement"
                      : (STATUS_LABEL[found.status] ?? found.status)}
                </span>
              </p>
              <p className="quiet">
                {found.method === "expert"
                  ? `Set by ${found.author}`
                  : found.method === "computed"
                    ? "Recomputed from its parts"
                    : found.stated_for
                      ? `Stated for ${found.stated_for}`
                      : "Read in the file"}
              </p>
              {found.citations.map((citation, index) => {
                const on = cited?.doc_id === citation.doc_id && cited.locator === citation.locator;
                return (
                  <button
                    key={index}
                    type="button"
                    className={`cite${on ? " on" : ""}`}
                    onClick={() => props.onCite(citation)}
                  >
                    {citation.doc_id.replaceAll("_", " ")}
                    {citation.locator ? `, ${citation.locator}` : ""}
                  </button>
                );
              })}
            </li>
          );
        })}
      </ul>
      {editing ? (
        <form
          className="edit"
          onSubmit={(event) => {
            event.preventDefault();
            props.onSet(fact.name, value, unit, reason);
            setEditing(false);
          }}
        >
          <label>
            Value
            <input required value={value} onChange={(event) => setValue(event.target.value)} />
          </label>
          <label>
            Unit, if any
            <input value={unit} onChange={(event) => setUnit(event.target.value)} placeholder="m2, m, EUR…" />
          </label>
          <label>
            Why
            <input
              required
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Which document or check supports it"
            />
          </label>
          <div className="row">
            <button type="submit">Set value</button>
            <button type="button" className="plain" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button type="button" className="plain" onClick={() => setEditing(true)}>
          Set another value
        </button>
      )}
    </section>
  );
}

function Changes({ changes, memo }: { changes: Change[]; memo: Memo }) {
  const title = (id: string) => memo.sections.find((section) => section.id === id)?.title ?? id;
  const kept = memo.sections.filter((s) => s.state !== "draft").length - changes.filter((c) => c.rewritten).length;
  return (
    <section className="changes">
      <h2>What the edit changed</h2>
      <p className="quiet">
        {changes.filter((c) => c.rewritten).length} sections rewritten, {kept} left as they were. The edit is now
        a regression case for the engine.
      </p>
      {changes.map((change) => (
        <div key={change.section} className="change" lang="fr">
          <h3>{title(change.section)}</h3>
          {change.values
            .filter((value) => !value.name.includes("#"))
            .map((value) => (
            <p key={value.name} className="swap">
              <del>{value.before ?? "absent"}</del> <ins>{value.after ?? "absent"}</ins>
            </p>
          ))}
          {change.removed.map((text) => (
            <p key={`-${text}`} className="minus">
              {text}
            </p>
          ))}
          {change.added.map((text) => (
            <p key={`+${text}`} className="plus">
              {text}
            </p>
          ))}
        </div>
      ))}
    </section>
  );
}

function SourceView({ run, source, cited }: { run: string; source: Source; cited: Citation }) {
  const parts = cited.quote ? around(source.text, cited.quote) : null;
  const page = /^p(\d+)$/.exec(source.locator);
  return (
    <section className="source">
      <h2>
        {source.doc_id.replaceAll("_", " ")}
        <span className="quiet">
          {" "}
          {source.cell ?? source.locator}
          {source.type ? `, ${source.type.replaceAll("_", " ")}` : ""}
          {source.date ? `, ${source.date}` : ""}
        </span>
      </h2>
      {source.form === "pdf" && page && (
        <PdfPage url={api.fileUrl(run, source.doc_id)} page={Number(page[1])} quote={cited.quote} />
      )}
      {source.form === "xlsx" ? (
        <table className="cells" lang="fr">
          <tbody>
            {source.text.split("\n").map((line) => {
              const cell = /^\[([^\]]+)\] ?(.*)$/.exec(line);
              if (!cell) return null;
              const on = cell[1] === source.cell || (!!cited.quote && !source.cell && cell[2] === cited.quote);
              return (
                <tr key={cell[1]} className={on ? "on" : undefined}>
                  <th>{cell[1]?.split("!")[1]}</th>
                  <td>{cell[2]}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p className="page-text" lang="fr">
          {parts ? (
            <>
              {parts[0]}
              <mark>{parts[1]}</mark>
              {parts[2]}
            </>
          ) : (
            source.text
          )}
        </p>
      )}
    </section>
  );
}
