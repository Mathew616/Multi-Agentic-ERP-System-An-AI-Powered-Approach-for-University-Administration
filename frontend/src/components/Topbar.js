// src/components/Topbar.js
import React, { useContext } from "react";
import { AuthContext } from "../context/AuthContext";

const Topbar = () => {
  const { user, logout } = useContext(AuthContext);

  const getRoleDisplay = () => {
    const roleMap = {
      student: "Student Portal",
      teacher: "Faculty Portal",
      iqc: "Administration Portal"
    };
    return roleMap[user?.role] || "Dashboard";
  };

  return (
    <header className="bg-white shadow-sm flex justify-between items-center px-8 py-4 border-b border-gray-200">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">
          {getRoleDisplay()}
        </h1>
        <p className="text-sm text-gray-500">
          Welcome back, {user?.username}
        </p>
      </div>

      <div className="flex items-center gap-4">
        <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium">
          {user?.role?.toUpperCase()}
        </span>
        <button
          onClick={logout}
          className="btn-danger text-sm px-4 py-2"
        >
          Sign Out
        </button>
      </div>
    </header>
  );
};

export default Topbar;
