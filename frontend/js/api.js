/**
 * API Client for One-Click Attendance System with JWT Authentication
 */

const isSeparateFrontendPort = ['3000', '5500', '5173', '8080'].includes(window.location.port) || window.location.protocol === 'file:';
const DEFAULT_HOST = isSeparateFrontendPort ? 'http://127.0.0.1:8000' : (window.location.origin || 'http://127.0.0.1:8000');

const API_BASE_URL = `${DEFAULT_HOST}/api/v1`;
const AUTH_BASE_URL = `${DEFAULT_HOST}/auth`;
const HEALTH_URL = `${DEFAULT_HOST}/health`;

const Api = {
  getToken() {
    return localStorage.getItem('token');
  },

  setToken(token) {
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
  },

  getUser() {
    const raw = localStorage.getItem('user');
    return raw ? JSON.parse(raw) : null;
  },

  setUser(user) {
    if (user) {
      localStorage.setItem('user', JSON.stringify(user));
    } else {
      localStorage.removeItem('user');
    }
  },

  logout() {
    this.setToken(null);
    this.setUser(null);
  },

  getAuthHeaders() {
    const headers = {};
    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  },

  /** Check backend connectivity */
  async checkHealth() {
    try {
      const response = await fetch(HEALTH_URL, { method: 'GET' });
      return response.ok;
    } catch (e) {
      return false;
    }
  },

  /** User Login */
  async login(username, password) {
    const res = await fetch(`${AUTH_BASE_URL}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || 'Invalid username or password');
    }

    const data = await res.json();
    this.setToken(data.access_token);
    this.setUser(data.user);
    return data;
  },

  /** User Registration */
  async register(userData) {
    const res = await fetch(`${AUTH_BASE_URL}/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userData),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
      throw new Error(err.detail || 'Registration failed');
    }

    return await res.json();
  },

  /** Fetch currently authenticated user */
  async getMe() {
    const token = this.getToken();
    if (!token) return null;

    const res = await fetch(`${AUTH_BASE_URL}/me`, {
      headers: this.getAuthHeaders(),
    });

    if (!res.ok) {
      this.logout();
      return null;
    }

    const user = await res.json();
    this.setUser(user);
    return user;
  },

  // ==========================================
  // ADMIN PORTAL APIS
  // ==========================================

  /** Admin portal stats */
  async getAdminStats() {
    const res = await fetch(`${API_BASE_URL}/admin/dashboard-stats`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch admin stats' }));
      throw new Error(err.detail || 'Failed to fetch admin stats');
    }
    return await res.json();
  },

  // --- Classes ---
  async listClasses() {
    const res = await fetch(`${API_BASE_URL}/admin/classes`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch classes' }));
      throw new Error(err.detail || 'Failed to fetch classes');
    }
    return await res.json();
  },

  async createClass(data) {
    const res = await fetch(`${API_BASE_URL}/admin/classes`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create class' }));
      throw new Error(err.detail || 'Failed to create class');
    }
    return await res.json();
  },

  async updateClass(classId, data) {
    const res = await fetch(`${API_BASE_URL}/admin/classes/${classId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update class' }));
      throw new Error(err.detail || 'Failed to update class');
    }
    return await res.json();
  },

  async deleteClass(classId) {
    const res = await fetch(`${API_BASE_URL}/admin/classes/${classId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete class' }));
      throw new Error(err.detail || 'Failed to delete class');
    }
    return true;
  },

  async assignClassTeacher(classId, teacherId) {
    const res = await fetch(`${API_BASE_URL}/admin/classes/${classId}/assign-teacher`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify({ class_teacher_id: teacherId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to assign class teacher' }));
      throw new Error(err.detail || 'Failed to assign class teacher');
    }
    return await res.json();
  },

  // --- Subjects ---
  async listSubjects() {
    const res = await fetch(`${API_BASE_URL}/admin/subjects`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch subjects' }));
      throw new Error(err.detail || 'Failed to fetch subjects');
    }
    return await res.json();
  },

  async createSubject(data) {
    const res = await fetch(`${API_BASE_URL}/admin/subjects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create subject' }));
      throw new Error(err.detail || 'Failed to create subject');
    }
    return await res.json();
  },

  async updateSubject(subjectId, data) {
    const res = await fetch(`${API_BASE_URL}/admin/subjects/${subjectId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update subject' }));
      throw new Error(err.detail || 'Failed to update subject');
    }
    return await res.json();
  },

  async deleteSubject(subjectId) {
    const res = await fetch(`${API_BASE_URL}/admin/subjects/${subjectId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete subject' }));
      throw new Error(err.detail || 'Failed to delete subject');
    }
    return true;
  },

  // --- Teachers ---
  async listTeachers() {
    const res = await fetch(`${API_BASE_URL}/admin/teachers`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch teachers' }));
      throw new Error(err.detail || 'Failed to fetch teachers');
    }
    return await res.json();
  },

  async createTeacher(data) {
    const res = await fetch(`${API_BASE_URL}/admin/teachers`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create teacher' }));
      throw new Error(err.detail || 'Failed to create teacher');
    }
    return await res.json();
  },

  async updateTeacher(teacherId, data) {
    const res = await fetch(`${API_BASE_URL}/admin/teachers/${teacherId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update teacher' }));
      throw new Error(err.detail || 'Failed to update teacher');
    }
    return await res.json();
  },

  async deleteTeacher(teacherId) {
    const res = await fetch(`${API_BASE_URL}/admin/teachers/${teacherId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete teacher' }));
      throw new Error(err.detail || 'Failed to delete teacher');
    }
    return true;
  },

  // --- Assignments ---
  async listAssignments(filters = {}) {
    const query = new URLSearchParams(filters).toString();
    const url = query ? `${API_BASE_URL}/admin/assignments?${query}` : `${API_BASE_URL}/admin/assignments`;
    const res = await fetch(url, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch assignments' }));
      throw new Error(err.detail || 'Failed to fetch assignments');
    }
    return await res.json();
  },

  async createAssignment(data) {
    const res = await fetch(`${API_BASE_URL}/admin/assignments`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to assign teacher' }));
      throw new Error(err.detail || 'Failed to assign teacher');
    }
    return await res.json();
  },

  async deleteAssignment(assignmentId) {
    const res = await fetch(`${API_BASE_URL}/admin/assignments/${assignmentId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to remove assignment' }));
      throw new Error(err.detail || 'Failed to remove assignment');
    }
    return true;
  },

  // --- Students ---
  async listStudents(filters = {}) {
    const query = new URLSearchParams(filters).toString();
    const url = query ? `${API_BASE_URL}/admin/students?${query}` : `${API_BASE_URL}/admin/students`;
    const res = await fetch(url, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch students' }));
      throw new Error(err.detail || 'Failed to fetch students');
    }
    return await res.json();
  },

  async createStudent(studentData) {
    const res = await fetch(`${API_BASE_URL}/admin/students`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(studentData),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create student' }));
      throw new Error(err.detail || 'Failed to create student');
    }
    return await res.json();
  },

  async updateStudent(studentId, data) {
    const res = await fetch(`${API_BASE_URL}/admin/students/${studentId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update student' }));
      throw new Error(err.detail || 'Failed to update student');
    }
    return await res.json();
  },

  async deleteStudent(studentId) {
    const res = await fetch(`${API_BASE_URL}/admin/students/${studentId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete student' }));
      throw new Error(err.detail || 'Failed to delete student');
    }
    return true;
  },

  // --- Attendance Records View & Management ---
  async listAttendanceRecords(filters = {}) {
    const cleanFilters = {};
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') {
        cleanFilters[key] = value;
      }
    }
    const query = new URLSearchParams(cleanFilters).toString();
    const url = query ? `${API_BASE_URL}/admin/attendance?${query}` : `${API_BASE_URL}/admin/attendance`;
    const res = await fetch(url, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch attendance records' }));
      throw new Error(err.detail || 'Failed to fetch attendance records');
    }
    return await res.json();
  },

  async createAttendanceRecord(data) {
    const res = await fetch(`${API_BASE_URL}/admin/attendance`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create attendance record' }));
      throw new Error(err.detail || 'Failed to create attendance record');
    }
    return await res.json();
  },

  async deleteAttendanceRecord(recordId) {
    const res = await fetch(`${API_BASE_URL}/admin/attendance/${recordId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete attendance record' }));
      throw new Error(err.detail || 'Failed to delete attendance record');
    }
    return true;
  },

  // ==========================================
  // CLASS TEACHER PORTAL APIS
  // ==========================================

  /** Get assigned class details and metrics */
  async getMyAssignedClass(classId = null) {
    const url = classId 
      ? `${API_BASE_URL}/teachers/class-teacher/my-class?class_id=${classId}`
      : `${API_BASE_URL}/teachers/class-teacher/my-class`;
    const res = await fetch(url, { headers: this.getAuthHeaders() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch assigned class' }));
      throw new Error(err.detail || 'Failed to fetch assigned class');
    }
    return await res.json();
  },

  /** Get student list for assigned class with optional filters */
  async getClassStudents(params = {}) {
    const query = new URLSearchParams();
    if (params.class_id) query.append('class_id', params.class_id);
    if (params.search) query.append('search', params.search);
    if (params.status) query.append('status', params.status);
    if (params.face_status) query.append('face_status', params.face_status);

    const queryString = query.toString() ? `?${query.toString()}` : '';
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/students${queryString}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch student list' }));
      throw new Error(err.detail || 'Failed to fetch student list');
    }
    return await res.json();
  },

  /** Add a student to assigned class */
  async addClassStudent(studentData, classId = null) {
    const url = classId
      ? `${API_BASE_URL}/teachers/class-teacher/students?class_id=${classId}`
      : `${API_BASE_URL}/teachers/class-teacher/students`;
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(studentData),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to add student' }));
      throw new Error(err.detail || 'Failed to add student');
    }
    return await res.json();
  },

  /** Get student details */
  async getClassStudent(studentId) {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/students/${studentId}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch student' }));
      throw new Error(err.detail || 'Failed to fetch student details');
    }
    return await res.json();
  },

  /** Edit student information */
  async editClassStudent(studentId, studentData) {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/students/${studentId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(studentData),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update student' }));
      throw new Error(err.detail || 'Failed to update student');
    }
    return await res.json();
  },

  /** Toggle student active/inactive status */
  async toggleClassStudentStatus(studentId) {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/students/${studentId}/toggle-status`, {
      method: 'PATCH',
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to toggle student status' }));
      throw new Error(err.detail || 'Failed to toggle student status');
    }
    return await res.json();
  },

  /** Delete student from class */
  async deleteClassStudent(studentId) {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/students/${studentId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete student' }));
      throw new Error(err.detail || 'Failed to delete student');
    }
    return true;
  },

  /** Upload and enroll student face photo via Computer Vision pipeline */
  async uploadStudentFace(studentId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE_URL}/students/${studentId}/face`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to upload face photo' }));
      throw new Error(err.detail || err.message || 'Failed to upload face photo');
    }
    return await res.json();
  },

  /** Get student face enrollment status */
  async getStudentFaceStatus(studentId) {
    const res = await fetch(`${API_BASE_URL}/students/${studentId}/face`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to get face status' }));
      throw new Error(err.detail || err.message || 'Failed to fetch face enrollment status');
    }
    return await res.json();
  },

  /** Get class attendance summary */
  async getClassAttendanceSummary(classId = null) {
    const url = classId
      ? `${API_BASE_URL}/teachers/class-teacher/attendance-summary?class_id=${classId}`
      : `${API_BASE_URL}/teachers/class-teacher/attendance-summary`;
    const res = await fetch(url, { headers: this.getAuthHeaders() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch attendance summary' }));
      throw new Error(err.detail || 'Failed to fetch attendance summary');
    }
    return await res.json();
  },

  /** Get all subject teachers */
  async getClassTeacherSubjectTeachers() {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/subject-teachers`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch subject teachers' }));
      throw new Error(err.detail || 'Failed to fetch subject teachers');
    }
    return await res.json();
  },

  /** Get available classes and subjects for assignment */
  async getAvailableAssignmentOptions() {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/available-assignment-options`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch options' }));
      throw new Error(err.detail || 'Failed to fetch options');
    }
    return await res.json();
  },

  /** Create a subject teacher */
  async createSubjectTeacher(data) {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/subject-teachers`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create subject teacher' }));
      throw new Error(err.detail || 'Failed to create subject teacher');
    }
    return await res.json();
  },

  /** Get a single subject teacher details */
  async getSubjectTeacherDetail(id) {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/subject-teachers/${id}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch teacher details' }));
      throw new Error(err.detail || 'Failed to fetch teacher details');
    }
    return await res.json();
  },

  /** Update subject teacher details & assignments */
  async updateSubjectTeacher(id, data) {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/subject-teachers/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update subject teacher' }));
      throw new Error(err.detail || 'Failed to update subject teacher');
    }
    return await res.json();
  },

  /** Toggle active / deactivated status */
  async toggleSubjectTeacherStatus(id) {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/subject-teachers/${id}/toggle-status`, {
      method: 'PATCH',
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to toggle status' }));
      throw new Error(err.detail || 'Failed to toggle status');
    }
    return await res.json();
  },

  /** Assign subject teacher to class & subject */
  async assignSubjectTeacherToClass(id, assignment) {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/subject-teachers/${id}/assignments`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(assignment),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to assign course' }));
      throw new Error(err.detail || 'Failed to assign course');
    }
    return await res.json();
  },

  /** Remove assignment from subject teacher */
  async removeSubjectTeacherAssignment(id, assignmentId) {
    const res = await fetch(`${API_BASE_URL}/teachers/class-teacher/subject-teachers/${id}/assignments/${assignmentId}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to remove assignment' }));
      throw new Error(err.detail || 'Failed to remove assignment');
    }
    return await res.json();
  },

  // ==========================================
  // OTHER PORTALS & UTILITIES
  // ==========================================

  /** Class teacher overview */
  async getClassTeacherOverview(dept = 'Computer Science', year = 3, section = 'A') {
    const res = await fetch(
      `${API_BASE_URL}/teachers/class-teacher/overview?department=${encodeURIComponent(dept)}&year=${year}&section=${encodeURIComponent(section)}`,
      { headers: this.getAuthHeaders() }
    );
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch class overview' }));
      throw new Error(err.detail || 'Failed to fetch class teacher overview');
    }
    return await res.json();
  },

  /** Subject teacher assigned classes */
  async getSubjectTeacherClasses() {
    const res = await fetch(`${API_BASE_URL}/teachers/subject-teacher/classes`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch subject classes' }));
      throw new Error(err.detail || 'Failed to fetch subject classes');
    }
    return await res.json();
  },

  /** Upload classroom group photo for one-click attendance */
  async uploadClassroomPhoto(formData) {
    const res = await fetch(`${API_BASE_URL}/attendance/process-classroom-photo`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to process classroom photo');
    return await res.json();
  },

  /** Analyze classroom photo with Computer Vision without saving attendance */
  async analyzeClassroomPhoto(formData) {
    const res = await fetch(`${API_BASE_URL}/attendance/analyze`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to analyze classroom photo' }));
      throw new Error(err.detail || err.message || 'Failed to analyze classroom photo');
    }
    return await res.json();
  },

  /** Confirm and save verified attendance records */
  async confirmAttendance(confirmedRecords) {
    const res = await fetch(`${API_BASE_URL}/attendance/confirm`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify({ confirmed_records: confirmedRecords }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to confirm attendance' }));
      throw new Error(err.detail || err.message || 'Failed to confirm attendance');
    }
    return await res.json();
  },

  // ==========================================
  // ATTENDANCE REPORTS & CSV EXPORT
  // ==========================================

  /** General Attendance Reports Dispatcher */
  async getReports(params = {}) {
    const query = this._cleanParams(params);
    const res = await fetch(`${API_BASE_URL}/attendance/reports?${query}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch attendance reports');
    return await res.json();
  },

  /** 1. Daily Attendance Report */
  async getDailyReport(params = {}) {
    const query = this._cleanParams(params);
    const res = await fetch(`${API_BASE_URL}/attendance/reports/daily?${query}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch daily report' }));
      throw new Error(err.detail || 'Failed to fetch daily attendance report');
    }
    return await res.json();
  },

  /** 2. Student Attendance Report */
  async getStudentReport(params = {}) {
    const query = this._cleanParams(params);
    const res = await fetch(`${API_BASE_URL}/attendance/reports/student?${query}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch student report' }));
      throw new Error(err.detail || 'Failed to fetch student attendance report');
    }
    return await res.json();
  },

  /** 3. Subject Attendance Report */
  async getSubjectReport(params = {}) {
    const query = this._cleanParams(params);
    const res = await fetch(`${API_BASE_URL}/attendance/reports/subject?${query}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch subject report' }));
      throw new Error(err.detail || 'Failed to fetch subject attendance report');
    }
    return await res.json();
  },

  /** 4. Class Attendance Report */
  async getClassReport(params = {}) {
    const query = this._cleanParams(params);
    const res = await fetch(`${API_BASE_URL}/attendance/reports/class?${query}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch class report' }));
      throw new Error(err.detail || 'Failed to fetch class attendance report');
    }
    return await res.json();
  },

  /** 5. Monthly Attendance Report */
  async getMonthlyReport(params = {}) {
    const query = this._cleanParams(params);
    const res = await fetch(`${API_BASE_URL}/attendance/reports/monthly?${query}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to fetch monthly report' }));
      throw new Error(err.detail || 'Failed to fetch monthly attendance report');
    }
    return await res.json();
  },

  /** Unified Report Getter */
  async getAttendanceReport(reportType = 'daily', params = {}) {
    const cleanType = (reportType || 'daily').toLowerCase().trim();
    if (cleanType === 'daily') return this.getDailyReport(params);
    if (cleanType === 'student') return this.getStudentReport(params);
    if (cleanType === 'subject') return this.getSubjectReport(params);
    if (cleanType === 'class') return this.getClassReport(params);
    if (cleanType === 'monthly') return this.getMonthlyReport(params);
    return this.getReports({ report_type: cleanType, ...params });
  },

  /** Helper to construct direct CSV Export URL */
  getReportCsvUrl(reportType = 'daily', params = {}) {
    const clean = { report_type: reportType, ...params };
    const query = this._cleanParams(clean);
    return `${API_BASE_URL}/attendance/reports/export-csv?${query}`;
  },

  /** Trigger CSV Export Download */
  async downloadReportCsv(reportType = 'daily', params = {}) {
    const query = this._cleanParams({ report_type: reportType, ...params });
    const res = await fetch(`${API_BASE_URL}/attendance/reports/export-csv?${query}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to export CSV' }));
      throw new Error(err.detail || 'Failed to export CSV');
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    const nowStr = new Date().toISOString().split('T')[0];
    a.download = `attendance_${reportType}_report_${nowStr}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  /** Helper to strip empty/null/undefined query params */
  _cleanParams(params = {}) {
    const clean = {};
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        clean[key] = value;
      }
    }
    return new URLSearchParams(clean).toString();
  },

  /** Class Teacher Attendance Dashboard */
  async getClassTeacherAttendanceDashboard(params = {}) {
    const query = this._cleanParams(params);
    const res = await fetch(`${API_BASE_URL}/attendance/dashboard/class-teacher?${query}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to load class teacher dashboard' }));
      throw new Error(err.detail || err.message || 'Failed to load class teacher dashboard');
    }
    return await res.json();
  },

  /** Subject Teacher Attendance Dashboard */
  async getSubjectTeacherAttendanceDashboard(params = {}) {
    const query = this._cleanParams(params);
    const res = await fetch(`${API_BASE_URL}/attendance/dashboard/subject-teacher?${query}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to load subject teacher dashboard' }));
      throw new Error(err.detail || err.message || 'Failed to load subject teacher dashboard');
    }
    return await res.json();
  },

  /** Admin Attendance Dashboard */
  async getAdminAttendanceDashboard(params = {}) {
    const query = this._cleanParams(params);
    const res = await fetch(`${API_BASE_URL}/attendance/dashboard/admin?${query}`, {
      headers: this.getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to load admin attendance dashboard' }));
      throw new Error(err.detail || err.message || 'Failed to load admin attendance dashboard');
    }
    return await res.json();
  },

  // ==========================================
  // TEACHER PORTAL APIs (/api/v1/teacher-portal)
  // ==========================================
  _tp(path) { return `${API_BASE_URL}/teacher-portal${path}`; },

  async tpDashboard() {
    const res = await fetch(this._tp('/dashboard'), { headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpMyClasses() {
    const res = await fetch(this._tp('/my-classes'), { headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpListAssignments(filters = {}) {
    const q = new URLSearchParams(this._cleanParams(filters)).toString();
    const res = await fetch(this._tp(`/assignments${q ? '?' + q : ''}`), { headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpCreateAssignment(data) {
    const res = await fetch(this._tp('/assignments'), { method: 'POST', headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() }, body: JSON.stringify(data) });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpUpdateAssignment(id, data) {
    const res = await fetch(this._tp(`/assignments/${id}`), { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() }, body: JSON.stringify(data) });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpDeleteAssignment(id) {
    const res = await fetch(this._tp(`/assignments/${id}`), { method: 'DELETE', headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return true;
  },
  async tpListSubmissions(aid, filters = {}) {
    const q = new URLSearchParams(this._cleanParams(filters)).toString();
    const res = await fetch(this._tp(`/assignments/${aid}/submissions${q ? '?' + q : ''}`), { headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpGradeSubmission(aid, sid, data) {
    const res = await fetch(this._tp(`/assignments/${aid}/submissions/${sid}/grade`), { method: 'PATCH', headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() }, body: JSON.stringify(data) });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpListOnlineClasses(filters = {}) {
    const q = new URLSearchParams(this._cleanParams(filters)).toString();
    const res = await fetch(this._tp(`/online-classes${q ? '?' + q : ''}`), { headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpCreateOnlineClass(data) {
    const res = await fetch(this._tp('/online-classes'), { method: 'POST', headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() }, body: JSON.stringify(data) });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpDeleteOnlineClass(id) {
    const res = await fetch(this._tp(`/online-classes/${id}`), { method: 'DELETE', headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return true;
  },
  async tpListMaterials(filters = {}) {
    const q = new URLSearchParams(this._cleanParams(filters)).toString();
    const res = await fetch(this._tp(`/study-materials${q ? '?' + q : ''}`), { headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpCreateMaterial(data) {
    const res = await fetch(this._tp('/study-materials'), { method: 'POST', headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() }, body: JSON.stringify(data) });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpDeleteMaterial(id) {
    const res = await fetch(this._tp(`/study-materials/${id}`), { method: 'DELETE', headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return true;
  },
  async tpGetTimetable(filters = {}) {
    const q = new URLSearchParams(this._cleanParams(filters)).toString();
    const res = await fetch(this._tp(`/timetable${q ? '?' + q : ''}`), { headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpGetCalendar() {
    const res = await fetch(this._tp('/calendar'), { headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpCreateEvent(data) {
    const res = await fetch(this._tp('/calendar/events'), { method: 'POST', headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() }, body: JSON.stringify(data) });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpListAnnouncements() {
    const res = await fetch(this._tp('/announcements'), { headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpCreateAnnouncement(data) {
    const res = await fetch(this._tp('/announcements'), { method: 'POST', headers: { 'Content-Type': 'application/json', ...this.getAuthHeaders() }, body: JSON.stringify(data) });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },
  async tpDeleteAnnouncement(id) {
    const res = await fetch(this._tp(`/announcements/${id}`), { method: 'DELETE', headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return true;
  },
  async tpGetPerformance(filters = {}) {
    const q = new URLSearchParams(this._cleanParams(filters)).toString();
    const res = await fetch(this._tp(`/student-performance${q ? '?' + q : ''}`), { headers: this.getAuthHeaders() });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed');
    return res.json();
  },

  // ─────────────────────────────────────────────────────────────────
  // STUDENT PORTAL API METHODS
  // ─────────────────────────────────────────────────────────────────
  studentPortal: {
    _sp(path) { return `${API_BASE_URL}/student-portal${path}`; },
    _h() { return Api.getAuthHeaders(); },

    async getProfile(studentId = null) {
      const q = studentId ? `?student_id=${studentId}` : '';
      const res = await fetch(this._sp(`/me${q}`), { headers: this._h() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to load profile');
      return res.json();
    },

    async getAttendance(studentId = null) {
      const q = studentId ? `?student_id=${studentId}` : '';
      const res = await fetch(this._sp(`/attendance${q}`), { headers: this._h() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to load attendance');
      return res.json();
    },

    async getTimetable(studentId = null) {
      const q = studentId ? `?student_id=${studentId}` : '';
      const res = await fetch(this._sp(`/timetable${q}`), { headers: this._h() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to load timetable');
      return res.json();
    },

    async getAssignments(studentId = null) {
      const q = studentId ? `?student_id=${studentId}` : '';
      const res = await fetch(this._sp(`/assignments${q}`), { headers: this._h() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to load assignments');
      return res.json();
    },

    async submitAssignment(assignmentId, submissionText = null, uploadedFile = null, studentId = null) {
      const params = new URLSearchParams();
      if (submissionText) params.append('submission_text', submissionText);
      if (uploadedFile) params.append('uploaded_file', uploadedFile);
      if (studentId) params.append('student_id', studentId);
      const q = params.toString() ? '?' + params.toString() : '';
      const res = await fetch(this._sp(`/assignments/${assignmentId}/submit${q}`), {
        method: 'POST',
        headers: this._h(),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Submission failed');
      return res.json();
    },

    async getGrades(studentId = null) {
      const q = studentId ? `?student_id=${studentId}` : '';
      const res = await fetch(this._sp(`/grades${q}`), { headers: this._h() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to load grades');
      return res.json();
    },

    async getAnnouncements(studentId = null) {
      const q = studentId ? `?student_id=${studentId}` : '';
      const res = await fetch(this._sp(`/announcements${q}`), { headers: this._h() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to load announcements');
      return res.json();
    },

    async getMaterials(studentId = null) {
      const q = studentId ? `?student_id=${studentId}` : '';
      const res = await fetch(this._sp(`/materials${q}`), { headers: this._h() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to load materials');
      return res.json();
    },

    async getEvents() {
      const res = await fetch(this._sp('/events'), { headers: this._h() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to load events');
      return res.json();
    },

    async getNotifications() {
      const res = await fetch(this._sp('/notifications'), { headers: this._h() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to load notifications');
      return res.json();
    },

    async markNotificationRead(id) {
      const res = await fetch(this._sp(`/notifications/${id}/read`), { method: 'POST', headers: this._h() });
      if (!res.ok) throw new Error('Failed');
      return res.json();
    },
  },
};

window.Api = Api;
