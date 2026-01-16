// src/App.js
import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./routes/ProtectedRoute";
import Layout from "./components/Layout";

import Login from "./pages/Login";
import Upload from "./pages/Upload";
import Tracker from "./pages/Tracker";
import Validate from "./pages/Validate";
import Admin from "./pages/Admin";
import DepartmentTracker from "./pages/DepartmentTracker";
import StudentTracker from "./pages/StudentTracker";
import TeacherTracker from "./pages/TeacherTracker";
import TeacherUpload from "./pages/TeacherUpload";

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public route */}
          <Route path="/" element={<Login />} />

          {/* Student Routes */}
          <Route
            path="/upload"
            element={
              <ProtectedRoute roles={["student"]}>
                <Layout>
                  <Upload />
                </Layout>
              </ProtectedRoute>
            }
          />

          {/* Teacher / IQC Validation */}
          <Route
            path="/validate"
            element={
              <ProtectedRoute roles={["teacher", "iqc"]}>
                <Layout>
                  <Validate />
                </Layout>
              </ProtectedRoute>
            }
          />

          {/* IQC Admin */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute roles={["iqc"]}>
                <Layout>
                  <Admin />
                </Layout>
              </ProtectedRoute>
            }
          />

          {/* IQC Tracker Dashboard */}
          <Route
            path="/tracker"
            element={
              <ProtectedRoute roles={["iqc"]}>
                <Layout>
                  <Tracker />
                </Layout>
              </ProtectedRoute>
            }
          />

          {/* Department Detail View for IQC */}
          <Route
            path="/tracker/:dept"
            element={
              <ProtectedRoute roles={["iqc"]}>
                <Layout>
                  <DepartmentTracker />
                </Layout>
              </ProtectedRoute>
            }
          />
          
          {/* Student Tracker */}
          <Route
            path="/student/tracker"
            element={
              <ProtectedRoute roles={["student"]}>
                <Layout>
                  <StudentTracker />
                </Layout>
              </ProtectedRoute>
            }
          />

          {/* Teacher Tracker */}
          <Route
            path="/teacher/tracker"
            element={
              <ProtectedRoute roles={["teacher"]}>
                <Layout>
                  <TeacherTracker />
                </Layout>
              </ProtectedRoute>
            }
          />
          {/* Teacher Upload */}
          <Route
            path="/teacher/upload"
            element={
              <ProtectedRoute roles={["teacher"]}>
                <Layout>
                  <TeacherUpload />
                </Layout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
