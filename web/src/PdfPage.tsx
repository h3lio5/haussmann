import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useEffect, useRef, useState } from "react";
import { canonical } from "./text";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

type Box = { left: number; top: number; width: number; height: number };

/** One page of a PDF, with the lines that hold the quote marked over it. */
export function PdfPage({ url, page, quote }: { url: string; page: number; quote: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [boxes, setBoxes] = useState<Box[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const task = pdfjs.getDocument({ url });
    (async () => {
      try {
        const document = await task.promise;
        const shown = await document.getPage(page);
        const target = canvas.current;
        if (cancelled || !target) return;
        const width = target.parentElement?.clientWidth ?? 560;
        const base = shown.getViewport({ scale: 1 });
        const viewport = shown.getViewport({ scale: width / base.width });
        const ratio = window.devicePixelRatio || 1;
        target.width = viewport.width * ratio;
        target.height = viewport.height * ratio;
        target.style.width = `${viewport.width}px`;
        target.style.height = `${viewport.height}px`;
        const context = target.getContext("2d");
        if (!context) return;
        context.setTransform(ratio, 0, 0, ratio, 0, 0);
        await shown.render({ canvas: target, canvasContext: context, viewport }).promise;

        const content = await shown.getTextContent();
        const wanted = canonical(quote);
        let plain = "";
        const spans: { from: number; to: number; box: Box }[] = [];
        for (const item of content.items) {
          if (!("str" in item)) continue;
          const piece = canonical(item.str);
          if (!piece) continue;
          const from = plain.length + (plain ? 1 : 0);
          plain += (plain ? " " : "") + piece;
          const [x1, y1] = viewport.convertToViewportPoint(item.transform[4], item.transform[5]);
          const [x2, y2] = viewport.convertToViewportPoint(
            item.transform[4] + item.width,
            item.transform[5] + item.height,
          );
          const box = {
            left: Math.min(x1, x2),
            top: Math.min(y1, y2),
            width: Math.abs(x2 - x1),
            height: Math.abs(y2 - y1),
          };
          spans.push({ from, to: plain.length, box });
        }
        const at = wanted ? plain.indexOf(wanted) : -1;
        const marked =
          at < 0 ? [] : spans.filter((s) => s.to > at && s.from < at + wanted.length).map((s) => s.box);
        if (!cancelled) setBoxes(marked);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      void task.destroy();
    };
  }, [url, page, quote]);

  const first = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    first.current?.scrollIntoView({ block: "center" });
  }, [boxes]);

  if (failed) return <p className="quiet">The page image could not be drawn. The text is below.</p>;
  return (
    <div className="pdf">
      <canvas ref={canvas} />
      {boxes.map((box, index) => (
        <span key={index} ref={index === 0 ? first : undefined} className="pdf-mark" style={box} />
      ))}
    </div>
  );
}
