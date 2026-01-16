// src/pages/TeacherUpload.js
import React, { useState, useContext } from "react";
import axios from "axios";
import { AuthContext } from "../context/AuthContext";

export default function TeacherUpload() {
  const { token, user } = useContext(AuthContext);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return setMessage("⚠️ Please select a file first.");

    const formData = new FormData();
    formData.append("file", file);

    try {
      setUploading(true);
      setMessage("");

      const res = await axios.post("http://localhost:5000/api/upload", formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data",
        },
      });

      if (res.data.success) {
        setMessage("✅ File uploaded successfully and sent for processing!");
        setFile(null);
      } else {
        setMessage("⚠️ Upload completed but failed to process.");
      }
    } catch (err) {
      console.error("Upload error:", err);
      setMessage("❌ Upload failed. Try again.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-8 bg-gray-50 min-h-screen flex flex-col items-center">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">
        Upload Event Reports / Certificates
      </h1>

      <form
        onSubmit={handleUpload}
        className="bg-white rounded-lg shadow-lg p-6 w-full max-w-md border border-gray-200"
      >
        <input
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          onChange={(e) => setFile(e.target.files[0])}
          className="w-full border p-2 rounded mb-4"
        />
        <button
          disabled={uploading}
          type="submit"
          className={`w-full py-2 rounded text-white ${
            uploading ? "bg-gray-400 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"
          }`}
        >
          {uploading ? "Uploading..." : "Upload File"}
        </button>
      </form>

      {message && (
        <p className="mt-4 text-center text-sm font-medium text-gray-700">{message}</p>
      )}
    </div>
  );
}
