import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadInvoice } from "../api";

export default function Upload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [isPdf, setIsPdf] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setError(null);
    if (file.type === "application/pdf") {
      setIsPdf(true);
      setPreview(null);
    } else {
      setIsPdf(false);
      setPreview(URL.createObjectURL(file));
    }
  }

  async function handleUpload() {
    const file = inputRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadInvoice(file);
      navigate("/invoices");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="mt-6">
      <h1 className="text-xl font-bold mb-4">Upload Receipt</h1>

      <div
        className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-blue-400 transition-colors"
        onClick={() => inputRef.current?.click()}
      >
        {preview ? (
          <img src={preview} alt="Preview" className="mx-auto max-h-64 rounded-lg object-contain" />
        ) : isPdf ? (
          <div className="text-5xl mb-2">📄</div>
        ) : (
          <div className="text-5xl mb-2">📷</div>
        )}
        <p className="text-gray-500 mt-2 text-sm">
          {fileName ?? "Tap to select a photo or PDF"}
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="image/*,application/pdf"
          capture="environment"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-600">{error}</p>
      )}

      <button
        onClick={handleUpload}
        disabled={!fileName || uploading}
        className="mt-4 w-full py-3 rounded-xl bg-blue-600 text-white font-semibold text-base disabled:opacity-40 hover:bg-blue-700 transition-colors"
      >
        {uploading ? "Uploading…" : "Upload"}
      </button>
    </div>
  );
}
