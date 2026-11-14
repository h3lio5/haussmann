import { Fragment, useEffect, useState } from "react";
import { api } from "./api";
import type { Evals as Measured, Table } from "./api";

const SHOWN = ["id", "date", "split", "change", "after", "cost_usd", "decision"];

function plain(text: string): string {
  return text.replaceAll("`", "");
}

/** The verdict of a row is its first clause; the rest is read on opening the row. */
function verdict(decision: string): string {
  return plain(decision).split(/[;.:]/)[0] ?? "";
}

function Plain({ table, mark }: { table: Table; mark?: (row: string[]) => string }) {
  return (
    <div className="scroll">
      <table className="grid">
        <thead>
          <tr>
            {table.header.map((name) => (
              <th key={name}>{name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row) => (
            <tr key={row.join("|")} className={mark?.(row) ?? ""}>
              {row.map((cell, index) => (
                <td key={table.header[index]}>{plain(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Log({ table }: { table: Table }) {
  const [open, setOpen] = useState("");
  const at = (name: string) => table.header.indexOf(name);
  const rows = [...table.rows].reverse();
  return (
    <div className="scroll">
      <table className="grid log">
        <thead>
          <tr>
            {SHOWN.map((name) => (
              <th key={name}>{name.replace("_", " ")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const id = row[at("id")] ?? "";
            const isOpen = open === id;
            return (
              <Fragment key={id}>
                <tr
                  className={isOpen ? "entry on" : "entry"}
                  tabIndex={0}
                  role="button"
                  aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? "" : id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setOpen(isOpen ? "" : id);
                    }
                  }}
                >
                  {SHOWN.map((name) => {
                    const cell = row[at(name)] ?? "";
                    return (
                      <td key={name} className={name}>
                        {name === "decision" ? verdict(cell) : plain(cell)}
                      </td>
                    );
                  })}
                </tr>
                {isOpen && (
                  <tr className="detail">
                    <td colSpan={SHOWN.length}>
                      <dl>
                        <dt>Expected before the run</dt>
                        <dd>{plain(row[at("hypothesis")] ?? "")}</dd>
                        <dt>Before</dt>
                        <dd>{plain(row[at("before")] ?? "")}</dd>
                        <dt>After</dt>
                        <dd>{plain(row[at("after")] ?? "")}</dd>
                        <dt>Decision and what was seen</dt>
                        <dd>{plain(row[at("decision")] ?? "")}</dd>
                      </dl>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function Evals() {
  const [measured, setMeasured] = useState<Measured | null>(null);
  const [problem, setProblem] = useState("");

  useEffect(() => {
    api
      .evals()
      .then(setMeasured)
      .catch(() => setProblem("The results could not be read. Check that the review server is running."));
  }, []);

  const log = measured?.experiments?.find((table) => table.header[0] === "id");
  const cases = measured?.cases?.[0];
  const splits = new Map<string, Table[]>();
  for (const table of measured?.report ?? []) {
    splits.set(table.heading, [...(splits.get(table.heading) ?? []), table]);
  }

  return (
    <div className="evals">
      <header className="bar">
        <h1>Haussmann evals</h1>
        <a href="#">Review a memo</a>
      </header>
      <main>
        {problem && <p className="problem">{problem}</p>}
        {!measured && !problem && <p className="quiet">Reading the results…</p>}

        {[...splits].map(([heading, tables]) => (
          <section key={heading}>
            <h2>{heading.startsWith("heldout") ? "Held-out scenarios" : "Dev scenarios"}</h2>
            <p className="quiet">
              {heading.split(":")[1]?.trim().replaceAll("_", " ")}. Three runs per system, pooled.
              {heading.startsWith("heldout")
                ? " Written after the engine was frozen and run once; never tuned on."
                : " The engine was built against these."}
            </p>
            <Plain table={tables[0]!} mark={(row) => (row[0] === "engine" ? "ours" : "")} />
            {tables[1] && (
              <>
                <h3>Traps passed, by type</h3>
                <Plain table={tables[1]} mark={(row) => (row[0] === "engine" ? "ours" : "")} />
              </>
            )}
          </section>
        ))}

        {cases && (
          <section>
            <h2>Regression cases</h2>
            <p className="quiet">
              Each case is a value an expert set in review. A held case must keep passing; an open one is a known
              error the engine has not fixed.
            </p>
            <Plain table={cases} mark={(row) => row[row.length - 1] ?? ""} />
          </section>
        )}

        {log && (
          <section>
            <h2>Experiments</h2>
            <p className="quiet">
              Newest first. Each row states what was expected before the run; select a row to read it in full.
            </p>
            <Log table={log} />
          </section>
        )}
      </main>
    </div>
  );
}
