import React, { useState, useEffect, useContext } from "react";
import axios from "axios";
import { AuthContext } from "../context/AuthContext";
import { Eye, EyeOff } from "lucide-react";

export default function Admin() {
  const { token } = useContext(AuthContext);
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({
    username: "",
    password: "",
    role: "student",
    department: "",
  });
  const [loading, setLoading] = useState(false);
  const [visiblePasswords, setVisiblePasswords] = useState({});

  const DEPARTMENTS = [
    { value: "", label: "-- Department (optional) --" },
    { value: "AIML", label: "Computer Science & Engineering - AIML" },
    { value: "CSE(Core)", label: "Computer Science & Engineering (Core)" },
    { value: "CSE-DS", label: "Computer Science & Engineering - Data Science" },
    { value: "CSE-CY", label: "Computer Science & Engineering - Cyber Security" },
    { value: "ISE", label: "Information Science & Engineering" },
    { value: "ECE", label: "Electronics & Communication Engineering" },
    { value: "AERO", label: "Aeronautical Engineering" },
  ];

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await axios.get("/api/auth/users", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUsers(res.data.users);
    } catch (err) {
      alert("Failed to fetch users");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post(
        "/api/auth/add_user",
        {
          username: form.username,
          password: form.password,
          role: form.role,
          department: form.department,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      alert(res.data.message);
      setUsers((prev) => [
        ...prev,
        {
          id: Math.random(),
          username: form.username,
          password: form.password,
          role: form.role,
          department: form.department,
        },
      ]);

      setForm({ username: "", password: "", role: "student", department: "" });
    } catch (err) {
      alert(err.response?.data?.message || "Failed to create user");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this user?")) return;
    try {
      await axios.delete(`/api/auth/users/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchUsers();
    } catch {
      alert("Failed to delete user");
    }
  };

  const handleSetPassword = async (id, password) => {
    try {
      const res = await axios.post(
        `/api/auth/users/${id}/set_password`,
        { password },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      alert(res.data.message);
      setUsers((prev) =>
        prev.map((u) =>
          u.id === id ? { ...u, password } : u
        )
      );
    } catch (err) {
      alert("Failed to set password");
    }
  };

  const togglePasswordVisibility = (id) => {
    setVisiblePasswords((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">IQC User Management</h1>

      <div className="bg-white p-4 rounded shadow mb-6">
        <h2 className="text-lg font-semibold mb-3">Add New User</h2>
        <form
          onSubmit={handleCreate}
          className="grid grid-cols-1 md:grid-cols-5 gap-3"
        >
          <input
            required
            placeholder="Username"
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            className="border px-3 py-2 rounded"
          />

          <input
            required
            placeholder="Password"
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="border px-3 py-2 rounded"
          />

          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="border px-3 py-2 rounded"
          >
            <option value="student">Student</option>
            <option value="teacher">Teacher</option>
            <option value="iqc">IQC</option>
          </select>

          <select
            value={form.department}
            onChange={(e) => setForm({ ...form, department: e.target.value })}
            className="border px-3 py-2 rounded"
          >
            {DEPARTMENTS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>

          <button
            type="submit"
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded"
          >
            Add User
          </button>
        </form>
      </div>

      <div className="bg-white p-4 rounded shadow">
        <h2 className="text-lg font-semibold mb-3">Existing Users</h2>
        {loading ? (
          <p>Loading...</p>
        ) : (
          <table className="w-full text-sm border">
            <thead className="bg-gray-100">
              <tr>
                <th className="p-2 text-left">Username</th>
                <th className="p-2 text-left">Role</th>
                <th className="p-2 text-left">Department</th>
                <th className="p-2 text-left">Password</th>
                <th className="p-2 text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t">
                  <td className="p-2">{u.username}</td>
                  <td className="p-2">{u.role}</td>
                  <td className="p-2">{u.department || "-"}</td>
                  <td className="p-2 flex items-center space-x-2">
                    <span>
                      {visiblePasswords[u.id]
                        ? (u.plain_password || u.password || "N/A")
                        : "••••••••"}
                    </span>
                    <button
                      onClick={() => togglePasswordVisibility(u.id)}
                      className="text-gray-600 hover:text-black"
                    >
                      {visiblePasswords[u.id] ? (
                        <EyeOff size={18} />
                      ) : (
                        <Eye size={18} />
                      )}
                    </button>
                  </td>
                  <td className="p-2 text-center">
                    <button
                      onClick={() => {
                        const newPassword = prompt(
                          `Enter a new password for ${u.username}:`
                        );
                        if (newPassword) handleSetPassword(u.id, newPassword);
                      }}
                      className="bg-yellow-500 text-white px-3 py-1 rounded mr-2"
                    >
                      Set Password
                    </button>
                    <button
                      onClick={() => handleDelete(u.id)}
                      className="bg-red-500 text-white px-3 py-1 rounded"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
