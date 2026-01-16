import React, { useEffect, useState, useContext } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import { AuthContext } from "../context/AuthContext";

export default function DepartmentTracker() {
  const { dept } = useParams();
  const { token } = useContext(AuthContext);
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);

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

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">{dept} — Validated Events</h1>
        <Link to="/tracker" className="text-blue-600 underline">
          ← Back to Tracker
        </Link>
        <button
          onClick={async () => {
            try {
              const res = await fetch(`http://localhost:5000/api/tracker/${dept}/report`, {
                headers: { Authorization: "Bearer " + token },
              });
              const blob = await res.blob();
              const link = document.createElement("a");
              link.href = URL.createObjectURL(blob);
              link.download = `${dept}_IQC_Report.pdf`;
              link.click();
            } catch (err) {
              console.error("Report download failed", err);
            }
          }}
          className="bg-green-600 text-white px-4 py-2 rounded-md ml-3 hover:bg-green-700"
        >
          Generate Report PDF
        </button>
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
                          className="bg-blue-600 text-white px-3 py-1 rounded-md text-sm hover:bg-blue-700"
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

      {/* Details Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex justify-center items-center z-50">
          <div className="bg-white rounded-xl shadow-lg w-2/3 p-6 max-h-[80vh] overflow-y-auto">
            <h2 className="text-xl font-semibold mb-4">Event Details</h2>
            <p><strong>Name:</strong> {selectedEvent.name}</p>
            <p><strong>Date:</strong> {selectedEvent.date || "N/A"}</p>
            <p><strong>Category:</strong> {selectedEvent.category}</p>
            <p><strong>Type:</strong> {selectedEvent.type || "Report"}</p>
            <p><strong>Department:</strong> {dept}</p>
            <hr className="my-3" />
            <p><strong>Abstract / Extracted Text:</strong></p>
            <pre className="bg-gray-100 p-3 rounded-md text-sm overflow-x-auto">
              {selectedEvent.extracted_text || "No extracted text available"}
            </pre>
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
