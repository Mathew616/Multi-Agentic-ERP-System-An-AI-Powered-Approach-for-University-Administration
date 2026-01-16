// src/components/Topbar.js
import React, { useContext } from "react";
import { AuthContext } from "../context/AuthContext";

const Topbar = () => {
  const { user, logout } = useContext(AuthContext);

  return (
    <header className="bg-white shadow flex justify-between items-center px-6 py-3 border-b border-gray-200">
      <h1 className="text-lg font-semibold text-gray-700">
        {user?.role === "student" && "Student Dashboard"}
        {user?.role === "teacher" && "Teacher Dashboard"}
        {user?.role === "iqc" && "IQC Admin Dashboard"}
      </h1>

      <div className="flex items-center gap-3">
        <span className="text-gray-600 font-medium">
          {user?.username?.toUpperCase()}
        </span>
        <button
          onClick={logout}
          className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded-md transition"
        >
          Logout
        </button>
      </div>
    </header>
  );
};

export default Topbar;
