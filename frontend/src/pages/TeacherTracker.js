import React, { useEffect, useState, useContext } from "react";
import axios from "axios";
import { AuthContext } from "../context/AuthContext";

export default function TeacherTracker() {
  const { token, user } = useContext(AuthContext);
  const [events, setEvents] = useState({});
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);

    // 📄 Download Report Handler
    const handleDownloadReport = async () => {
    try {
        setLoadingReport(true);
        const response = await axios.get(
        `http://localhost:5000/api/tracker/${user.department}/report`,
        {
            headers: { Authorization: `Bearer ${token}` },
            responseType: "blob", // get PDF stream
        }
        );

        // Create a temporary download link
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `${user.department}_IQC_Report.pdf`);
        document.body.appendChild(link);
        link.click();
        link.remove();
    } catch (err) {
        console.error("Failed to download report:", err);
        alert("Failed to generate report.");
    } finally {
        setLoadingReport(false);
    }
    };


  useEffect(() => {
    const fetchDeptEvents = async () => {
      try {
        const res = await axios.get(`http://localhost:5000/api/tracker/${user.department}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setEvents(res.data.events_by_category || {});
      } catch (err) {
        console.error("Failed to fetch department events", err);
      }
    };
    fetchDeptEvents();
  }, [user, token]);

  const total = 10;
  const validatedCount = Object.values(events).flat().length;
  const progress = ((validatedCount / total) * 100).toFixed(1);

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">
            {user.department} Department — Events Overview
        </h1>

        <div className="flex items-center gap-4">
            <p className="text-gray-600">Progress: {validatedCount}/10</p>
            <button
            onClick={handleDownloadReport}
            disabled={loadingReport}
            className={`${
                loadingReport
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-green-600 hover:bg-green-700"
            } text-white px-4 py-2 rounded-md shadow`}
            >
            {loadingReport ? "Generating..." : "Download Report"}
            </button>
        </div>
    </div>


      <div className="w-full bg-gray-200 rounded-full h-3 mb-6">
        <div
          className="bg-green-600 h-3 rounded-full transition-all"
          style={{ width: `${progress}%` }}
        ></div>
      </div>

      {Object.keys(events).length === 0 ? (
        <p>No validated events yet.</p>
      ) : (
        Object.entries(events).map(([category, catEvents]) => (
          <div key={category} className="mb-10 bg-white rounded-lg shadow-md p-5">
            <h2 className="text-xl font-semibold mb-3 text-gray-800">{category}</h2>

            {catEvents.length === 0 ? (
              <p className="text-gray-500 text-sm italic">No events in this category.</p>
            ) : (
              <table className="w-full border text-sm">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="border px-3 py-2">Event Name</th>
                    <th className="border px-3 py-2">Date</th>
                    <th className="border px-3 py-2">Category</th>
                    <th className="border px-3 py-2">Type</th>
                    <th className="border px-3 py-2 text-center">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {catEvents.map((e) => (
                    <tr key={e.id} className="hover:bg-gray-50 border-t">
                      <td className="border px-3 py-2">{e.name}</td>
                      <td className="border px-3 py-2">{e.date || "N/A"}</td>
                      <td className="border px-3 py-2">{e.category}</td>
                      <td className="border px-3 py-2">{e.type || "Report"}</td>
                      <td className="border px-3 py-2 text-center">
                        <button
                          onClick={() => setSelectedEvent(e)}
                          className="bg-green-600 text-white px-3 py-1 rounded-md text-sm hover:bg-green-700"
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))
      )}

      {selectedEvent && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex justify-center items-center z-50">
          <div className="bg-white rounded-xl shadow-lg w-2/3 p-6 max-h-[80vh] overflow-y-auto">
            <h2 className="text-xl font-semibold mb-4">Event Details</h2>
            <p><strong>Name:</strong> {selectedEvent.name}</p>
            <p><strong>Date:</strong> {selectedEvent.date || "N/A"}</p>
            <p><strong>Category:</strong> {selectedEvent.category}</p>
            <p><strong>Type:</strong> {selectedEvent.type || "Report"}</p>
            <p><strong>Department:</strong> {user.department}</p>
            <div className="text-right mt-5">
              <button
                onClick={() => setSelectedEvent(null)}
                className="bg-gray-300 px-4 py-2 rounded-md hover:bg-gray-400"
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
