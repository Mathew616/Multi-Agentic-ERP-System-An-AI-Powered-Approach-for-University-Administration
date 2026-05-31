import React, { useEffect, useState, useContext } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { AuthContext } from "../context/AuthContext";

export default function DepartmentTracker() {
  const { dept } = useParams();
  const { token } = useContext(AuthContext);
  const navigate = useNavigate();
  const [events, setEvents] = useState({});
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);

  useEffect(() => {
    const fetchDept = async () => {
      try {
        const res = await axios.get(`http://localhost:5000/api/tracker/${dept}`, {
          headers: { Authorization: "Bearer " + token },
        });
        setEvents(res.data.events_by_category || {});
      } catch (err) {
        console.error("Failed to fetch department details", err);
      }
    };
    fetchDept();
  }, [dept, token]);

  const handleDownloadReport = async () => {
    try {
      setLoadingReport(true);
      const res = await fetch(`http://localhost:5000/api/tracker/${dept}/report`, {
        headers: { Authorization: "Bearer " + token },
      });
      const blob = await res.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${dept}_IQC_Report.pdf`;
      link.click();
      link.remove();
    } catch (err) {
      console.error("Report download failed", err);
      alert("Failed to generate report.");
    } finally {
      setLoadingReport(false);
    }
  };

  const total = 10;
  const validatedCount = Object.values(events).flat().length;
  const progress = ((validatedCount / total) * 100).toFixed(1);

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate("/tracker")}
            className="bg-white border border-gray-300 text-gray-700 px-4 py-2 rounded-md shadow-sm hover:bg-gray-100 transition text-sm font-medium"
          >
            &larr; Back
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-800">
              Department of {dept} — Events Overview
            </h1>
            <p className="text-gray-500 text-sm mt-1">
              Validated events grouped by IQC activity categories
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <p className="text-gray-600 font-medium">Progress: {validatedCount}/{total}</p>
          <button
            onClick={handleDownloadReport}
            disabled={loadingReport}
            className={`${
              loadingReport
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-green-600 hover:bg-green-700"
            } text-white px-5 py-2 rounded-md shadow font-medium transition`}
          >
            {loadingReport ? "Generating..." : "Generate Report PDF"}
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-gray-200 rounded-full h-3 mb-8">
        <div
          className="bg-green-600 h-3 rounded-full transition-all"
          style={{ width: `${progress}%` }}
        ></div>
      </div>

      {/* Category Sections */}
      {Object.keys(events).length === 0 ? (
        <p className="text-gray-500">No validated events yet.</p>
      ) : (
        Object.entries(events).map(([category, catEvents]) => (
          <div key={category} className="mb-8 bg-white rounded-lg shadow-md p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-gray-800">{category}</h2>
              <span className="text-xs font-medium bg-gray-100 text-gray-600 px-3 py-1 rounded-full">
                {catEvents.length} {catEvents.length === 1 ? "event" : "events"}
              </span>
            </div>

            {catEvents.length === 0 ? (
              <p className="text-gray-400 text-sm italic">No events in this category.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="border px-4 py-2.5 text-left text-gray-600 font-semibold">Event Name</th>
                      <th className="border px-4 py-2.5 text-left text-gray-600 font-semibold">Date</th>
                      <th className="border px-4 py-2.5 text-left text-gray-600 font-semibold">Category</th>
                      <th className="border px-4 py-2.5 text-left text-gray-600 font-semibold">Type</th>
                      <th className="border px-4 py-2.5 text-center text-gray-600 font-semibold">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {catEvents.map((e) => (
                      <tr key={e.id} className="hover:bg-gray-50 border-t">
                        <td className="border px-4 py-2.5">{e.name}</td>
                        <td className="border px-4 py-2.5">{e.date || "N/A"}</td>
                        <td className="border px-4 py-2.5">{e.category}</td>
                        <td className="border px-4 py-2.5">{e.type || "Report"}</td>
                        <td className="border px-4 py-2.5 text-center">
                          <button
                            onClick={() => setSelectedEvent(e)}
                            className="bg-blue-600 text-white px-3 py-1 rounded-md text-sm hover:bg-blue-700 transition"
                          >
                            View Details
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))
      )}

      {/* Details Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex justify-center items-center z-50">
          <div className="bg-white rounded-xl shadow-lg w-2/3 p-6 max-h-[80vh] overflow-y-auto">
            <h2 className="text-xl font-semibold mb-4 text-gray-800">Event Details</h2>
            <div className="space-y-2 text-gray-700">
              <p><strong>Name:</strong> {selectedEvent.name}</p>
              <p><strong>Date:</strong> {selectedEvent.date || "N/A"}</p>
              <p><strong>Category:</strong> {selectedEvent.category}</p>
              <p><strong>Type:</strong> {selectedEvent.type || "Report"}</p>
              <p><strong>Department:</strong> {dept}</p>
            </div>
            <hr className="my-4" />
            <p className="font-semibold text-gray-700 mb-2">Abstract / Extracted Text:</p>
            <pre className="bg-gray-100 p-3 rounded-md text-sm overflow-x-auto text-gray-600">
              {selectedEvent.extracted_text || "No extracted text available"}
            </pre>
            <div className="text-right mt-5">
              <button
                onClick={() => setSelectedEvent(null)}
                className="bg-gray-200 text-gray-700 px-5 py-2 rounded-md hover:bg-gray-300 font-medium transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
