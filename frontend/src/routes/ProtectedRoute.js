// src/routes/ProtectedRoute.js
import React, { useContext, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";

const ProtectedRoute = ({ children, roles }) => {
  const { user, token } = useContext(AuthContext);
  const [loading, setLoading] = useState(true);

  // Wait for user restoration
  useEffect(() => {
    const savedUser = localStorage.getItem("user");
    if (savedUser && !user) {
      try {
        const parsedUser = JSON.parse(savedUser);
        if (parsedUser) {
          // simulate auth restoration delay
          setTimeout(() => setLoading(false), 200);
        } else setLoading(false);
      } catch {
        setLoading(false);
      }
    } else {
      setLoading(false);
    }
  }, [user]);

  if (loading) return <div className="p-8 text-gray-500">Loading...</div>;

  if (!token || !user) {
    return <Navigate to="/" replace />;
  }

  if (roles && user && !roles.includes(user.role)) {
      return <Navigate to="/" replace />;
  }
  
  return children;
};

export default ProtectedRoute;
