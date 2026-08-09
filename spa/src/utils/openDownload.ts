export function openDownload(url: string): void {
  window.open(url, "_blank", "noopener,noreferrer");
}

export function getDownloadFilename(
  contentDisposition: string | null,
  fallback: string,
): string {
  const encoded = contentDisposition?.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = contentDisposition?.match(/filename="?([^";]+)"?/i)?.[1];
  const candidate = encoded ? decodeURIComponent(encoded) : plain || fallback;
  return Array.from(candidate, (character) => {
    const code = character.charCodeAt(0);
    return character === "/" || character === "\\" || code < 32 || code === 127
      ? "_"
      : character;
  }).join("");
}

export async function downloadResponse(
  response: Response,
  fallbackFilename: string,
): Promise<void> {
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = getDownloadFilename(
    response.headers.get("Content-Disposition"),
    fallbackFilename,
  );
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
