export interface FileExtraction {
  id: string;
  uploaded_file_id: string;
  extractor_name: string;
  status: "succeeded" | "failed";
  text_content: string | null;
  metadata: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface UploadedFile {
  id: string;
  thread_id: string | null;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  sha256: string;
  status: "uploaded" | "extracted" | "failed" | "deleted";
  created_at: string;
  updated_at: string;
  extraction: FileExtraction | null;
}

export interface UploadedFileList {
  items: UploadedFile[];
}

// 文件上传只把原始文件交给后端解析。前端不再用 FileReader 直接读取，
// 这样 PDF/DOCX 和解析失败状态都能统一由后端记录。
export async function uploadChatFile(file: File, threadId: string): Promise<UploadedFile> {
  const form = new FormData();
  form.append("file", file);
  form.append("thread_id", threadId);

  const response = await fetch("/api/files", {
    method: "POST",
    body: form,
  });

  if (!response.ok) {
    throw new Error(`Upload file failed with ${response.status}`);
  }

  return response.json() as Promise<UploadedFile>;
}

export async function fetchThreadFiles(threadId: string): Promise<UploadedFileList> {
  const response = await fetch(`/api/files?thread_id=${encodeURIComponent(threadId)}`);

  if (!response.ok) {
    throw new Error(`Fetch files failed with ${response.status}`);
  }

  return response.json() as Promise<UploadedFileList>;
}
