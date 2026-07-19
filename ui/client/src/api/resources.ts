import axios from "@/http/axiosAgentConfig";

export async function uploadResourceFile(
  file: File,
  format: string = "pem",
): Promise<{ content: string; filename: string; size_bytes: number; format_valid: boolean }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("format", format);

  const response = await axios.post("/resources/resource.upload-file", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}
