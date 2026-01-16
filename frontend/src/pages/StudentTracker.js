import React, { useEffect, useState, useContext } from "react";
import axios from "axios";
import { AuthContext } from "../context/AuthContext";

export default function StudentTracker() {
  const { token, user } = useContext(AuthContext);
  const [events, setEvents] = useState({});
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [rejectedEvents, setRejectedEvents] = useState([]);
  const [deletingId, setDeletingId] = useState(null);

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

  useEffect(() => {
    const fetchRejected = async () => {
      try {
        const res = await axios.get(
          `http://localhost:5000/api/tracker/rejected/${user.username}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setRejectedEvents(res.data.rejected_events || []);
      } catch (err) {
        console.error("Failed to fetch rejected events", err);
      }
    };
    fetchRejected();
  }, [user, token]);

  const handleDeleteRejected = async (eventId) => {
    if (!window.confirm("Are you sure you want to delete this rejected event?")) return;
    
    try {
      setDeletingId(eventId);
      await axios.delete(`http://localhost:5000/api/events/${eventId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRejectedEvents(rejectedEvents.filter(e => e.id !== eventId));
    } catch (err) {
      console.error("Failed to delete event", err);
      alert("Failed to delete event.");
    } finally {
      setDeletingId(null);
    }
  };

  const total = 10;
  const validatedCount = Object.values(events).flat().length;
  const progress = ((validatedCount / total) * 100).toFixed(1);

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-800">
          {user.department} Department — My Event Tracker
        </h1>
        <p className="text-gray-600">Progress: {validatedCount}/10</p>
      </div>

      <div className="w-full bg-gray-200 rounded-full h-3 mb-6">
        <div
          className="bg-blue-600 h-3 rounded-full transition-all"
          style={{ width: `${progress}%` }}
        ></div>
      </div>

      {/* ---------------------------
          Rejected Events - single section
          --------------------------- */}
      <div className="mb-8">
        <div className="bg-red-50 rounded-lg shadow-md p-5 border border-red-300">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xl font-semibold text-red-700">Rejected Events</h2>
            <p className="text-sm text-red-500">{rejectedEvents.length} rejected</p>
          </div>

          {rejectedEvents.length === 0 ? (
            <p className="text-gray-600 text-sm italic">No rejected events 🎉</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border text-sm">
                <thead className="bg-red-100">
                  <tr>
                    <th className="border px-3 py-2">Event Name</th>
                    <th className="border px-3 py-2">Date</th>
                    <th className="border px-3 py-2">Category</th>
                    <th className="border px-3 py-2">Reviewer Comment</th>
                    <th className="border px-3 py-2 text-center">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rejectedEvents.map((e) => (
                    <tr key={e.id} className="border-t hover:bg-red-50">
                      <td className="border px-3 py-2">{e.name}</td>
                      <td className="border px-3 py-2">{e.date || "N/A"}</td>
                      <td className="border px-3 py-2">{e.category}</td>
                      <td className="border px-3 py-2 text-red-600 font-medium">{e.comment}</td>
                      <td className="border px-3 py-2 text-center">
                        <div className="flex gap-2 justify-center">
                          <button
                            onClick={() => setSelectedEvent(e)}
                            className="bg-blue-600 text-white px-3 py-1 rounded-md text-sm hover:bg-blue-700"
                          >
                            View Details
                          </button>
                          <button
                            onClick={() => handleDeleteRejected(e.id)}
                            disabled={deletingId === e.id}
                            className="bg-red-600 text-white px-3 py-1 rounded-md text-sm hover:bg-red-700 disabled:bg-red-400"
                          >
                            {deletingId === e.id ? "Deleting..." : "Delete"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* ---------------------------
          Validated / categorized events (unchanged)
          --------------------------- */}
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
