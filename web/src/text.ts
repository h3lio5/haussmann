/** Lower case, no accents, no punctuation, single spaces: how the verifier compares text. */
export function canonical(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

/** Split a text around the first place the quote occurs, comparing as the verifier does. */
export function around(text: string, quote: string): [string, string, string] | null {
  const wanted = canonical(quote);
  if (!wanted) return null;
  const starts: number[] = [];
  let plain = "";
  for (let index = 0; index < text.length; index++) {
    const piece = canonical(text[index] ?? "");
    if (piece) {
      for (const char of piece) {
        plain += char;
        starts.push(index);
      }
    } else if (plain && !plain.endsWith(" ")) {
      plain += " ";
      starts.push(index);
    }
  }
  const at = plain.indexOf(wanted);
  if (at < 0) return null;
  const from = starts[at] ?? 0;
  const to = (starts[at + wanted.length - 1] ?? text.length - 1) + 1;
  return [text.slice(0, from), text.slice(from, to), text.slice(to)];
}
