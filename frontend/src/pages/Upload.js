// src/pages/Upload.js
import React, { useState, useContext, useRef } from "react";
import axios from "axios";
import { AuthContext } from "../context/AuthContext";

export default function Upload() {
  const { token, user } = useContext(AuthContext);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return setMessage("Please select a file first.");

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
        setMessage("File uploaded successfully and sent for validation!");
        setFile(null);
      } else {
        setMessage("Upload completed but failed to process.");
      }
    } catch (err) {
      console.error("Upload error:", err);
      setMessage("Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const droppedFile = files[0];
      const allowedTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg'];
      
      if (allowedTypes.includes(droppedFile.type)) {
        setFile(droppedFile);
        setMessage("");
      } else {
        setMessage("Please upload only PDF, PNG, JPG, or JPEG files.");
      }
    }
  };

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setMessage("");
    }
  };

  const handleRemoveFile = () => {
    setFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleClickBrowse = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-semibold mb-2 text-gray-900">
          Upload Event Documents
        </h1>
        <p className="text-gray-600 mb-8">
          Submit event reports or certificates for processing
        </p>

        <div className="card">
          <form onSubmit={handleUpload} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Document
              </label>
              
              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={handleFileSelect}
                className="hidden"
              />

              {/* Drag and Drop Zone */}
              <div
                onDragEnter={handleDragEnter}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={handleClickBrowse}
                className={`
                  relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
                  transition-all duration-200 ease-in-out
                  ${isDragging 
                    ? 'border-indigo-500 bg-indigo-50' 
                    : file 
                      ? 'border-green-400 bg-green-50' 
                      : 'border-gray-300 bg-gray-50 hover:border-indigo-400 hover:bg-indigo-50'
                  }
                `}
              >
                {!file ? (
                  <div className="space-y-3">
                    <div className="flex justify-center">
                      <svg 
                        className={`w-12 h-12 ${isDragging ? 'text-indigo-500' : 'text-gray-400'}`}
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path 
                          strokeLinecap="round" 
                          strokeLinejoin="round" 
                          strokeWidth={2} 
                          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" 
                        />
                      </svg>
                    </div>
                    <div>
                      <p className="text-lg font-medium text-gray-700">
                        {isDragging ? 'Drop file here' : 'Click to browse or drag & drop'}
                      </p>
                      <p className="text-sm text-gray-500 mt-1">
                        Accepted formats: PDF, PNG, JPG, JPEG
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex justify-center">
                      <svg 
                        className="w-12 h-12 text-green-500" 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path 
                          strokeLinecap="round" 
                          strokeLinejoin="round" 
                          strokeWidth={2} 
                          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" 
                        />
                      </svg>
                    </div>
                    <div>
                      <p className="text-lg font-medium text-gray-700">
                        {file.name}
                      </p>
                      <p className="text-sm text-gray-500 mt-1">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemoveFile();
                      }}
                      className="inline-flex items-center px-3 py-1.5 text-sm text-red-600 hover:text-red-800 hover:bg-red-100 rounded transition-colors"
                    >
                      ✕ Remove
                    </button>
                  </div>
                )}
              </div>
            </div>

            <button
              disabled={uploading || !file}
              type="submit"
              className={`w-full py-3 rounded-lg font-medium text-white transition-all duration-150 ${
                uploading || !file
                  ? "bg-gray-400 cursor-not-allowed" 
                  : "bg-indigo-600 hover:bg-indigo-700 hover:shadow-md"
              }`}
            >
              {uploading ? "Uploading..." : "Upload Document"}
            </button>
          </form>

          {message && (
            <div className={`mt-6 p-4 rounded-lg ${
              message.includes("successfully") ? "alert-success" :
              message.includes("failed") ? "alert-error" :
              "alert-warning"
            }`}>
              <p className="font-medium">{message}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
