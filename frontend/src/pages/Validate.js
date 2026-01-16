import React, { useEffect, useState } from "react";
import axios from "axios";
import { useAuth } from "../context/AuthContext";

  const DEPARTMENTS = [
    { value: "", label: "-- Department (optional) --" },
    { value: "AIML", label: "Computer Science & Engineering - AIML" },
    { value: "CSE(Core)", label: "Computer Science & Engineering (Core)" },
    { value: "CSE-DS", label: "Computer Science & Engineering - Data Science" },
    { value: "CSE-CY", label: "Computer Science & Engineering - Cyber Security" },
    { value: "ISE", label: "Information Science & Engineering" },
    { value: "ECE", label: "Electronics & Communication Engineering" },
    { value: "AERO", label: "Aeronautical Engineering" },
  ];

const EVENT_TYPES = [
  { value: "Seminar", label: "Seminar" },
  { value: "Workshop", label: "Workshop / Hands-on / Training" },
  { value: "Guest Lecture", label: "Guest Lecture / Expert Talk" },
  { value: "Conference", label: "Conference / Symposium" },
  { value: "Competition", label: "Competition / Hackathon / Quiz" },
  { value: "Orientation", label: "Orientation / Induction / Welcome" },
  { value: "Research/Report", label: "Research / Report / Paper Presentation" },
  { value: "Certificate Event", label: "Certificate Event" },
  { value: "General Event", label: "General / Department Activity" },
];

function DocumentModal({ open, onClose, docId, token, onValidated }) {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState([]);

  const [form, setForm] = useState({
    name: "",
    date: "",
    category: "",
    department: "",
    venue: "",
    organizer: "",
    abstract: "",
    comment: "",
  });

  useEffect(() => {
    if (!open || !docId) return;
    setLoading(true);
    (async () => {
      try {
        const res = await axios.get(`http://localhost:5000/api/document/${docId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = res.data;
        setDoc(data);

        // Helper function to get entity value by type
        const getEntityValue = (entityType) => {
          const entity = data.entities?.find(
            (e) => e.entity_type.toLowerCase() === entityType.toLowerCase()
          );
          return entity?.entity_value || "";
        };

        if (data.events?.[0]) {
          const ev = data.events[0];
          setForm({
            name: ev.name || getEntityValue("event_name") || "",
            date: ev.date || getEntityValue("date") || "",
            category: ev.category || getEntityValue("category") || "",
            department: ev.department || getEntityValue("department") || "",
            venue: getEntityValue("venue") || "",
            organizer: getEntityValue("organizer") || "",
            abstract: getEntityValue("abstract") || data.abstract || "",
          });
        }
      } catch (err) {
        console.error("Failed to load document", err);
      } finally {
        setLoading(false);
      }
    })();
  }, [open, docId, token]);

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleValidate = async () => {
    try {
      const evId = doc.events[0].id;
      const res = await axios.post(
        `http://localhost:5000/api/validate/${evId}`,
        form,
        {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (res.data.errors?.length) {
        setErrors(res.data.errors);
        alert("⚠️ Please fix the highlighted fields.");
      } else {
        alert("✅ Event validated successfully!");
        onValidated(evId);
        onClose();
      }
    } catch (e) {
      console.error("Validation failed", e);
      alert("Validation failed!");
    }
  };

  const handleReject = async () => {
    if (!window.confirm("Are you sure you want to mark this document as NOT valid?")) return;

    try {
      const evId = doc.events[0].id;
      const res = await axios.post(
        `http://localhost:5000/api/validate/${evId}/reject`,
        { comment: form.comment || "Rejected by reviewer." },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (res.status === 200) {
        alert("❌ Document marked as NOT valid. Student will be notified.");
        onValidated(evId);
        onClose();
      }
    } catch (e) {
      console.error("Rejection failed", e);
      alert("Rejection failed!");
    }
  };

  if (!open) return null;

  const fileUrl = `http://localhost:5000/api/document/${docId}/file?token=${token}`;
  const fieldStyle = (key) =>
    errors.some((err) => err.toLowerCase().includes(key)) ? "border-red-500" : "border-gray-300";

  // Get document type badge
  const docType = doc?.events?.[0]?.type || "Report";
  const isCertificate = docType === "Certificate";

  return (
    <div className="fixed inset-0 flex items-start justify-center p-6 z-50">
      <div className="absolute inset-0 bg-black opacity-40" onClick={onClose}></div>
      <div className="bg-white rounded-lg p-6 shadow-xl relative z-50 w-full max-w-3xl max-h-[85vh] overflow-auto">
        {/* Header with Document Type Badge */}
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">Document Review & Validation</h2>
          <span
            className={`px-3 py-1 rounded-full text-sm font-semibold ${
              isCertificate
                ? "bg-purple-100 text-purple-700 border border-purple-300"
                : "bg-blue-100 text-blue-700 border border-blue-300"
            }`}
          >
            {isCertificate ? "📜 Certificate" : "📄 Report"}
          </span>
        </div>

        <a href={fileUrl} target="_blank" rel="noreferrer" className="text-blue-600 underline">
          📄 Open Uploaded File
        </a>

        {errors.length > 0 && (
          <div className="bg-red-50 border border-red-400 text-red-600 p-2 mt-3 rounded text-sm">
            <strong>⚠ Validation Issues:</strong>
            <ul className="list-disc ml-5">
              {errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-4 space-y-2">
          <label className="block">
            <span className="text-sm font-medium">Event Name:</span>
            <input
              value={form.name}
              onChange={(e) => handleChange("name", e.target.value)}
              className={`border p-2 w-full rounded ${fieldStyle("event name")}`}
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium">Date:</span>
            <input
              type="date"
              value={form.date ? form.date.slice(0, 10) : ""}
              onChange={(e) => handleChange("date", e.target.value)}
              className={`border p-2 w-full rounded ${fieldStyle("date")}`}
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium">
              Event Type:
              {isCertificate && (
                <span className="ml-2 text-purple-600 text-xs font-normal">
                  (Certificate detected - consider "Certificate Event")
                </span>
              )}
            </span>
            <select
              value={form.category}
              onChange={(e) => handleChange("category", e.target.value)}
              className={`border p-2 w-full rounded ${fieldStyle("category")}`}
            >
              <option value="">-- Select Event Type --</option>
              {EVENT_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium">Department:</span>
            <select
              value={form.department}
              onChange={(e) => handleChange("department", e.target.value)}
              className={`border p-2 w-full rounded ${fieldStyle("department")}`}
            >
              <option value="">-- Select Department --</option>
              {DEPARTMENTS.map((dept) => (
                <option key={dept.value} value={dept.value}>
                  {dept.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium">Venue:</span>
            <input
              value={form.venue}
              onChange={(e) => handleChange("venue", e.target.value)}
              className={`border p-2 w-full rounded ${fieldStyle("venue")}`}
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium">Organizer:</span>
            <input
              value={form.organizer}
              onChange={(e) => handleChange("organizer", e.target.value)}
              className={`border p-2 w-full rounded ${fieldStyle("organizer")}`}
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium">Abstract / Description:</span>
            <textarea
              value={form.abstract}
              onChange={(e) => handleChange("abstract", e.target.value)}
              className={`border p-2 w-full rounded ${fieldStyle("abstract")}`}
              rows={4}
            />
          </label>
        </div>

        <div className="mt-4">
          <h3 className="font-semibold">Extracted Entities</h3>
          <ul className="list-disc pl-5 text-sm">
            {doc?.entities?.length ? (
              doc.entities.map((e, i) => (
                <li key={i}>
                  <strong>{e.entity_type}</strong>: {e.entity_value} (conf: {e.confidence})
                </li>
              ))
            ) : (
              <li>No entities found.</li>
            )}
          </ul>
        </div>

        <div className="mt-6 space-y-2">
          <label className="block">
            <span className="text-sm font-medium">Reviewer Comment (Optional):</span>
            <textarea
              value={form.comment || ""}
              onChange={(e) => handleChange("comment", e.target.value)}
              placeholder="Add a note explaining rejection or feedback..."
              className="border p-2 w-full rounded text-sm"
              rows={3}
            />
          </label>

          <div className="flex justify-end gap-3">
            <button
              onClick={handleValidate}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded"
            >
              ✅ Validate & Save
            </button>
            <button
              onClick={handleReject}
              className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded"
            >
              ❌ Discard / Not Valid
            </button>
            <button onClick={onClose} className="bg-gray-300 px-4 py-2 rounded">
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Validate() {
  const { token } = useAuth();
  const [events, setEvents] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState(null);

  useEffect(() => {
    fetchEvents();
  }, [token]);

  const fetchEvents = async () => {
    try {
      const res = await axios.get("http://localhost:5000/api/validate/events", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setEvents(res.data.events || []);
    } catch (err) {
      console.error("Error fetching events", err);
    }
  };

  const onValidated = (id) => {
    setEvents(events.filter((e) => e.id !== id));
  };

  // Get document type badge helper
  const getTypeBadge = (type) => {
    if (type === "Certificate") {
      return (
        <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs font-semibold rounded-full">
          📜 Certificate
        </span>
      );
    }
    return (
      <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs font-semibold rounded-full">
        📄 Report
      </span>
    );
  };

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      <h1 className="text-2xl font-bold mb-4">Validation Queue</h1>
      {events.length === 0 ? (
        <p>No pending events 🎉</p>
      ) : (
        <table className="w-full border bg-white rounded shadow">
          <thead>
            <tr className="bg-gray-200">
              <th className="p-2 border">Type</th>
              <th className="p-2 border">Event Name</th>
              <th className="p-2 border">Date</th>
              <th className="p-2 border">Category</th>
              <th className="p-2 border">Department</th>
              <th className="p-2 border">Uploaded By</th>
              <th className="p-2 border">Action</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-t hover:bg-gray-100">
                <td className="p-2 border text-center">
                  {getTypeBadge(e.type || "Report")}
                </td>
                <td className="p-2 border">{e.name || "Unknown"}</td>
                <td className="p-2 border">{e.date || "N/A"}</td>
                <td className="p-2 border">{e.category || "General"}</td>
                <td className="p-2 border">{e.department || "Unknown"}</td>
                <td className="p-2 border">{e.uploaded_by}</td>
                <td className="p-2 border text-center">
                  <button
                    onClick={() => {
                      setSelectedDocId(e.document_id);
                      setModalOpen(true);
                    }}
                    className="bg-blue-600 text-white px-3 py-1 rounded"
                  >
                    Review
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <DocumentModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        docId={selectedDocId}
        token={token}
        onValidated={onValidated}
      />
    </div>
  );
}