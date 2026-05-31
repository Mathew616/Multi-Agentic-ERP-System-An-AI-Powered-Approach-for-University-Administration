import React, { useEffect, useState, useContext } from "react";
import axios from "axios";
import { AuthContext } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

export default function Tracker() {
  const { token } = useContext(AuthContext);
  const [progressData, setProgressData] = useState({});
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const fetchTracker = async () => {
    try {
      setLoading(true);
      const res = await axios.get("http://localhost:5000/api/tracker", {
        headers: { Authorization: "Bearer " + token },
      });
      setProgressData(res.data);
    } catch (err) {
      console.error("Failed to fetch tracker", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTracker();
  }, [token]);

  const getDeptDisplay = (dept) => {
    // Return clean department name
    return dept;
  };

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-semibold text-gray-900">Department Tracker</h1>
          <p className="text-gray-600 mt-1">Monitor validation progress across departments</p>
        </div>
        <button
          onClick={fetchTracker}
          disabled={loading}
          className={`px-5 py-2.5 rounded-lg font-medium transition-all duration-150 ${
            loading 
              ? "bg-gray-400 cursor-not-allowed text-white"
              : "btn-primary hover:shadow-md"
          }`}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {Object.keys(progressData).map((dept) => {
          const { total, validated, progress } = progressData[dept];
          const percentage = progress && !isNaN(progress) ? progress.toFixed(0) : 0;
          const barColor =
            percentage < 40
              ? "bg-red-500"
              : percentage < 75
              ? "bg-yellow-500"
              : "bg-green-600";

          return (
            <div
              key={dept}
              className="card cursor-pointer hover:shadow-lg transition-all duration-200 hover:-translate-y-1"
              onClick={() => navigate(`/tracker/${dept}`)}
            >
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  {dept}
                </h2>
                <span className="badge bg-gray-100 text-gray-700">
                  {percentage}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5 mb-4">
                <div
                  className={`${barColor} h-2.5 rounded-full transition-all duration-500`}
                  style={{ width: `${percentage}%` }}
                ></div>
              </div>
              <p className="text-sm text-gray-600">
                <span className="font-semibold text-gray-900">{validated}</span> of{" "}
                <span className="font-semibold text-gray-900">{total}</span> events validated
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
