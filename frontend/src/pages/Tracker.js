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

  const getEmoji = (dept) => {
    switch (dept) {
      case "AIML":
        return "🤖";
      case "CSE(Core)":
        return "💻";
      case "CSE-DS":
        return "📊";
      case "CSE-CY":
        return "🔐";
      case "ISE":
        return "⚙️";
      case "ECE":
        return "📡";
      case "AERO":
        return "✈️";
      default:
        return "🏫";
    }
  };

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">IQC Department Tracker</h1>
        <button
          onClick={fetchTracker}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
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
              className="p-6 bg-white border border-gray-200 rounded-2xl shadow-md cursor-pointer hover:shadow-lg transition transform hover:-translate-y-1"
              onClick={() => navigate(`/tracker/${dept}`)}
            >
              <div className="flex justify-between items-center mb-3">
                <h2 className="text-xl font-semibold text-gray-800">
                  {getEmoji(dept)} {dept}
                </h2>
                <span className="text-sm text-gray-500 font-medium">
                  {percentage}% done
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3 mb-3">
                <div
                  className={`${barColor} h-3 rounded-full transition-all duration-500`}
                  style={{ width: `${percentage}%` }}
                ></div>
              </div>
              <p className="text-sm text-gray-700 font-medium">
                {validated} of {total} events validated
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
