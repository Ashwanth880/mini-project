/**
 * Application Navigation, Authentication & Interaction Logic
 * Includes Full Admin Portal Operations & Role-Based Workflows
 */

// Global cached datasets for admin interactions
let adminCachedData = {
  classes: [],
  subjects: [],
  teachers: [],
  students: [],
  assignments: [],
  attendance: [],
};

document.addEventListener('DOMContentLoaded', async () => {
  initAuthUI();
  initNavigation();
  initBackendStatusCheck();
  initFormHandlers();
  initAdminPortal();
  initClassTeacherPortal();
  initSubjectTeacherPortal();
  initAttendanceDashboards();

  // Check if session token exists
  await checkCurrentSession();
});


/** Quick fill helper for testing credentials */
function fillLogin(username, password) {
  const uInput = document.getElementById('login-username');
  const pInput = document.getElementById('login-password');
  if (uInput && pInput) {
    uInput.value = username;
    pInput.value = password;
  }
}
window.fillLogin = fillLogin;

/** Authentication UI toggles and form submissions */
function initAuthUI() {
  const loginForm = document.getElementById('login-form');
  const registerForm = document.getElementById('register-form');
  const toggleToReg = document.getElementById('toggle-to-register');
  const toggleToLogin = document.getElementById('toggle-to-login');
  const btnLogout = document.getElementById('btn-logout');

  // Toggle between Login and Register
  if (toggleToReg && toggleToLogin && loginForm && registerForm) {
    toggleToReg.addEventListener('click', (e) => {
      e.preventDefault();
      loginForm.classList.add('d-none');
      registerForm.classList.remove('d-none');
      hideAuthAlert();
    });

    toggleToLogin.addEventListener('click', (e) => {
      e.preventDefault();
      registerForm.classList.add('d-none');
      loginForm.classList.remove('d-none');
      hideAuthAlert();
    });
  }

  // Handle Login Submission
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const u = document.getElementById('login-username').value.trim();
      const p = document.getElementById('login-password').value;
      const submitBtn = document.getElementById('btn-login-submit');

      hideAuthAlert();
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Signing In...';

      try {
        const data = await Api.login(u, p);
        applyAuthenticatedState(data.user);
      } catch (err) {
        showAuthAlert(err.message || 'Login failed. Please check credentials.');
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="bi bi-box-arrow-in-right me-1"></i>Sign In';
      }
    });
  }

  // Handle Registration Submission
  if (registerForm) {
    registerForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        full_name: document.getElementById('reg-fullname').value.trim(),
        username: document.getElementById('reg-username').value.trim(),
        role: document.getElementById('reg-role').value,
        email: document.getElementById('reg-email').value.trim(),
        department: document.getElementById('reg-dept').value.trim(),
        password: document.getElementById('reg-pwd').value,
      };

      try {
        await Api.register(payload);
        showAdminAlert(`User '${payload.username}' registered successfully! Please sign in.`, 'success');
        registerForm.reset();
        registerForm.classList.add('d-none');
        loginForm.classList.remove('d-none');
        fillLogin(payload.username, payload.password);
      } catch (err) {
        showAuthAlert(err.message || 'Registration failed');
      }
    });
  }

  // Handle Logout
  if (btnLogout) {
    btnLogout.addEventListener('click', (e) => {
      e.preventDefault();
      Api.logout();
      showLoginView();
    });
  }
}

function showAuthAlert(msg) {
  const alertEl = document.getElementById('auth-alert');
  if (alertEl) {
    alertEl.textContent = msg;
    alertEl.classList.remove('d-none');
  }
}

function hideAuthAlert() {
  const alertEl = document.getElementById('auth-alert');
  if (alertEl) {
    alertEl.classList.add('d-none');
  }
}

/** Check existing JWT token on load */
async function checkCurrentSession() {
  const user = await Api.getMe();
  if (user) {
    applyAuthenticatedState(user);
  } else {
    showLoginView();
  }
}

function showLoginView() {
  const authContainer = document.getElementById('auth-container');
  const appContainer = document.getElementById('app-container');
  if (authContainer) authContainer.classList.remove('d-none');
  if (appContainer) appContainer.classList.add('d-none');
}

/** Transition UI into authenticated user state with role-based routing */
function applyAuthenticatedState(user) {
  const authContainer = document.getElementById('auth-container');
  const appContainer = document.getElementById('app-container');
  const headerName = document.getElementById('header-user-name');
  const headerRole = document.getElementById('header-user-role');
  const dropdownEmail = document.getElementById('dropdown-user-email');

  if (authContainer) authContainer.classList.add('d-none');
  if (appContainer) appContainer.classList.remove('d-none');

  if (headerName) headerName.textContent = user.full_name;
  if (dropdownEmail) dropdownEmail.textContent = `${user.email} (${user.department || 'General'})`;

  if (headerRole) {
    headerRole.textContent = user.role;
    if (user.role === 'ADMIN') {
      headerRole.className = 'badge bg-danger';
    } else if (user.role === 'CLASS_TEACHER') {
      headerRole.className = 'badge bg-primary';
    } else {
      headerRole.className = 'badge bg-info';
    }
  }

  // Filter sidebar items according to user role
  applyRoleNavigation(user.role);

  // Auto redirect to role-specific dashboard
  redirectRoleDashboard(user.role);

  // Load authorized dashboard metrics
  loadRoleDashboardData(user.role);

  // If Admin, load all admin portal datasets
  if (user.role === 'ADMIN') {
    loadAdminData();
  } else if (user.role === 'CLASS_TEACHER') {
    loadClassTeacherData();
  } else if (user.role === 'SUBJECT_TEACHER') {
    loadSubjectTeacherData();
  }
}

/** Role-based sidebar menu filtering */
function applyRoleNavigation(role) {
  const roleNavItems = document.querySelectorAll('.sidebar-nav li[data-role-req]');
  roleNavItems.forEach(item => {
    const required = item.getAttribute('data-role-req');
    if (required === 'ALL') {
      item.classList.remove('d-none');
    } else if (required.includes(role)) {
      item.classList.remove('d-none');
    } else {
      item.classList.add('d-none');
    }
  });
}

/** Auto redirect to appropriate portal dashboard upon login */
function redirectRoleDashboard(role) {
  let targetSection = 'dashboard-section';
  if (role === 'ADMIN') {
    targetSection = 'admin-section';
  } else if (role === 'CLASS_TEACHER') {
    targetSection = 'class-teacher-section';
  } else if (role === 'SUBJECT_TEACHER') {
    targetSection = 'subject-teacher-section';
  } else if (role === 'STUDENT') {
    targetSection = 'student-portal-section';
  }

  const link = document.querySelector(`.sidebar-nav .nav-link[data-target="${targetSection}"]`);
  if (link) {
    link.click();
  }
}

/** Navigation handling between portals */
function initNavigation() {
  const navLinks = document.querySelectorAll('.sidebar-nav .nav-link[data-target]');
  const sections = document.querySelectorAll('.portal-section');
  const sectionTitle = document.getElementById('current-section-title');

  navLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = link.getAttribute('data-target');

      // Update active nav link
      navLinks.forEach(l => l.classList.remove('active'));
      link.classList.add('active');

      // Update visible section
      sections.forEach(sec => sec.classList.remove('active'));
      const activeSection = document.getElementById(targetId);
      if (activeSection) {
        activeSection.classList.add('active');
        if (sectionTitle) {
          sectionTitle.textContent = link.textContent.trim();
        }

        // Trigger on-demand data loads
        if (targetId === 'class-teacher-section') {
          loadClassTeacherData();
          loadClassTeacherDashboard();
        } else if (targetId === 'admin-section') {
          loadAdminData();
          loadAdminAttendanceDashboard();
        } else if (targetId === 'subject-teacher-section') {
          loadSubjectTeacherData();
          loadSubjectTeacherDashboard();
        } else if (targetId === 'reports-section') {
          loadAttendanceReport();
          initAttendanceReportsModule();
        } else if (targetId === 'student-portal-section') {
          // Initialize student portal and load overview
          if (window.SP) {
            SP.init();
            SP.switchTab('sp-overview');
          }
        } else if (targetId === 'teacher-portal-section') {
          // Initialize teacher portal
          if (window.TP) {
            TP.init();
          }
        }
      }
    });
  });


  // Mobile sidebar toggle
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('show');
    });
  }
}

/** Check backend status */
async function initBackendStatusCheck() {
  const badge = document.getElementById('api-status-badge');
  const statusText = document.getElementById('api-status-text');

  async function updateStatus() {
    const isOnline = await Api.checkHealth();
    if (badge && statusText) {
      if (isOnline) {
        badge.className = 'status-pill status-online';
        statusText.textContent = 'Backend Online (FastAPI)';
      } else {
        badge.className = 'status-pill status-offline';
        statusText.textContent = 'Backend Disconnected';
      }
    }
  }

  updateStatus();
  setInterval(updateStatus, 10000);

  // Live institutional clock updater
  function updateLiveClock() {
    const clockEl = document.getElementById('hero-live-clock');
    if (clockEl) {
      const now = new Date();
      const options = { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' };
      clockEl.innerHTML = `<i class="bi bi-clock me-1"></i>${now.toLocaleDateString('en-US', options)}`;
    }
  }
  updateLiveClock();
  setInterval(updateLiveClock, 30000);
}

/** Floating Toast Notification System */
function showToast(type = 'info', title = '', message = '', duration = 4000) {
  const container = document.getElementById('app-toast-container');
  if (!container) return;

  const iconMap = {
    success: 'bi-check-circle-fill text-success',
    error: 'bi-exclamation-octagon-fill text-danger',
    warning: 'bi-exclamation-triangle-fill text-warning',
    info: 'bi-info-circle-fill text-info',
  };

  const toast = document.createElement('div');
  toast.className = `app-toast ${type}`;
  toast.innerHTML = `
    <i class="bi ${iconMap[type] || iconMap.info} fs-4"></i>
    <div class="flex-grow-1">
      ${title ? `<div class="fw-bold small text-dark mb-1">${escapeHtml(title)}</div>` : ''}
      <div class="small text-secondary">${escapeHtml(message)}</div>
    </div>
    <button type="button" class="btn-close btn-sm ms-2" aria-label="Close"></button>
  `;

  const closeBtn = toast.querySelector('.btn-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-10px)';
      setTimeout(() => toast.remove(), 250);
    });
  }

  container.appendChild(toast);

  if (duration > 0) {
    setTimeout(() => {
      if (toast.parentNode) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        setTimeout(() => toast.remove(), 250);
      }
    }, duration);
  }
}
window.showToast = showToast;

/** Update 7-Step Horizontal Stepper */
function updateAttendanceStepper(currentStep) {
  for (let i = 1; i <= 7; i++) {
    const stepEl = document.getElementById(`att-step-${i}`);
    if (!stepEl) continue;
    stepEl.classList.remove('active', 'completed');
    if (i < currentStep) {
      stepEl.classList.add('completed');
    } else if (i === currentStep) {
      stepEl.classList.add('active');
    }
  }
}
window.updateAttendanceStepper = updateAttendanceStepper;

/** Load stats according to role privileges */
async function loadRoleDashboardData(role) {
  try {
    let stats = null;
    try {
      stats = await Api.getAdminStats();
    } catch (e) {
      // Non-admin may receive 403 or role restriction
    }

    const teachersEl = document.getElementById('stat-teachers');
    const studentsEl = document.getElementById('stat-students');
    const facesEl = document.getElementById('stat-faces');
    const sessionsEl = document.getElementById('stat-sessions');

    if (stats) {
      if (teachersEl) teachersEl.textContent = stats.total_teachers ?? 8;
      if (studentsEl) studentsEl.textContent = stats.total_students ?? 45;
      if (facesEl) facesEl.textContent = stats.enrolled_faces ?? 38;
      if (sessionsEl) sessionsEl.textContent = stats.total_attendance_records ?? 110;
    } else {
      if (teachersEl) teachersEl.textContent = '6';
      if (studentsEl) studentsEl.textContent = '35';
      if (facesEl) facesEl.textContent = '32';
      if (sessionsEl) sessionsEl.textContent = '48';
    }

    renderDashboardCharts();
  } catch (err) {
    console.warn('Dashboard data fetch notification:', err.message);
  }
}

function renderDashboardCharts() {
  // 1. Attendance Timeline Trend
  const trendCanvas = document.getElementById('dash-chart-attendance-trend');
  if (trendCanvas && window.Chart) {
    createOrUpdateChart('dash-chart-attendance-trend', {
      type: 'line',
      data: {
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Today'],
        datasets: [{
          label: 'Institutional Attendance Rate (%)',
          data: [88.5, 91.2, 89.0, 93.4, 90.1, 87.5, 94.2],
          borderColor: '#4f46e5',
          backgroundColor: 'rgba(79, 70, 229, 0.1)',
          fill: true,
          tension: 0.35,
          pointBackgroundColor: '#4f46e5',
          pointRadius: 4,
          pointHoverRadius: 6,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { min: 70, max: 100, ticks: { callback: v => v + '%' } },
          x: { grid: { display: false } }
        },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => `Attendance: ${ctx.parsed.y}%` } }
        }
      }
    });
  }

  // 2. Status Donut
  const donutCanvas = document.getElementById('dash-chart-status-donut');
  if (donutCanvas && window.Chart) {
    createOrUpdateChart('dash-chart-status-donut', {
      type: 'doughnut',
      data: {
        labels: ['Present', 'Absent', 'Manual Override'],
        datasets: [{
          data: [84, 12, 4],
          backgroundColor: ['#10b981', '#ef4444', '#f59e0b'],
          borderWidth: 2,
          borderColor: '#ffffff',
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 12, padding: 15, font: { family: 'Inter', size: 12 } } }
        },
        cutout: '68%'
      }
    });
  }
}

// =================================================================
// ADMIN PORTAL INITIALIZATION & MANAGEMENT FUNCTIONS
// =================================================================

function showAdminAlert(message, type = 'success') {
  const banner = document.getElementById('admin-alert-banner');
  const textEl = document.getElementById('admin-alert-text');
  if (!banner || !textEl) return;

  banner.className = `alert alert-${type} alert-dismissible fade show py-2 px-3 small mb-3`;
  textEl.textContent = message;
  banner.classList.remove('d-none');

  // Auto-hide after 5 seconds
  setTimeout(() => {
    if (banner) banner.classList.add('d-none');
  }, 5000);
}

function initAdminPortal() {
  // 1. Sub-Tab Switching
  const tabButtons = document.querySelectorAll('.admin-tab-btn[data-admin-tab]');
  const panes = document.querySelectorAll('.admin-tab-pane');

  tabButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const targetTab = btn.getAttribute('data-admin-tab');

      tabButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      panes.forEach(p => p.classList.remove('active'));
      const activePane = document.getElementById(`admin-pane-${targetTab}`);
      if (activePane) {
        activePane.classList.add('active');
        if (targetTab === 'analytics') {
          loadAdminAttendanceDashboard();
        }
      }
    });
  });

  // 2. Refresh Button
  const refreshBtn = document.getElementById('btn-admin-refresh-all');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      refreshBtn.disabled = true;
      refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Refreshing...';
      await loadAdminData();
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Refresh';
      showAdminAlert('Admin Portal data reloaded successfully!', 'success');
    });
  }

  // 3. Form: Create Class
  const formCreateClass = document.getElementById('form-create-class');
  if (formCreateClass) {
    formCreateClass.addEventListener('submit', async (e) => {
      e.preventDefault();
      const teacherVal = document.getElementById('class-teacher-select').value;
      const payload = {
        name: document.getElementById('class-name-input').value.trim(),
        department: document.getElementById('class-dept-input').value.trim(),
        year: parseInt(document.getElementById('class-year-select').value, 10),
        section: document.getElementById('class-section-select').value,
        class_teacher_id: teacherVal ? parseInt(teacherVal, 10) : null,
      };

      try {
        const newClass = await Api.createClass(payload);
        showAdminAlert(`Class '${newClass.name}' created successfully!`, 'success');
        formCreateClass.reset();
        document.getElementById('class-dept-input').value = 'Computer Science';
        await loadAdminData();
      } catch (err) {
        showAdminAlert(err.message, 'danger');
      }
    });
  }

  // 4. Form: Create Subject
  const formCreateSubject = document.getElementById('form-create-subject');
  if (formCreateSubject) {
    formCreateSubject.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        code: document.getElementById('subject-code-input').value.trim().toUpperCase(),
        name: document.getElementById('subject-name-input').value.trim(),
        department: document.getElementById('subject-dept-input').value.trim(),
      };

      try {
        const newSubj = await Api.createSubject(payload);
        showAdminAlert(`Subject '${newSubj.code} - ${newSubj.name}' created successfully!`, 'success');
        formCreateSubject.reset();
        document.getElementById('subject-dept-input').value = 'Computer Science';
        await loadAdminData();
      } catch (err) {
        showAdminAlert(err.message, 'danger');
      }
    });
  }

  // 5. Form: Create Teacher
  const formCreateTeacher = document.getElementById('form-create-teacher');
  if (formCreateTeacher) {
    formCreateTeacher.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        full_name: document.getElementById('teacher-fullname-input').value.trim(),
        username: document.getElementById('teacher-username-input').value.trim(),
        role: document.getElementById('teacher-role-select').value,
        email: document.getElementById('teacher-email-input').value.trim(),
        department: document.getElementById('teacher-dept-input').value.trim(),
        password: document.getElementById('teacher-pwd-input').value,
      };

      try {
        const newTeacher = await Api.createTeacher(payload);
        showAdminAlert(`Faculty '${newTeacher.full_name}' created successfully!`, 'success');
        formCreateTeacher.reset();
        document.getElementById('teacher-dept-input').value = 'Computer Science';
        await loadAdminData();
      } catch (err) {
        showAdminAlert(err.message, 'danger');
      }
    });
  }

  // 6. Form: Assign Class Teacher (Left side form)
  const formAssignCT = document.getElementById('form-assign-class-teacher');
  if (formAssignCT) {
    formAssignCT.addEventListener('submit', async (e) => {
      e.preventDefault();
      const classId = parseInt(document.getElementById('assign-ct-class-select').value, 10);
      const teacherId = parseInt(document.getElementById('assign-ct-teacher-select').value, 10);

      try {
        const updated = await Api.assignClassTeacher(classId, teacherId);
        showAdminAlert(`Class teacher assigned to '${updated.name}'!`, 'success');
        formAssignCT.reset();
        await loadAdminData();
      } catch (err) {
        showAdminAlert(err.message, 'danger');
      }
    });
  }

  // 7. Form: Assign Subject Teacher to Class
  const formAssignST = document.getElementById('form-assign-subject-teacher');
  if (formAssignST) {
    formAssignST.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        class_id: parseInt(document.getElementById('assign-st-class-select').value, 10),
        subject_id: parseInt(document.getElementById('assign-st-subject-select').value, 10),
        teacher_id: parseInt(document.getElementById('assign-st-teacher-select').value, 10),
      };

      try {
        await Api.createAssignment(payload);
        showAdminAlert('Subject Teacher assigned successfully!', 'success');
        formAssignST.reset();
        await loadAdminData();
      } catch (err) {
        showAdminAlert(err.message, 'danger');
      }
    });
  }

  // 8. Form: Admin Create Student
  const formAdminCreateStudent = document.getElementById('form-admin-create-student');
  if (formAdminCreateStudent) {
    formAdminCreateStudent.addEventListener('submit', async (e) => {
      e.preventDefault();
      const classVal = document.getElementById('admin-stud-class-select').value;
      const payload = {
        roll_number: document.getElementById('admin-stud-roll-input').value.trim(),
        register_number: document.getElementById('admin-stud-reg-input').value.trim(),
        full_name: document.getElementById('admin-stud-name-input').value.trim(),
        department: document.getElementById('admin-stud-dept-input').value.trim(),
        year: parseInt(document.getElementById('admin-stud-year-select').value, 10),
        section: document.getElementById('admin-stud-section-select').value,
        class_id: classVal ? parseInt(classVal, 10) : null,
      };

      try {
        const st = await Api.createStudent(payload);
        showAdminAlert(`Student '${st.full_name}' (${st.roll_number}) registered successfully!`, 'success');
        formAdminCreateStudent.reset();
        document.getElementById('admin-stud-dept-input').value = 'Computer Science';
        await loadAdminData();
      } catch (err) {
        showAdminAlert(err.message, 'danger');
      }
    });
  }

  // 9. Students Search & Filter
  const studentSearchInput = document.getElementById('admin-student-search-input');
  const studentClassFilter = document.getElementById('admin-student-class-filter');
  const btnFilterStudents = document.getElementById('btn-admin-filter-students');

  function filterStudentsTable() {
    const term = (studentSearchInput?.value || '').toLowerCase().trim();
    const classId = studentClassFilter?.value;

    let filtered = adminCachedData.students;
    if (classId) {
      filtered = filtered.filter(s => String(s.class_id) === String(classId));
    }
    if (term) {
      filtered = filtered.filter(s =>
        s.full_name.toLowerCase().includes(term) ||
        s.roll_number.toLowerCase().includes(term) ||
        s.register_number.toLowerCase().includes(term)
      );
    }
    renderStudents(filtered);
  }

  if (studentSearchInput) studentSearchInput.addEventListener('input', filterStudentsTable);
  if (studentClassFilter) studentClassFilter.addEventListener('change', filterStudentsTable);
  if (btnFilterStudents) btnFilterStudents.addEventListener('click', filterStudentsTable);

  // 10. Attendance Records Filter
  const btnApplyAttFilters = document.getElementById('btn-apply-attendance-filters');
  const btnResetAttFilters = document.getElementById('btn-reset-attendance-filters');

  if (btnApplyAttFilters) {
    btnApplyAttFilters.addEventListener('click', async () => {
      const filters = {
        class_id: document.getElementById('att-filter-class')?.value || undefined,
        subject_id: document.getElementById('att-filter-subject')?.value || undefined,
        date_val: document.getElementById('att-filter-date')?.value || undefined,
        status_filter: document.getElementById('att-filter-status')?.value || undefined,
      };
      try {
        const records = await Api.listAttendanceRecords(filters);
        adminCachedData.attendance = records;
        renderAttendanceRecords(records);
      } catch (err) {
        showAdminAlert(err.message, 'danger');
      }
    });
  }

  if (btnResetAttFilters) {
    btnResetAttFilters.addEventListener('click', async () => {
      if (document.getElementById('att-filter-class')) document.getElementById('att-filter-class').value = '';
      if (document.getElementById('att-filter-subject')) document.getElementById('att-filter-subject').value = '';
      if (document.getElementById('att-filter-date')) document.getElementById('att-filter-date').value = '';
      if (document.getElementById('att-filter-status')) document.getElementById('att-filter-status').value = '';
      const records = await Api.listAttendanceRecords();
      adminCachedData.attendance = records;
      renderAttendanceRecords(records);
    });
  }

  // 11. Modal: Assign Class Teacher form submission
  const formModalAssignCT = document.getElementById('form-modal-assign-ct');
  if (formModalAssignCT) {
    formModalAssignCT.addEventListener('submit', async (e) => {
      e.preventDefault();
      const classId = parseInt(document.getElementById('modal-assign-ct-class-id').value, 10);
      const teacherId = parseInt(document.getElementById('modal-assign-ct-teacher-select').value, 10);

      try {
        await Api.assignClassTeacher(classId, teacherId);
        showAdminAlert('Class teacher updated successfully!', 'success');
        const modalEl = document.getElementById('modal-assign-class-teacher');
        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (modalInstance) modalInstance.hide();
        await loadAdminData();
      } catch (err) {
        showAdminAlert(err.message, 'danger');
      }
    });
  }

  // 12. Modal: Edit Student form submission
  const formModalEditStudent = document.getElementById('form-modal-edit-student');
  if (formModalEditStudent) {
    formModalEditStudent.addEventListener('submit', async (e) => {
      e.preventDefault();
      const studentId = parseInt(document.getElementById('modal-edit-student-id').value, 10);
      const classVal = document.getElementById('modal-edit-student-class').value;
      const payload = {
        roll_number: document.getElementById('modal-edit-student-roll').value.trim(),
        register_number: document.getElementById('modal-edit-student-reg').value.trim(),
        full_name: document.getElementById('modal-edit-student-name').value.trim(),
        department: document.getElementById('modal-edit-student-dept').value.trim(),
        year: parseInt(document.getElementById('modal-edit-student-year').value, 10),
        section: document.getElementById('modal-edit-student-section').value,
        class_id: classVal ? parseInt(classVal, 10) : null,
        is_active: document.getElementById('modal-edit-student-active').checked,
      };

      try {
        await Api.updateStudent(studentId, payload);
        showAdminAlert('Student details updated successfully!', 'success');
        const modalEl = document.getElementById('modal-edit-student');
        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (modalInstance) modalInstance.hide();
        await loadAdminData();
      } catch (err) {
        showAdminAlert(err.message, 'danger');
      }
    });
  }

  // 13. Modal: Add Manual Attendance Record
  const btnOpenAttModal = document.getElementById('btn-open-create-attendance-modal');
  if (btnOpenAttModal) {
    btnOpenAttModal.addEventListener('click', () => {
      const today = new Date().toISOString().split('T')[0];
      const dateInput = document.getElementById('modal-att-date');
      if (dateInput) dateInput.value = today;

      const modalEl = document.getElementById('modal-create-attendance');
      if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();
      }
    });
  }

  const formModalCreateAtt = document.getElementById('form-modal-create-attendance');
  if (formModalCreateAtt) {
    formModalCreateAtt.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        student_id: parseInt(document.getElementById('modal-att-student-select').value, 10),
        class_id: parseInt(document.getElementById('modal-att-class-select').value, 10),
        subject_id: parseInt(document.getElementById('modal-att-subject-select').value, 10),
        date: document.getElementById('modal-att-date').value,
        period: parseInt(document.getElementById('modal-att-period').value, 10),
        status: document.getElementById('modal-att-status').value,
      };

      try {
        await Api.createAttendanceRecord(payload);
        showAdminAlert('Attendance record created successfully!', 'success');
        const modalEl = document.getElementById('modal-create-attendance');
        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (modalInstance) modalInstance.hide();
        const records = await Api.listAttendanceRecords();
        adminCachedData.attendance = records;
        renderAttendanceRecords(records);
        await updateAdminKPIs();
      } catch (err) {
        showAdminAlert(err.message, 'danger');
      }
    });
  }
}

/** Master loader for Admin Portal */
async function loadAdminData() {
  try {
    const [stats, classes, subjects, teachers, assignments, students, attendance] = await Promise.all([
      Api.getAdminStats(),
      Api.listClasses(),
      Api.listSubjects(),
      Api.listTeachers(),
      Api.listAssignments(),
      Api.listStudents(),
      Api.listAttendanceRecords(),
    ]);

    adminCachedData = {
      classes,
      subjects,
      teachers,
      assignments,
      students,
      attendance,
    };

    // Update KPI counters
    renderAdminKPIs(stats);

    // Populate all dependent select dropdowns
    populateAdminDropdowns(classes, subjects, teachers, students);

    // Render tables
    renderClasses(classes);
    renderSubjects(subjects);
    renderTeachers(teachers);
    renderAssignments(assignments);
    renderStudents(students);
    renderAttendanceRecords(attendance);

    // Load Admin Attendance Analytics Dashboard
    await loadAdminAttendanceDashboard();

    // Also update main dashboard stats
    const teachersEl = document.getElementById('stat-teachers');
    const studentsEl = document.getElementById('stat-students');
    const facesEl = document.getElementById('stat-faces');
    const sessionsEl = document.getElementById('stat-sessions');
    if (teachersEl) teachersEl.textContent = stats.total_teachers;
    if (studentsEl) studentsEl.textContent = stats.total_students;
    if (facesEl) facesEl.textContent = stats.enrolled_faces;
    if (sessionsEl) sessionsEl.textContent = stats.total_attendance_records;

  } catch (err) {
    console.error('Failed to load admin portal datasets:', err);
    showAdminAlert(`Failed to load admin portal: ${err.message}`, 'danger');
  }
}

async function updateAdminKPIs() {
  try {
    const stats = await Api.getAdminStats();
    renderAdminKPIs(stats);
  } catch (e) {
    console.warn('Could not refresh admin KPIs', e);
  }
}

function renderAdminKPIs(stats) {
  const kpiClasses = document.getElementById('admin-kpi-classes');
  const kpiSubjects = document.getElementById('admin-kpi-subjects');
  const kpiTeachers = document.getElementById('admin-kpi-teachers');
  const kpiStudents = document.getElementById('admin-kpi-students');
  const kpiAttendance = document.getElementById('admin-kpi-attendance');
  const kpiRate = document.getElementById('admin-kpi-rate');

  if (kpiClasses) kpiClasses.textContent = stats.total_classes;
  if (kpiSubjects) kpiSubjects.textContent = stats.total_subjects;
  if (kpiTeachers) kpiTeachers.textContent = stats.total_teachers;
  if (kpiStudents) kpiStudents.textContent = stats.total_students;
  if (kpiAttendance) kpiAttendance.textContent = stats.total_attendance_records;
  if (kpiRate) kpiRate.textContent = `${stats.attendance_rate || 0}%`;
}

/** Populate all select dropdowns across the portal */
function populateAdminDropdowns(classes, subjects, teachers, students) {
  // 1. Class Teacher dropdown (in Create Class)
  populateSelect('class-teacher-select', teachers, t => ({
    value: t.id,
    label: `${t.full_name} (${t.role})`,
  }), '-- No Class Teacher --');

  // 2. Class dropdown (in Assign Class Teacher)
  populateSelect('assign-ct-class-select', classes, c => ({
    value: c.id,
    label: `${c.name} (${c.department})`,
  }), '-- Choose Class --');

  // 3. Teacher dropdown (in Assign Class Teacher)
  populateSelect('assign-ct-teacher-select', teachers, t => ({
    value: t.id,
    label: `${t.full_name} (${t.department || 'General'})`,
  }), '-- Choose Teacher --');

  // 4. Modal Assign Class Teacher dropdown
  populateSelect('modal-assign-ct-teacher-select', teachers, t => ({
    value: t.id,
    label: `${t.full_name} (${t.department || 'General'})`,
  }), '-- Choose Faculty Member --');

  // 5. Subject Teacher Class Select
  populateSelect('assign-st-class-select', classes, c => ({
    value: c.id,
    label: `${c.name}`,
  }), '-- Choose Class --');

  // 6. Subject Teacher Subject Select
  populateSelect('assign-st-subject-select', subjects, s => ({
    value: s.id,
    label: `${s.code} - ${s.name}`,
  }), '-- Choose Subject --');

  // 7. Subject Teacher Faculty Select
  populateSelect('assign-st-teacher-select', teachers, t => ({
    value: t.id,
    label: `${t.full_name} (${t.role})`,
  }), '-- Choose Teacher --');

  // 8. Admin Student Class Select
  populateSelect('admin-stud-class-select', classes, c => ({
    value: c.id,
    label: `${c.name}`,
  }), '-- Match Automatically by Dept/Year/Sec --');

  // 9. Admin Student Filter by Class
  populateSelect('admin-student-class-filter', classes, c => ({
    value: c.id,
    label: `${c.name}`,
  }), 'All Classes');

  // 10. Modal Edit Student Class
  populateSelect('modal-edit-student-class', classes, c => ({
    value: c.id,
    label: `${c.name}`,
  }), '-- No Class / Auto Match --');

  // 11. Attendance Filters Class
  populateSelect('att-filter-class', classes, c => ({
    value: c.id,
    label: `${c.name}`,
  }), 'All Classes');

  // 12. Attendance Filters Subject
  populateSelect('att-filter-subject', subjects, s => ({
    value: s.id,
    label: `${s.code} - ${s.name}`,
  }), 'All Subjects');

  // 13. Modal Attendance Student Select
  populateSelect('modal-att-student-select', students, st => ({
    value: st.id,
    label: `${st.roll_number} - ${st.full_name} (${st.department})`,
  }), '-- Select Student --');

  // 14. Modal Attendance Class Select
  populateSelect('modal-att-class-select', classes, c => ({
    value: c.id,
    label: `${c.name}`,
  }), '-- Select Class --');

  // 15. Modal Attendance Subject Select
  populateSelect('modal-att-subject-select', subjects, s => ({
    value: s.id,
    label: `${s.code} - ${s.name}`,
  }), '-- Select Subject --');
}

function populateSelect(selectId, items, mapFn, defaultLabel = '') {
  const el = document.getElementById(selectId);
  if (!el) return;

  const currentVal = el.value;
  el.innerHTML = '';
  if (defaultLabel) {
    const defOpt = document.createElement('option');
    defOpt.value = '';
    defOpt.textContent = defaultLabel;
    el.appendChild(defOpt);
  }

  items.forEach(item => {
    const opt = document.createElement('option');
    const { value, label } = mapFn(item);
    opt.value = value;
    opt.textContent = label;
    el.appendChild(opt);
  });

  if (currentVal) el.value = currentVal;
}

/** Render Classes Table */
function renderClasses(classes) {
  const tbody = document.getElementById('classes-table-body');
  const badge = document.getElementById('classes-count-badge');
  if (badge) badge.textContent = `${classes.length} Classes`;
  if (!tbody) return;

  if (classes.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No classes created yet. Use the form on the left to add your first class cohort.</td></tr>';
    return;
  }

  tbody.innerHTML = classes.map(c => {
    const teacherDisplay = c.class_teacher_name
      ? `<span class="fw-semibold text-primary"><i class="bi bi-person-check me-1"></i>${c.class_teacher_name}</span>`
      : `<span class="badge bg-secondary-subtle text-secondary">Unassigned</span>`;

    return `
      <tr>
        <td>
          <div class="fw-bold text-dark">${escapeHtml(c.name)}</div>
          <small class="text-muted">ID: #${c.id}</small>
        </td>
        <td>${escapeHtml(c.department)}</td>
        <td><span class="badge bg-light text-dark border">Yr ${c.year} - Sec ${c.section}</span></td>
        <td>${teacherDisplay}</td>
        <td><span class="badge bg-primary-subtle text-primary">${c.student_count || 0} students</span></td>
        <td>
          <div class="d-flex gap-1">
            <button class="btn btn-action-sm btn-action-assign" onclick="openAssignClassTeacherModal(${c.id}, '${escapeHtml(c.name)}', ${c.class_teacher_id || 'null'})" title="Assign / Change Teacher">
              <i class="bi bi-person-gear"></i>Teacher
            </button>
            <button class="btn btn-action-sm btn-action-delete" onclick="handleDeleteClass(${c.id}, '${escapeHtml(c.name)}')" title="Delete Class">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

/** Open Assign Class Teacher Modal */
window.openAssignClassTeacherModal = function(classId, className, currentTeacherId) {
  const modalEl = document.getElementById('modal-assign-class-teacher');
  const idInput = document.getElementById('modal-assign-ct-class-id');
  const nameInput = document.getElementById('modal-assign-ct-class-name');
  const teacherSelect = document.getElementById('modal-assign-ct-teacher-select');

  if (idInput) idInput.value = classId;
  if (nameInput) nameInput.value = className;
  if (teacherSelect && currentTeacherId) teacherSelect.value = currentTeacherId;

  if (modalEl) {
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
  }
};

/** Delete Class */
window.handleDeleteClass = async function(classId, className) {
  if (!confirm(`Are you sure you want to delete class '${className}'? This will also remove student group associations.`)) return;

  try {
    await Api.deleteClass(classId);
    showAdminAlert(`Class '${className}' deleted successfully!`, 'success');
    await loadAdminData();
  } catch (err) {
    showAdminAlert(err.message, 'danger');
  }
};

/** Render Subjects Table */
function renderSubjects(subjects) {
  const tbody = document.getElementById('subjects-table-body');
  const badge = document.getElementById('subjects-count-badge');
  if (badge) badge.textContent = `${subjects.length} Subjects`;
  if (!tbody) return;

  if (subjects.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">No curriculum subjects registered yet.</td></tr>';
    return;
  }

  tbody.innerHTML = subjects.map(s => `
    <tr>
      <td><span class="badge bg-info-subtle text-info fw-bold font-monospace">${escapeHtml(s.code)}</span></td>
      <td>
        <div class="fw-semibold text-dark">${escapeHtml(s.name)}</div>
        <small class="text-muted">ID: #${s.id}</small>
      </td>
      <td>${escapeHtml(s.department)}</td>
      <td>
        <button class="btn btn-action-sm btn-action-delete" onclick="handleDeleteSubject(${s.id}, '${escapeHtml(s.name)}')" title="Delete Subject">
          <i class="bi bi-trash"></i>Delete
        </button>
      </td>
    </tr>
  `).join('');
}

window.handleDeleteSubject = async function(subjectId, subjectName) {
  if (!confirm(`Are you sure you want to delete subject '${subjectName}'?`)) return;

  try {
    await Api.deleteSubject(subjectId);
    showAdminAlert(`Subject '${subjectName}' deleted successfully!`, 'success');
    await loadAdminData();
  } catch (err) {
    showAdminAlert(err.message, 'danger');
  }
};

/** Render Teachers Table */
function renderTeachers(teachers) {
  const tbody = document.getElementById('teachers-table-body');
  const badge = document.getElementById('teachers-count-badge');
  if (badge) badge.textContent = `${teachers.length} Teachers`;
  if (!tbody) return;

  if (teachers.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No teachers registered yet.</td></tr>';
    return;
  }

  tbody.innerHTML = teachers.map(t => {
    let roleBadge = '<span class="badge bg-info-subtle text-info">SUBJECT_TEACHER</span>';
    if (t.role === 'ADMIN') roleBadge = '<span class="badge bg-danger-subtle text-danger">ADMIN</span>';
    else if (t.role === 'CLASS_TEACHER') roleBadge = '<span class="badge bg-primary-subtle text-primary">CLASS_TEACHER</span>';

    const currentUser = Api.getUser();
    const isSelf = currentUser && currentUser.id === t.id;

    return `
      <tr>
        <td>
          <div class="fw-bold text-dark">${escapeHtml(t.full_name)} ${isSelf ? '<span class="badge bg-secondary ms-1">You</span>' : ''}</div>
          <small class="text-muted"><i class="bi bi-envelope me-1"></i>${escapeHtml(t.email)} • @${escapeHtml(t.username)}</small>
        </td>
        <td>${roleBadge}</td>
        <td>${escapeHtml(t.department || 'Administration')}</td>
        <td><small class="text-muted">${new Date(t.created_at).toLocaleDateString()}</small></td>
        <td>
          ${isSelf ? '<span class="small text-muted fst-italic">Active Session</span>' : `
            <button class="btn btn-action-sm btn-action-delete" onclick="handleDeleteTeacher(${t.id}, '${escapeHtml(t.full_name)}')" title="Delete Teacher">
              <i class="bi bi-trash"></i>Delete
            </button>
          `}
        </td>
      </tr>
    `;
  }).join('');
}

window.handleDeleteTeacher = async function(teacherId, teacherName) {
  if (!confirm(`Are you sure you want to delete teacher account '${teacherName}'?`)) return;

  try {
    await Api.deleteTeacher(teacherId);
    showAdminAlert(`Teacher account '${teacherName}' deleted successfully!`, 'success');
    await loadAdminData();
  } catch (err) {
    showAdminAlert(err.message, 'danger');
  }
};

/** Render Assignments Table */
function renderAssignments(assignments) {
  const tbody = document.getElementById('assignments-table-body');
  const badge = document.getElementById('assignments-count-badge');
  if (badge) badge.textContent = `${assignments.length} Assignments`;
  if (!tbody) return;

  if (assignments.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">No subject teacher assignments mapped yet. Use the form on the left to map teachers to classes and subjects.</td></tr>';
    return;
  }

  tbody.innerHTML = assignments.map(a => `
    <tr>
      <td>
        <div class="fw-bold text-dark">${escapeHtml(a.class_name || 'Class #' + a.class_id)}</div>
      </td>
      <td>
        <span class="badge bg-info-subtle text-info me-1">${escapeHtml(a.subject_code || '')}</span>
        <span class="fw-medium">${escapeHtml(a.subject_name || '')}</span>
      </td>
      <td>
        <div class="fw-semibold text-primary"><i class="bi bi-person me-1"></i>${escapeHtml(a.teacher_name || 'Teacher #' + a.teacher_id)}</div>
      </td>
      <td>
        <button class="btn btn-action-sm btn-action-delete" onclick="handleDeleteAssignment(${a.id})" title="Remove Assignment">
          <i class="bi bi-x-circle me-1"></i>Remove
        </button>
      </td>
    </tr>
  `).join('');
}

window.handleDeleteAssignment = async function(assignmentId) {
  if (!confirm('Are you sure you want to remove this subject teacher assignment?')) return;

  try {
    await Api.deleteAssignment(assignmentId);
    showAdminAlert('Subject assignment removed successfully!', 'success');
    await loadAdminData();
  } catch (err) {
    showAdminAlert(err.message, 'danger');
  }
};

/** Render Students Table */
function renderStudents(students) {
  const tbody = document.getElementById('students-table-body');
  const badge = document.getElementById('students-count-badge');
  if (badge) badge.textContent = `${students.length} Students`;
  if (!tbody) return;

  if (students.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No students found matching current filters.</td></tr>';
    return;
  }

  tbody.innerHTML = students.map(st => {
    const faceBadge = st.face_enrolled
      ? '<span class="badge bg-success-subtle text-success"><i class="bi bi-check-circle me-1"></i>Enrolled</span>'
      : '<span class="badge bg-warning-subtle text-warning"><i class="bi bi-clock me-1"></i>Pending</span>';

    const activeBadge = st.is_active
      ? '<span class="badge bg-success">Active</span>'
      : '<span class="badge bg-secondary">Inactive</span>';

    const classDisplay = st.class_name
      ? escapeHtml(st.class_name)
      : `<span class="text-muted">${escapeHtml(st.department)} - Yr ${st.year} (${st.section})</span>`;

    return `
      <tr>
        <td>
          <span class="fw-bold font-monospace text-primary">${escapeHtml(st.roll_number)}</span>
          <div><small class="text-muted">${escapeHtml(st.register_number)}</small></div>
        </td>
        <td>
          <div class="fw-semibold text-dark">${escapeHtml(st.full_name)}</div>
          <small class="text-muted">${escapeHtml(st.department)}</small>
        </td>
        <td>${classDisplay}</td>
        <td>${activeBadge}</td>
        <td>${faceBadge}</td>
        <td>
          <div class="d-flex gap-1">
            <button class="btn btn-action-sm btn-action-edit" onclick="openEditStudentModal(${st.id})" title="Edit Student">
              <i class="bi bi-pencil"></i>Edit
            </button>
            <button class="btn btn-action-sm btn-action-delete" onclick="handleDeleteStudent(${st.id}, '${escapeHtml(st.full_name)}')" title="Delete Student">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

/** Open Edit Student Modal */
window.openEditStudentModal = function(studentId) {
  const st = adminCachedData.students.find(s => s.id === studentId);
  if (!st) return;

  const modalEl = document.getElementById('modal-edit-student');
  document.getElementById('modal-edit-student-id').value = st.id;
  document.getElementById('modal-edit-student-roll').value = st.roll_number;
  document.getElementById('modal-edit-student-reg').value = st.register_number;
  document.getElementById('modal-edit-student-name').value = st.full_name;
  document.getElementById('modal-edit-student-dept').value = st.department;
  document.getElementById('modal-edit-student-year').value = st.year;
  document.getElementById('modal-edit-student-section').value = st.section;
  document.getElementById('modal-edit-student-class').value = st.class_id || '';
  document.getElementById('modal-edit-student-active').checked = st.is_active;

  if (modalEl) {
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
  }
};

window.handleDeleteStudent = async function(studentId, studentName) {
  if (!confirm(`Are you sure you want to delete student '${studentName}'? This will also remove their attendance history.`)) return;

  try {
    await Api.deleteStudent(studentId);
    showAdminAlert(`Student '${studentName}' deleted successfully!`, 'success');
    await loadAdminData();
  } catch (err) {
    showAdminAlert(err.message, 'danger');
  }
};

/** Render Attendance Records Table */
function renderAttendanceRecords(records) {
  const tbody = document.getElementById('attendance-table-body');
  const badge = document.getElementById('attendance-total-badge');
  const summaryText = document.getElementById('attendance-summary-text');
  if (badge) badge.textContent = `${records.length} Records`;
  if (!tbody) return;

  if (records.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">No attendance records found. Take a classroom photo or click "Add Attendance Record" to create entries.</td></tr>';
    if (summaryText) summaryText.textContent = 'Showing 0 records';
    return;
  }

  const presentCount = records.filter(r => r.status === 'PRESENT').length;
  const rate = Math.round((presentCount / records.length) * 100);
  if (summaryText) {
    summaryText.innerHTML = `Showing <strong>${records.length}</strong> records • <strong>${presentCount}</strong> Present (${rate}% attendance rate)`;
  }

  tbody.innerHTML = records.map(r => {
    let statusClass = 'badge-status-present';
    if (r.status === 'ABSENT') statusClass = 'badge-status-absent';
    else if (r.status === 'LATE') statusClass = 'badge-status-late';
    else if (r.status === 'EXCUSED') statusClass = 'badge-status-excused';

    const confDisplay = r.confidence !== null && r.confidence !== undefined
      ? `<span class="text-success fw-bold">${Math.round(r.confidence * 100)}%</span>`
      : `<span class="text-muted">${r.is_manual ? 'Manual' : '-'}</span>`;

    const typeDisplay = r.is_manual
      ? '<span class="badge bg-secondary-subtle text-secondary"><i class="bi bi-pencil me-1"></i>Manual</span>'
      : '<span class="badge bg-primary-subtle text-primary"><i class="bi bi-camera me-1"></i>Vision</span>';

    return `
      <tr>
        <td>
          <div class="fw-semibold text-dark">${r.date}</div>
        </td>
        <td><span class="badge bg-light text-dark border">P${r.period}</span></td>
        <td><span class="font-monospace fw-bold">${escapeHtml(r.student_roll || '#' + r.student_id)}</span></td>
        <td>
          <div class="fw-semibold text-dark">${escapeHtml(r.student_name || 'Student #' + r.student_id)}</div>
        </td>
        <td><span class="${statusClass}">${r.status}</span></td>
        <td>
          <div>${confDisplay}</div>
          <small>${typeDisplay}</small>
        </td>
        <td><small class="text-muted">${r.teacher_id ? 'Faculty #' + r.teacher_id : 'System'}</small></td>
        <td>
          <button class="btn btn-action-sm btn-action-delete" onclick="handleDeleteAttendance(${r.id})" title="Delete Record">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

window.handleDeleteAttendance = async function(recordId) {
  if (!confirm('Are you sure you want to delete this attendance record?')) return;

  try {
    await Api.deleteAttendanceRecord(recordId);
    showAdminAlert('Attendance record deleted successfully!', 'success');
    const records = await Api.listAttendanceRecords();
    adminCachedData.attendance = records;
    renderAttendanceRecords(records);
    await updateAdminKPIs();
  } catch (err) {
    showAdminAlert(err.message, 'danger');
  }
};

/** HTML escape helper */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/** Form and photo handlers */
function initFormHandlers() {
  // Student registration form on enrollment tab
  const studentForm = document.getElementById('student-reg-form');
  if (studentForm) {
    studentForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        roll_number: document.getElementById('roll-number').value.trim(),
        register_number: document.getElementById('reg-number').value.trim(),
        full_name: document.getElementById('full-name').value.trim(),
        department: document.getElementById('dept').value,
        year: parseInt(document.getElementById('year').value, 10),
        section: document.getElementById('section').value,
      };

      try {
        const student = await Api.createStudent(payload);
        showAdminAlert(`Student ${student.full_name} (${student.roll_number}) registered successfully!`, 'success');
        studentForm.reset();
        await loadAdminData();
      } catch (err) {
        alert(`Error: ${err.message}`);
      }
    });
  }

  // Classroom photo preview
  const classroomPhotoInput = document.getElementById('classroom-photo-input');
  const photoPreview = document.getElementById('photo-preview');
  const previewContainer = document.getElementById('preview-container');

  if (classroomPhotoInput) {
    classroomPhotoInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (event) => {
          if (photoPreview && previewContainer) {
            photoPreview.src = event.target.result;
            previewContainer.classList.remove('d-none');
          }
        };
        reader.readAsDataURL(file);
      }
    });
  }
}

// =================================================================
// CLASS TEACHER PORTAL & STUDENT MANAGEMENT LOGIC
// =================================================================

let currentClassTeacherClass = null;
let currentClassTeacherStudents = [];
let currentClassTeacherSubjectTeachers = [];
let availableAssignmentOptions = { classes: [], subjects: [] };
let selectedFaceUploadStudent = null;
let selectedFaceFile = null;

// Note: escapeHtml helper is declared once globally above

function showClassTeacherAlert(message, type = 'success') {
  const banner = document.getElementById('ct-alert-banner');
  if (!banner) return;
  banner.className = `alert alert-${type} alert-dismissible fade show py-2 px-3 small mb-3`;
  banner.innerHTML = `
    <div class="d-flex justify-content-between align-items-center">
      <div>
        <i class="bi bi-${type === 'success' ? 'check-circle-fill text-success' : 'exclamation-circle-fill text-danger'} me-2"></i>
        <span>${message}</span>
      </div>
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>
  `;
  banner.classList.remove('d-none');
  setTimeout(() => {
    if (banner) banner.classList.add('d-none');
  }, 5000);
}

async function loadClassTeacherData() {
  const refreshBtn = document.getElementById('btn-ct-refresh');
  if (refreshBtn) refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Loading...';

  try {
    // 1. Fetch assigned class details
    const classData = await Api.getMyAssignedClass();
    currentClassTeacherClass = classData;

    // Header Card Updates
    const nameEl = document.getElementById('ct-class-name');
    const deptEl = document.getElementById('ct-section-dept-badge');
    const batchEl = document.getElementById('ct-section-batch-badge');
    const mentorEl = document.getElementById('ct-teacher-name');

    if (nameEl) nameEl.textContent = classData.name;
    if (deptEl) deptEl.innerHTML = `<i class="bi bi-building me-1"></i>${classData.department}`;
    if (batchEl) batchEl.innerHTML = `<i class="bi bi-mortarboard me-1"></i>Year ${classData.year} - Sec ${classData.section}`;
    if (mentorEl) mentorEl.textContent = classData.class_teacher_name || 'Faculty Mentor';

    // KPI Stat Row Updates
    const strengthEl = document.getElementById('ct-stat-total-students');
    const activeEl = document.getElementById('ct-stat-active-students');
    const enrolledEl = document.getElementById('ct-stat-face-enrolled');
    const barEl = document.getElementById('ct-stat-face-bar');
    const percentEl = document.getElementById('ct-stat-face-percent');
    const attRateEl = document.getElementById('ct-stat-attendance-rate');

    if (strengthEl) strengthEl.textContent = classData.total_students;
    if (activeEl) activeEl.textContent = classData.active_students;
    if (enrolledEl) enrolledEl.textContent = `${classData.face_enrolled_count} / ${classData.total_students}`;
    if (barEl) barEl.style.width = `${classData.face_enrollment_rate}%`;
    if (percentEl) percentEl.textContent = `${classData.face_enrollment_rate}%`;
    if (attRateEl) attRateEl.textContent = `${classData.overall_attendance_rate}%`;

    // 2. Fetch Students Roster with filters
    await filterAndRenderClassTeacherStudents();

    // 3. Fetch Attendance Summary Analytics
    await loadClassTeacherAttendanceSummary();
    await loadClassTeacherDashboard(classData.id);

    // 4. Render Subjects list
    renderClassTeacherSubjects(classData.subjects || []);

    // 5. Load Subject Teachers & Course Assignments
    await loadClassTeacherSubjectTeachers();

  } catch (err) {
    console.error('Failed to load class teacher data:', err);
    showClassTeacherAlert(err.message, 'danger');
  } finally {
    if (refreshBtn) refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh';
  }
}

async function filterAndRenderClassTeacherStudents() {
  const searchInput = document.getElementById('ct-student-search');
  const statusFilter = document.getElementById('ct-student-status-filter');
  const faceFilter = document.getElementById('ct-student-face-filter');

  const params = {};
  if (searchInput && searchInput.value.trim()) params.search = searchInput.value.trim();
  if (statusFilter && statusFilter.value !== 'all') params.status = statusFilter.value;
  if (faceFilter && faceFilter.value !== 'all') params.face_status = faceFilter.value;

  try {
    const students = await Api.getClassStudents(params);
    currentClassTeacherStudents = students;
    renderClassTeacherStudentsTable(students);
  } catch (err) {
    console.error('Failed to filter students:', err);
    showClassTeacherAlert(err.message, 'danger');
  }
}

function renderClassTeacherStudentsTable(students) {
  const tbody = document.getElementById('ct-students-table-body');
  const emptyState = document.getElementById('ct-students-empty-state');
  if (!tbody) return;

  if (!students || students.length === 0) {
    tbody.innerHTML = '';
    if (emptyState) emptyState.classList.remove('d-none');
    return;
  }

  if (emptyState) emptyState.classList.add('d-none');

  tbody.innerHTML = students.map((st) => {
    const hasPhoto = !!st.face_image_path;
    const photoHtml = hasPhoto
      ? `<img src="${st.face_image_path}" class="student-avatar" alt="${escapeHtml(st.full_name)}" onclick="openViewFaceModal(${st.id})" title="Click to view portrait" style="cursor: pointer;">`
      : `<div class="student-avatar-placeholder" onclick="openUploadFaceModal(${st.id})" title="Click to upload face photo" style="cursor: pointer;"><i class="bi bi-camera"></i></div>`;

    const faceBadgeHtml = st.face_enrolled
      ? `<span class="enrollment-badge-enrolled" onclick="openViewFaceModal(${st.id})" style="cursor: pointer;" title="Face enrolled. Click to view portrait."><i class="bi bi-check-circle-fill"></i> Enrolled</span>`
      : `<span class="enrollment-badge-pending" onclick="openUploadFaceModal(${st.id})" style="cursor: pointer;" title="Pending face enrollment. Click to upload."><i class="bi bi-camera"></i> Pending</span>`;

    const attHtml = st.attendance_rate !== null && st.attendance_rate !== undefined
      ? `<div>
           <span class="small fw-bold ${st.attendance_rate >= 75 ? 'text-success' : 'text-danger'}">${st.attendance_rate}%</span>
           <div class="att-progress-track" style="width: 75px;">
             <div class="att-progress-fill ${st.attendance_rate >= 75 ? 'bg-success' : 'bg-danger'}" style="width: ${st.attendance_rate}%;"></div>
           </div>
         </div>`
      : `<span class="text-muted small">No sessions</span>`;

    const statusBadge = st.is_active
      ? `<button class="btn btn-sm btn-outline-success py-0 px-2 small" onclick="toggleClassStudentStatus(${st.id})" title="Active student. Click to deactivate."><i class="bi bi-check-circle me-1"></i>Active</button>`
      : `<button class="btn btn-sm btn-outline-secondary py-0 px-2 small" onclick="toggleClassStudentStatus(${st.id})" title="Inactive student. Click to activate."><i class="bi bi-dash-circle me-1"></i>Inactive</button>`;

    const emailDisplay = st.email ? `<span class="d-block small text-secondary"><i class="bi bi-envelope me-1"></i>${escapeHtml(st.email)}</span>` : '';
    const phoneDisplay = st.phone ? `<span class="d-block small text-secondary"><i class="bi bi-telephone me-1"></i>${escapeHtml(st.phone)}</span>` : '';
    const contactHtml = (emailDisplay || phoneDisplay) ? `${emailDisplay}${phoneDisplay}` : '<span class="text-muted small">Not provided</span>';

    return `
      <tr>
        <td>${photoHtml}</td>
        <td><span class="badge bg-light text-dark border fw-bold">${escapeHtml(st.roll_number)}</span></td>
        <td>
          <div class="fw-semibold text-dark">${escapeHtml(st.full_name)}</div>
          <small class="text-muted">Reg: ${escapeHtml(st.register_number || 'N/A')}</small>
        </td>
        <td>${contactHtml}</td>
        <td>${faceBadgeHtml}</td>
        <td>${attHtml}</td>
        <td>${statusBadge}</td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-primary" onclick="openUploadFaceModal(${st.id})" title="Upload Face Photo">
              <i class="bi bi-camera-fill"></i>
            </button>
            <button class="btn btn-outline-secondary" onclick="openEditStudentModal(${st.id})" title="Edit Student">
              <i class="bi bi-pencil-fill"></i>
            </button>
            <button class="btn btn-outline-danger" onclick="deleteClassStudent(${st.id}, '${escapeHtml(st.full_name)}')" title="Delete Student">
              <i class="bi bi-trash-fill"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

async function loadClassTeacherAttendanceSummary() {
  try {
    const summary = await Api.getClassAttendanceSummary();
    const sessionsCountEl = document.getElementById('ct-stat-sessions-count');
    const lowAttCountEl = document.getElementById('ct-stat-low-att-count');
    const lowAttBadgeEl = document.getElementById('ct-low-att-badge');

    if (sessionsCountEl) sessionsCountEl.textContent = summary.total_sessions;
    if (lowAttCountEl) lowAttCountEl.textContent = summary.low_attendance_students.length;
    if (lowAttBadgeEl) lowAttBadgeEl.textContent = `${summary.low_attendance_students.length} Students`;

    // Render Low Attendance Table
    const lowAttBody = document.getElementById('ct-low-att-table-body');
    if (lowAttBody) {
      if (summary.low_attendance_students.length === 0) {
        lowAttBody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-muted"><i class="bi bi-check-circle text-success me-1"></i>All students satisfy the 75% attendance criterion!</td></tr>`;
      } else {
        lowAttBody.innerHTML = summary.low_attendance_students.map(s => `
          <tr>
            <td><span class="badge bg-light text-dark border">${escapeHtml(s.roll_number)}</span></td>
            <td><strong>${escapeHtml(s.full_name)}</strong></td>
            <td>${s.attended_classes} / ${s.total_classes}</td>
            <td><span class="badge bg-danger">${s.attendance_rate}%</span></td>
          </tr>
        `).join('');
      }
    }

    // Render Subject Breakdown Table
    const subBody = document.getElementById('ct-subject-summary-table-body');
    if (subBody) {
      if (!summary.subject_summaries || summary.subject_summaries.length === 0) {
        subBody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-muted">No subject assignments recorded.</td></tr>`;
      } else {
        subBody.innerHTML = summary.subject_summaries.map(sub => `
          <tr>
            <td>
              <strong>${escapeHtml(sub.subject_name)}</strong><br>
              <small class="text-muted">${escapeHtml(sub.subject_code)}</small>
            </td>
            <td>${escapeHtml(sub.teacher_name)}</td>
            <td>${sub.total_sessions} sessions</td>
            <td>
              ${sub.attendance_rate !== null 
                ? `<span class="badge ${sub.attendance_rate >= 75 ? 'bg-success' : 'bg-warning text-dark'}">${sub.attendance_rate}%</span>`
                : '<span class="text-muted small">No records</span>'}
            </td>
          </tr>
        `).join('');
      }
    }
  } catch (err) {
    console.warn('Attendance summary warning:', err.message);
  }
}

function renderClassTeacherSubjects(subjects) {
  const container = document.getElementById('ct-subjects-cards-row');
  if (!container) return;

  if (!subjects || subjects.length === 0) {
    container.innerHTML = `<div class="col-12 text-center py-4 text-muted">No course assignments mapped yet.</div>`;
    return;
  }

  container.innerHTML = subjects.map(sub => `
    <div class="col-md-6 col-lg-4">
      <div class="card border rounded-3 p-3 h-100 shadow-sm">
        <div class="d-flex justify-content-between align-items-start mb-2">
          <span class="badge bg-primary">${escapeHtml(sub.subject_code)}</span>
          <span class="badge bg-light text-dark border">Theory / Practical</span>
        </div>
        <h6 class="fw-bold text-dark mb-1">${escapeHtml(sub.subject_name)}</h6>
        <p class="text-secondary small mb-3">Assigned Faculty: <strong>${escapeHtml(sub.teacher_name)}</strong></p>
        <div class="mt-auto pt-2 border-top d-flex justify-content-between align-items-center">
          <span class="text-muted small">Curriculum Subject</span>
          <i class="bi bi-journal-check text-primary"></i>
        </div>
      </div>
    </div>
  `).join('');
}

async function loadClassTeacherSubjectTeachers() {
  const tbody = document.getElementById('ct-teachers-table-body');
  const countBadge = document.getElementById('ct-teachers-count-badge');
  const refreshBtn = document.getElementById('btn-ct-refresh-teachers');

  if (refreshBtn) {
    refreshBtn.disabled = true;
    refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Refreshing...';
  }

  try {
    const [teachers, options] = await Promise.all([
      Api.getClassTeacherSubjectTeachers(),
      Api.getAvailableAssignmentOptions()
    ]);
    currentClassTeacherSubjectTeachers = teachers || [];
    availableAssignmentOptions = options || { classes: [], subjects: [] };
    filterAndRenderClassTeacherSubjectTeachers();
  } catch (err) {
    console.error('Failed to load subject teachers:', err);
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger"><i class="bi bi-exclamation-triangle me-1"></i>${escapeHtml(err.message || 'Failed to load subject teachers')}</td></tr>`;
    }
  } finally {
    if (refreshBtn) {
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Refresh';
    }
  }
}

function filterAndRenderClassTeacherSubjectTeachers() {
  const tbody = document.getElementById('ct-teachers-table-body');
  const countBadge = document.getElementById('ct-teachers-count-badge');
  if (!tbody) return;

  const searchInput = document.getElementById('ct-teacher-search');
  const statusFilter = document.getElementById('ct-teacher-status-filter');

  const query = (searchInput ? searchInput.value : '').toLowerCase().trim();
  const statusVal = statusFilter ? statusFilter.value : 'all';

  const filtered = currentClassTeacherSubjectTeachers.filter(t => {
    // Status filter
    if (statusVal === 'active' && !t.is_active) return false;
    if (statusVal === 'inactive' && t.is_active) return false;

    // Search query
    if (query) {
      const matchName = (t.full_name || '').toLowerCase().includes(query);
      const matchTid = (t.teacher_id || '').toLowerCase().includes(query);
      const matchUser = (t.username || '').toLowerCase().includes(query);
      const matchEmail = (t.email || '').toLowerCase().includes(query);
      const matchDept = (t.department || '').toLowerCase().includes(query);
      const matchAssign = (t.assignments || []).some(a => 
        (a.subject_name || '').toLowerCase().includes(query) ||
        (a.subject_code || '').toLowerCase().includes(query) ||
        (a.class_name || '').toLowerCase().includes(query)
      );
      if (!matchName && !matchTid && !matchUser && !matchEmail && !matchDept && !matchAssign) {
        return false;
      }
    }
    return true;
  });

  if (countBadge) {
    countBadge.textContent = `Showing ${filtered.length} of ${currentClassTeacherSubjectTeachers.length} teachers`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="text-center py-5 text-muted">
          <i class="bi bi-person-x fs-2 d-block mb-2 text-secondary opacity-50"></i>
          <span>No subject teachers found matching your filters.</span>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(t => {
    const tidBadge = t.teacher_id
      ? `<span class="badge bg-secondary-subtle text-dark border font-monospace px-2 py-1">${escapeHtml(t.teacher_id)}</span>`
      : `<span class="text-muted small">N/A</span>`;

    const statusBadge = t.is_active
      ? `<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1"><i class="bi bi-check-circle me-1"></i>Active</span>`
      : `<span class="badge bg-danger-subtle text-danger border border-danger-subtle px-2 py-1"><i class="bi bi-slash-circle me-1"></i>Deactivated</span>`;

    const assignmentsBadges = (t.assignments && t.assignments.length > 0)
      ? t.assignments.map(a => `
          <span class="badge bg-primary-subtle text-primary border border-primary-subtle me-1 mb-1" title="${escapeHtml(a.subject_name)} (${escapeHtml(a.class_name)})">
            <i class="bi bi-book me-1"></i>${escapeHtml(a.subject_code)} &bull; ${escapeHtml(a.class_name)}
          </span>
        `).join('')
      : `<span class="text-muted small fst-italic">No classes/subjects assigned</span>`;

    const toggleActionBtn = t.is_active
      ? `<button class="btn btn-outline-danger btn-sm py-0 px-2 small" onclick="toggleClassTeacherSubjectTeacherStatus(${t.id}, '${escapeHtml(t.full_name)}', false)" title="Deactivate account">
           <i class="bi bi-pause-circle me-1"></i>Deactivate
         </button>`
      : `<button class="btn btn-outline-success btn-sm py-0 px-2 small" onclick="toggleClassTeacherSubjectTeacherStatus(${t.id}, '${escapeHtml(t.full_name)}', true)" title="Activate account">
           <i class="bi bi-play-circle me-1"></i>Activate
         </button>`;

    return `
      <tr>
        <td>${tidBadge}</td>
        <td>
          <div class="fw-bold text-dark">${escapeHtml(t.full_name)}</div>
          ${t.email ? `<small class="text-muted d-block" style="font-size: 0.75rem;">${escapeHtml(t.email)}</small>` : ''}
        </td>
        <td><span class="text-dark font-monospace small">${escapeHtml(t.username)}</span></td>
        <td><span class="text-secondary small">${escapeHtml(t.department || '—')}</span></td>
        <td><div class="d-flex flex-wrap" style="max-width: 320px;">${assignmentsBadges}</div></td>
        <td>${statusBadge}</td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-secondary py-0 px-2 small" onclick="openViewSubjectTeacherModal(${t.id})" title="View Details">
              <i class="bi bi-eye"></i>
            </button>
            <button class="btn btn-outline-primary py-0 px-2 small" onclick="openEditSubjectTeacherModal(${t.id})" title="Edit Teacher & Assignments">
              <i class="bi bi-pencil"></i>
            </button>
            ${toggleActionBtn}
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function createAssignmentRow(containerId, initialClassId = '', initialSubjectId = '') {
  const container = document.getElementById(containerId);
  if (!container) return;

  const rowId = `assign-row-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
  const rowDiv = document.createElement('div');
  rowDiv.className = 'row g-2 align-items-center assignment-row border rounded-2 p-2 bg-white';
  rowDiv.id = rowId;

  const classOptionsHtml = (availableAssignmentOptions.classes || []).map(c => `
    <option value="${c.id}" ${String(c.id) === String(initialClassId) ? 'selected' : ''}>
      ${escapeHtml(c.name)} (${escapeHtml(c.department || '')} - Yr ${c.year} Sec ${c.section})
    </option>
  `).join('');

  const subjectOptionsHtml = (availableAssignmentOptions.subjects || []).map(s => `
    <option value="${s.id}" ${String(s.id) === String(initialSubjectId) ? 'selected' : ''}>
      ${escapeHtml(s.code)} - ${escapeHtml(s.name)}
    </option>
  `).join('');

  rowDiv.innerHTML = `
    <div class="col-md-5">
      <select class="form-select form-select-sm assignment-class-select" required>
        <option value="">-- Select Class Section --</option>
        ${classOptionsHtml}
      </select>
    </div>
    <div class="col-md-5">
      <select class="form-select form-select-sm assignment-subject-select" required>
        <option value="">-- Select Subject --</option>
        ${subjectOptionsHtml}
      </select>
    </div>
    <div class="col-md-2 text-end">
      <button type="button" class="btn btn-outline-danger btn-sm w-100" onclick="document.getElementById('${rowId}').remove()" title="Remove this assignment">
        <i class="bi bi-trash"></i> Remove
      </button>
    </div>
  `;

  container.appendChild(rowDiv);
}

function openAddSubjectTeacherModal() {
  const form = document.getElementById('form-ct-add-teacher');
  if (form) form.reset();

  const container = document.getElementById('ct-add-assignments-list');
  if (container) {
    container.innerHTML = '';
    // Pre-populate with 1 empty assignment row for convenience
    createAssignmentRow('ct-add-assignments-list');
  }

  const pwdInput = document.getElementById('ct-add-teacher-password');
  if (pwdInput) pwdInput.type = 'password';

  const modalEl = document.getElementById('modal-ct-add-teacher');
  if (modalEl) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

async function openEditSubjectTeacherModal(teacherId) {
  let teacher = currentClassTeacherSubjectTeachers.find(t => t.id === teacherId);
  try {
    const fresh = await Api.getSubjectTeacherDetail(teacherId);
    if (fresh) teacher = fresh;
  } catch (e) {
    console.warn('Could not fetch fresh teacher details, falling back to cached:', e);
  }

  if (!teacher) {
    alert('Subject teacher details not found.');
    return;
  }

  document.getElementById('ct-edit-teacher-id').value = teacher.id;
  document.getElementById('ct-edit-teacher-name').value = teacher.full_name || '';
  document.getElementById('ct-edit-teacher-tid').value = teacher.teacher_id || '';
  document.getElementById('ct-edit-teacher-username').value = teacher.username || '';
  document.getElementById('ct-edit-teacher-email').value = teacher.email || '';
  document.getElementById('ct-edit-teacher-dept').value = teacher.department || '';
  document.getElementById('ct-edit-teacher-password').value = '';
  document.getElementById('ct-edit-teacher-active').checked = teacher.is_active !== false;

  const container = document.getElementById('ct-edit-assignments-list');
  if (container) {
    container.innerHTML = '';
    if (teacher.assignments && teacher.assignments.length > 0) {
      teacher.assignments.forEach(a => {
        createAssignmentRow('ct-edit-assignments-list', a.class_id, a.subject_id);
      });
    } else {
      createAssignmentRow('ct-edit-assignments-list');
    }
  }

  const modalEl = document.getElementById('modal-ct-edit-teacher');
  if (modalEl) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

async function openViewSubjectTeacherModal(teacherId) {
  let teacher = currentClassTeacherSubjectTeachers.find(t => t.id === teacherId);
  try {
    const fresh = await Api.getSubjectTeacherDetail(teacherId);
    if (fresh) teacher = fresh;
  } catch (e) {
    console.warn('Could not fetch fresh teacher details, falling back to cached:', e);
  }

  if (!teacher) return;

  const nameEl = document.getElementById('ct-view-t-name');
  const tidEl = document.getElementById('ct-view-t-tid');
  const userEl = document.getElementById('ct-view-t-username');
  const deptEl = document.getElementById('ct-view-t-dept');
  const statusEl = document.getElementById('ct-view-t-status');
  const emailEl = document.getElementById('ct-view-t-email');
  const tbody = document.getElementById('ct-view-t-assignments-body');

  if (nameEl) nameEl.textContent = teacher.full_name || 'Faculty Member';
  if (tidEl) tidEl.textContent = teacher.teacher_id || 'N/A';
  if (userEl) userEl.textContent = teacher.username || '';
  if (deptEl) deptEl.textContent = teacher.department || 'General';
  if (emailEl) emailEl.textContent = teacher.email || 'None';

  if (statusEl) {
    if (teacher.is_active) {
      statusEl.className = 'badge bg-success fs-6 px-3 py-2';
      statusEl.innerHTML = '<i class="bi bi-check-circle me-1"></i>Active';
    } else {
      statusEl.className = 'badge bg-danger fs-6 px-3 py-2';
      statusEl.innerHTML = '<i class="bi bi-slash-circle me-1"></i>Deactivated';
    }
  }

  if (tbody) {
    if (teacher.assignments && teacher.assignments.length > 0) {
      tbody.innerHTML = teacher.assignments.map(a => `
        <tr>
          <td class="fw-bold text-dark">${escapeHtml(a.class_name)}</td>
          <td><span class="text-secondary small">${escapeHtml(a.department || '—')} (Yr ${a.year || '—'})</span></td>
          <td><span class="badge bg-primary">${escapeHtml(a.subject_code)}</span></td>
          <td class="text-dark">${escapeHtml(a.subject_name)}</td>
        </tr>
      `).join('');
    } else {
      tbody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-muted">No course assignments mapped yet.</td></tr>`;
    }
  }

  const modalEl = document.getElementById('modal-ct-view-teacher');
  if (modalEl) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

async function toggleClassTeacherSubjectTeacherStatus(teacherId, teacherName, targetActive) {
  const actionText = targetActive ? 'activate' : 'deactivate';
  if (!confirm(`Are you sure you want to ${actionText} faculty account for "${teacherName}"?`)) {
    return;
  }

  try {
    const res = await Api.toggleSubjectTeacherStatus(teacherId);
    showClassTeacherAlert(res.message || `Teacher status updated.`, 'success');
    await loadClassTeacherSubjectTeachers();
  } catch (err) {
    showClassTeacherAlert(err.message, 'danger');
  }
}

function openAddStudentModal() {
  const form = document.getElementById('form-ct-add-student');
  if (form) form.reset();

  const classInput = document.getElementById('ct-add-student-class');
  if (classInput && currentClassTeacherClass) {
    classInput.value = currentClassTeacherClass.name;
  }

  const modalEl = document.getElementById('modal-ct-add-student');
  if (modalEl) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

function openEditStudentModal(studentId) {
  const student = currentClassTeacherStudents.find(s => s.id === studentId);
  if (!student) return;

  document.getElementById('ct-edit-student-id').value = student.id;
  document.getElementById('ct-edit-student-name').value = student.full_name;
  document.getElementById('ct-edit-student-roll').value = student.roll_number;
  document.getElementById('ct-edit-student-reg').value = student.register_number || '';
  document.getElementById('ct-edit-student-email').value = student.email || '';
  document.getElementById('ct-edit-student-phone').value = student.phone || '';
  document.getElementById('ct-edit-student-active').checked = student.is_active;

  const modalEl = document.getElementById('modal-ct-edit-student');
  if (modalEl) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

async function toggleClassStudentStatus(studentId) {
  try {
    const updated = await Api.toggleClassStudentStatus(studentId);
    showClassTeacherAlert(`Status for ${updated.full_name} updated to ${updated.is_active ? 'Active' : 'Inactive'}.`, 'success');
    await loadClassTeacherData();
  } catch (err) {
    showClassTeacherAlert(err.message, 'danger');
  }
}

async function deleteClassStudent(studentId, studentName) {
  if (!confirm(`Are you sure you want to delete student "${studentName}" from the class roster?`)) {
    return;
  }

  try {
    await Api.deleteClassStudent(studentId);
    showClassTeacherAlert(`Student ${studentName} successfully removed.`, 'success');
    await loadClassTeacherData();
  } catch (err) {
    showClassTeacherAlert(err.message, 'danger');
  }
}

function openUploadFaceModal(studentId) {
  const student = currentClassTeacherStudents.find(s => s.id === studentId);
  if (!student) return;

  selectedFaceUploadStudent = student;
  selectedFaceFile = null;

  document.getElementById('ct-upload-face-student-id').value = student.id;
  document.getElementById('ct-upload-face-student-name').textContent = student.full_name;
  document.getElementById('ct-upload-face-student-roll').textContent = `Roll No: ${student.roll_number}`;

  const currentBadge = document.getElementById('ct-upload-face-current-badge');
  if (currentBadge) {
    if (student.face_enrolled) {
      currentBadge.className = 'enrollment-badge-enrolled';
      currentBadge.innerHTML = '<i class="bi bi-check-circle-fill"></i> Currently Enrolled';
    } else {
      currentBadge.className = 'enrollment-badge-pending';
      currentBadge.innerHTML = '<i class="bi bi-hourglass-split"></i> Pending Enrollment';
    }
  }

  // Reset file input & live preview
  const fileInput = document.getElementById('ct-face-file-input');
  if (fileInput) fileInput.value = '';

  const previewContainer = document.getElementById('ct-face-preview-container');
  if (previewContainer) previewContainer.classList.add('d-none');

  const submitBtn = document.getElementById('btn-ct-submit-face');
  if (submitBtn) submitBtn.disabled = true;

  const modalEl = document.getElementById('modal-ct-upload-face');
  if (modalEl) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

function handleFaceFileSelected(file) {
  if (!file) return;

  // 1. File Type validation
  const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
  const validExts = ['.jpg', '.jpeg', '.png', '.webp'];

  if (!validTypes.includes(file.type) && !validExts.includes(ext)) {
    alert('Invalid file format. Please upload a JPEG, PNG, or WebP image.');
    return;
  }

  // 2. File Size validation (5MB max)
  const maxSize = 5 * 1024 * 1024;
  if (file.size > maxSize) {
    alert('File size exceeds the 5MB maximum limit. Please choose a smaller photo.');
    return;
  }
  if (file.size === 0) {
    alert('Uploaded file is empty.');
    return;
  }

  selectedFaceFile = file;

  // Live preview
  const reader = new FileReader();
  reader.onload = (e) => {
    const previewImg = document.getElementById('ct-face-preview-img');
    const previewName = document.getElementById('ct-face-preview-filename');
    const previewSize = document.getElementById('ct-face-preview-size');
    const previewContainer = document.getElementById('ct-face-preview-container');
    const submitBtn = document.getElementById('btn-ct-submit-face');

    if (previewImg) previewImg.src = e.target.result;
    if (previewName) previewName.textContent = file.name;
    if (previewSize) previewSize.textContent = `${(file.size / 1024).toFixed(1)} KB`;
    if (previewContainer) previewContainer.classList.remove('d-none');
    if (submitBtn) submitBtn.disabled = false;
  };
  reader.readAsDataURL(file);
}

function openViewFaceModal(studentId) {
  const student = currentClassTeacherStudents.find(s => s.id === studentId);
  if (!student) return;

  if (!student.face_image_path) {
    // If not enrolled yet, direct to upload modal
    openUploadFaceModal(studentId);
    return;
  }

  const imgEl = document.getElementById('ct-view-face-img');
  const nameEl = document.getElementById('ct-view-student-name');
  const rollEl = document.getElementById('ct-view-student-roll');
  const replaceBtn = document.getElementById('btn-ct-replace-face-photo');

  if (imgEl) imgEl.src = student.face_image_path;
  if (nameEl) nameEl.textContent = student.full_name;
  if (rollEl) rollEl.textContent = `Roll No: ${student.roll_number} • ${student.class_name || ''}`;

  if (replaceBtn) {
    replaceBtn.onclick = () => {
      const viewModalEl = document.getElementById('modal-ct-view-face');
      const viewModal = bootstrap.Modal.getInstance(viewModalEl);
      if (viewModal) viewModal.hide();
      openUploadFaceModal(studentId);
    };
  }

  const modalEl = document.getElementById('modal-ct-view-face');
  if (modalEl) {
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }
}

function initClassTeacherPortal() {
  // 1. Refresh Button
  const refreshBtn = document.getElementById('btn-ct-refresh');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => loadClassTeacherData());
  }

  // 2. Open Add Student modal buttons
  const openAddBtn1 = document.getElementById('btn-ct-open-add-student');
  const openAddBtn2 = document.getElementById('btn-ct-add-student-sm');
  if (openAddBtn1) openAddBtn1.addEventListener('click', openAddStudentModal);
  if (openAddBtn2) openAddBtn2.addEventListener('click', openAddStudentModal);

  // 3. Filters & Search
  const searchInput = document.getElementById('ct-student-search');
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => filterAndRenderClassTeacherStudents(), 250);
    });
  }

  const statusFilter = document.getElementById('ct-student-status-filter');
  if (statusFilter) {
    statusFilter.addEventListener('change', () => filterAndRenderClassTeacherStudents());
  }

  const faceFilter = document.getElementById('ct-student-face-filter');
  if (faceFilter) {
    faceFilter.addEventListener('change', () => filterAndRenderClassTeacherStudents());
  }

  // 4. Add Student Form Submit
  const addForm = document.getElementById('form-ct-add-student');
  if (addForm) {
    addForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('btn-ct-submit-add-student');
      const originalText = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Creating...';

      const payload = {
        name: document.getElementById('ct-add-student-name').value.trim(),
        roll_number: document.getElementById('ct-add-student-roll').value.trim(),
        register_number: document.getElementById('ct-add-student-reg').value.trim() || undefined,
        email: document.getElementById('ct-add-student-email').value.trim() || undefined,
        phone: document.getElementById('ct-add-student-phone').value.trim() || undefined,
      };

      try {
        const student = await Api.addClassStudent(payload);
        showClassTeacherAlert(`Student ${student.full_name} (${student.roll_number}) added successfully!`, 'success');

        const modalEl = document.getElementById('modal-ct-add-student');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();

        await loadClassTeacherData();
      } catch (err) {
        alert(`Error: ${err.message}`);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
      }
    });
  }

  // 5. Edit Student Form Submit
  const editForm = document.getElementById('form-ct-edit-student');
  if (editForm) {
    editForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const studentId = parseInt(document.getElementById('ct-edit-student-id').value, 10);
      const submitBtn = document.getElementById('btn-ct-submit-edit-student');
      const originalText = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Saving...';

      const payload = {
        name: document.getElementById('ct-edit-student-name').value.trim(),
        roll_number: document.getElementById('ct-edit-student-roll').value.trim(),
        register_number: document.getElementById('ct-edit-student-reg').value.trim() || undefined,
        email: document.getElementById('ct-edit-student-email').value.trim() || undefined,
        phone: document.getElementById('ct-edit-student-phone').value.trim() || undefined,
        is_active: document.getElementById('ct-edit-student-active').checked,
      };

      try {
        const updated = await Api.editClassStudent(studentId, payload);
        showClassTeacherAlert(`Student ${updated.full_name} (${updated.roll_number}) updated successfully!`, 'success');

        const modalEl = document.getElementById('modal-ct-edit-student');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();

        await loadClassTeacherData();
      } catch (err) {
        alert(`Error: ${err.message}`);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
      }
    });
  }

  // 6. Upload Face Modal Drag-and-Drop & File Picker
  const dropZone = document.getElementById('ct-face-drop-zone');
  const fileInput = document.getElementById('ct-face-file-input');
  const removeFileBtn = document.getElementById('btn-ct-remove-selected-file');
  const faceUploadForm = document.getElementById('form-ct-upload-face');

  if (dropZone && fileInput) {
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFaceFileSelected(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFaceFileSelected(e.target.files[0]);
      }
    });
  }

  if (removeFileBtn) {
    removeFileBtn.addEventListener('click', () => {
      selectedFaceFile = null;
      if (fileInput) fileInput.value = '';
      const previewContainer = document.getElementById('ct-face-preview-container');
      if (previewContainer) previewContainer.classList.add('d-none');
      const submitBtn = document.getElementById('btn-ct-submit-face');
      if (submitBtn) submitBtn.disabled = true;
    });
  }

  if (faceUploadForm) {
    faceUploadForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!selectedFaceUploadStudent || !selectedFaceFile) {
        alert('Please choose or drop a student face photo first.');
        return;
      }

      const submitBtn = document.getElementById('btn-ct-submit-face');
      const originalText = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Uploading & Enrolling...';

      try {
        const response = await Api.uploadStudentFace(selectedFaceUploadStudent.id, selectedFaceFile);
        showClassTeacherAlert(`Face photo for ${selectedFaceUploadStudent.full_name} uploaded and enrolled!`, 'success');

        const modalEl = document.getElementById('modal-ct-upload-face');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();

        await loadClassTeacherData();
      } catch (err) {
        alert(`Upload failed: ${err.message}`);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
      }
    });
  }

  // 7. Subject Teacher Management: Buttons, Search, & Filters
  const btnOpenAddTeacher = document.getElementById('btn-ct-open-add-teacher');
  if (btnOpenAddTeacher) {
    btnOpenAddTeacher.addEventListener('click', openAddSubjectTeacherModal);
  }

  const btnRefreshTeachers = document.getElementById('btn-ct-refresh-teachers');
  if (btnRefreshTeachers) {
    btnRefreshTeachers.addEventListener('click', loadClassTeacherSubjectTeachers);
  }

  const teacherSearch = document.getElementById('ct-teacher-search');
  if (teacherSearch) {
    let debounceTimer;
    teacherSearch.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => filterAndRenderClassTeacherSubjectTeachers(), 250);
    });
  }

  const teacherStatusFilter = document.getElementById('ct-teacher-status-filter');
  if (teacherStatusFilter) {
    teacherStatusFilter.addEventListener('change', () => filterAndRenderClassTeacherSubjectTeachers());
  }

  const btnAddAssignRow = document.getElementById('btn-ct-add-assignment-row');
  if (btnAddAssignRow) {
    btnAddAssignRow.addEventListener('click', () => createAssignmentRow('ct-add-assignments-list'));
  }

  const btnEditAddAssignRow = document.getElementById('btn-ct-edit-add-assignment-row');
  if (btnEditAddAssignRow) {
    btnEditAddAssignRow.addEventListener('click', () => createAssignmentRow('ct-edit-assignments-list'));
  }

  const btnToggleAddTeacherPwd = document.getElementById('btn-toggle-add-teacher-pwd');
  if (btnToggleAddTeacherPwd) {
    btnToggleAddTeacherPwd.addEventListener('click', () => {
      const pwdInput = document.getElementById('ct-add-teacher-password');
      if (!pwdInput) return;
      const isPwd = pwdInput.type === 'password';
      pwdInput.type = isPwd ? 'text' : 'password';
      btnToggleAddTeacherPwd.innerHTML = isPwd ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
    });
  }

  // 8. Add Subject Teacher Form Submit
  const addTeacherForm = document.getElementById('form-ct-add-teacher');
  if (addTeacherForm) {
    addTeacherForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('btn-ct-submit-add-teacher');
      const originalText = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Creating...';

      // Gather assignments from rows
      const rows = document.querySelectorAll('#ct-add-assignments-list .assignment-row');
      const assignments = [];
      rows.forEach(r => {
        const cVal = r.querySelector('.assignment-class-select').value;
        const sVal = r.querySelector('.assignment-subject-select').value;
        if (cVal && sVal) {
          assignments.push({
            class_id: parseInt(cVal, 10),
            subject_id: parseInt(sVal, 10)
          });
        }
      });

      const payload = {
        name: document.getElementById('ct-add-teacher-name').value.trim(),
        teacher_id: document.getElementById('ct-add-teacher-tid').value.trim(),
        username: document.getElementById('ct-add-teacher-username').value.trim(),
        password: document.getElementById('ct-add-teacher-password').value,
        email: document.getElementById('ct-add-teacher-email').value.trim() || undefined,
        department: document.getElementById('ct-add-teacher-dept').value.trim() || undefined,
        assignments: assignments
      };

      try {
        const created = await Api.createSubjectTeacher(payload);
        showClassTeacherAlert(`Subject Teacher ${created.full_name} (${created.teacher_id}) created successfully!`, 'success');
        const modalEl = document.getElementById('modal-ct-add-teacher');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();

        await loadClassTeacherSubjectTeachers();
      } catch (err) {
        alert(`Error creating teacher: ${err.message}`);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
      }
    });
  }

  // 9. Edit Subject Teacher Form Submit
  const editTeacherForm = document.getElementById('form-ct-edit-teacher');
  if (editTeacherForm) {
    editTeacherForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const teacherId = parseInt(document.getElementById('ct-edit-teacher-id').value, 10);
      const submitBtn = document.getElementById('btn-ct-submit-edit-teacher');
      const originalText = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Saving...';

      // Gather assignments
      const rows = document.querySelectorAll('#ct-edit-assignments-list .assignment-row');
      const assignments = [];
      rows.forEach(r => {
        const cVal = r.querySelector('.assignment-class-select').value;
        const sVal = r.querySelector('.assignment-subject-select').value;
        if (cVal && sVal) {
          assignments.push({
            class_id: parseInt(cVal, 10),
            subject_id: parseInt(sVal, 10)
          });
        }
      });

      const pwdVal = document.getElementById('ct-edit-teacher-password').value;
      const payload = {
        name: document.getElementById('ct-edit-teacher-name').value.trim(),
        teacher_id: document.getElementById('ct-edit-teacher-tid').value.trim(),
        username: document.getElementById('ct-edit-teacher-username').value.trim() || undefined,
        email: document.getElementById('ct-edit-teacher-email').value.trim() || undefined,
        department: document.getElementById('ct-edit-teacher-dept').value.trim() || undefined,
        is_active: document.getElementById('ct-edit-teacher-active').checked,
        assignments: assignments
      };
      if (pwdVal && pwdVal.trim().length > 0) {
        payload.password = pwdVal;
      }

      try {
        const updated = await Api.updateSubjectTeacher(teacherId, payload);
        showClassTeacherAlert(`Subject Teacher ${updated.full_name} updated successfully!`, 'success');
        const modalEl = document.getElementById('modal-ct-edit-teacher');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();

        await loadClassTeacherSubjectTeachers();
      } catch (err) {
        alert(`Error updating teacher: ${err.message}`);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
      }
    });
  }
}

// Expose handlers to window for inline onclick attributes
window.openAddStudentModal = openAddStudentModal;
window.openEditStudentModal = openEditStudentModal;
window.openUploadFaceModal = openUploadFaceModal;
window.openViewFaceModal = openViewFaceModal;
window.toggleClassStudentStatus = toggleClassStudentStatus;
window.deleteClassStudent = deleteClassStudent;
window.loadClassTeacherData = loadClassTeacherData;
window.openAddSubjectTeacherModal = openAddSubjectTeacherModal;
window.openEditSubjectTeacherModal = openEditSubjectTeacherModal;
window.openViewSubjectTeacherModal = openViewSubjectTeacherModal;
window.toggleClassTeacherSubjectTeacherStatus = toggleClassTeacherSubjectTeacherStatus;
window.loadClassTeacherSubjectTeachers = loadClassTeacherSubjectTeachers;


/* ========================================================
   SUBJECT TEACHER PORTAL & ATTENDANCE CAMERA ENGINE
   ======================================================== */

let subjectTeacherState = {
  teacherName: '',
  role: '',
  assignedSubjects: [],
  assignedClasses: [],
  availableClasses: [],
  availableSubjects: [],
  selectedClassId: null,
  selectedSubjectId: null,
  selectedPeriod: 1,
  selectedDate: new Date().toISOString().split('T')[0],
  cameraStream: null,
  currentFacingMode: 'environment', // rear mobile camera
  capturedImageBlob: null,
  capturedImageUrl: null,
  previewData: null,
  confirmedRecords: [],
};

async function loadSubjectTeacherData() {
  try {
    const data = await Api.getSubjectTeacherClasses();
    subjectTeacherState.teacherName = data.teacher_name || 'Faculty Member';
    subjectTeacherState.role = data.role || 'SUBJECT_TEACHER';
    subjectTeacherState.assignedSubjects = data.assigned_subjects || [];
    subjectTeacherState.assignedClasses = data.assigned_classes || [];
    subjectTeacherState.availableClasses = data.available_classes || [];
    subjectTeacherState.availableSubjects = data.available_subjects || [];

    // Update Header Pill
    const teacherNameBadge = document.getElementById('st-header-teacher-name');
    if (teacherNameBadge) {
      teacherNameBadge.innerHTML = `<i class="bi bi-person-fill text-primary me-1"></i>${escapeHtml(subjectTeacherState.teacherName)}`;
    }

    // Initialize session date if not already set
    const dateInput = document.getElementById('st-session-date');
    if (dateInput && !dateInput.value) {
      dateInput.value = subjectTeacherState.selectedDate;
    }

    // Populate Class dropdown
    populateClassDropdown();

    // Render Tab 2: Assigned Cards
    renderAssignedCards();

    // Render Tab 3: Attendance Dashboard & Records
    await loadSubjectTeacherDashboard();
  } catch (err) {
    console.error('Failed to load subject teacher data:', err);
  }
}

function populateClassDropdown() {
  const selectClass = document.getElementById('st-select-class');
  if (!selectClass) return;

  const classesToUse = subjectTeacherState.assignedClasses.length > 0
    ? subjectTeacherState.assignedClasses
    : subjectTeacherState.availableClasses;

  selectClass.innerHTML = '';
  if (classesToUse.length === 0) {
    selectClass.innerHTML = '<option value="">No classes found</option>';
    return;
  }

  classesToUse.forEach((c, idx) => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = `${c.name} (${c.department} - Yr ${c.year} Sec ${c.section})`;
    if (idx === 0) opt.selected = true;
    selectClass.appendChild(opt);
  });

  subjectTeacherState.selectedClassId = parseInt(selectClass.value);
  populateSubjectDropdown();
}

function populateSubjectDropdown() {
  const selectSubject = document.getElementById('st-select-subject');
  if (!selectSubject) return;

  const currentClassId = subjectTeacherState.selectedClassId;
  // Filter assigned subjects matching this class, or all assigned subjects
  let matchingSubjects = subjectTeacherState.assignedSubjects.filter(
    s => s.class_id === currentClassId
  );

  if (matchingSubjects.length === 0) {
    // Fallback to all assigned subjects or available subjects
    matchingSubjects = subjectTeacherState.assignedSubjects.length > 0
      ? subjectTeacherState.assignedSubjects
      : subjectTeacherState.availableSubjects.map(s => ({ subject_id: s.id, subject_name: s.name, subject_code: s.code }));
  }

  // Deduplicate by subject_id
  const seen = new Set();
  const uniqueSubjects = [];
  matchingSubjects.forEach(s => {
    const sid = s.subject_id || s.id;
    if (!seen.has(sid)) {
      seen.add(sid);
      uniqueSubjects.push(s);
    }
  });

  selectSubject.innerHTML = '';
  if (uniqueSubjects.length === 0) {
    selectSubject.innerHTML = '<option value="">No subjects found</option>';
    return;
  }

  uniqueSubjects.forEach((s, idx) => {
    const sid = s.subject_id || s.id;
    const sname = s.subject_name || s.name;
    const scode = s.subject_code || s.code || '';
    const opt = document.createElement('option');
    opt.value = sid;
    opt.textContent = scode ? `${sname} (${scode})` : sname;
    if (idx === 0) opt.selected = true;
    selectSubject.appendChild(opt);
  });

  subjectTeacherState.selectedSubjectId = parseInt(selectSubject.value);
}

function renderAssignedCards() {
  const container = document.getElementById('st-assigned-cards-container');
  if (!container) return;

  if (subjectTeacherState.assignedSubjects.length === 0) {
    container.innerHTML = `
      <div class="col-12 text-center py-4 text-muted">
        <i class="bi bi-info-circle display-6 d-block mb-2 text-secondary"></i>
        <h6>No explicit course assignments found</h6>
        <p class="small text-secondary mb-0">Use the class session selector to conduct attendance for any class section.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = subjectTeacherState.assignedSubjects.map(item => `
    <div class="col-md-6 col-lg-4">
      <div class="card border rounded-3 p-3 h-100 shadow-sm">
        <div class="d-flex justify-content-between align-items-start mb-2">
          <span class="badge bg-primary-subtle text-primary border border-primary-subtle px-2 py-1">
            ${escapeHtml(item.subject_code || 'COURSE')}
          </span>
          <span class="badge bg-light text-secondary border">Sec ${escapeHtml(item.section || 'A')}</span>
        </div>
        <h6 class="fw-bold mb-1 text-dark">${escapeHtml(item.subject_name || item.name)}</h6>
        <p class="text-secondary small mb-3">
          <i class="bi bi-mortarboard me-1"></i>${escapeHtml(item.class_name || item.class || 'Class Section')}
        </p>
        <button class="btn btn-outline-primary btn-sm w-100 mt-auto" onclick="quickStartSubjectAttendance(${item.class_id}, ${item.subject_id})">
          <i class="bi bi-camera-fill me-1"></i>Take Attendance
        </button>
      </div>
    </div>
  `).join('');
}

function quickStartSubjectAttendance(classId, subjectId) {
  // Switch to Tab 1
  const tabBtn = document.getElementById('st-tab-btn-take');
  if (tabBtn) tabBtn.click();

  // Select class
  const classSelect = document.getElementById('st-select-class');
  if (classSelect) {
    classSelect.value = classId;
    subjectTeacherState.selectedClassId = classId;
    populateSubjectDropdown();
  }

  // Select subject
  const subjectSelect = document.getElementById('st-select-subject');
  if (subjectSelect) {
    subjectSelect.value = subjectId;
    subjectTeacherState.selectedSubjectId = subjectId;
  }

  // Advance to camera step
  goToCameraStep();
}

function goToCameraStep() {
  const classSelect = document.getElementById('st-select-class');
  const subjectSelect = document.getElementById('st-select-subject');
  const dateInput = document.getElementById('st-session-date');

  if (!classSelect || !classSelect.value) {
    showToast('warning', 'Selection Required', 'Please select an assigned class first.');
    return;
  }
  if (!subjectSelect || !subjectSelect.value) {
    showToast('warning', 'Selection Required', 'Please select a subject course first.');
    return;
  }

  subjectTeacherState.selectedClassId = parseInt(classSelect.value);
  subjectTeacherState.selectedSubjectId = parseInt(subjectSelect.value);
  subjectTeacherState.selectedDate = (dateInput && dateInput.value) ? dateInput.value : new Date().toISOString().split('T')[0];

  const className = classSelect.options[classSelect.selectedIndex].text;
  const subjectName = subjectSelect.options[subjectSelect.selectedIndex].text;

  // Update session summary label
  const summaryLabel = document.getElementById('st-session-summary-label');
  if (summaryLabel) {
    summaryLabel.textContent = `${className} • ${subjectName} • Period ${subjectTeacherState.selectedPeriod} • ${subjectTeacherState.selectedDate}`;
  }

  // Update linear 7-step guide
  updateAttendanceStepper(4);

  // Update legacy step indicators for compatibility
  const step1 = document.getElementById('st-wiz-step-1');
  const step2 = document.getElementById('st-wiz-step-2');
  const step3 = document.getElementById('st-wiz-step-3');
  if (step1) { step1.classList.remove('active'); step1.classList.add('completed'); }
  if (step2) { step2.classList.add('active'); step2.classList.remove('completed'); }
  if (step3) { step3.classList.remove('active', 'completed'); }

  // Toggle step cards
  document.getElementById('st-step-session-card')?.classList.add('d-none');
  document.getElementById('st-step-camera-card')?.classList.remove('d-none');
  document.getElementById('st-step-preview-card')?.classList.add('d-none');
  document.getElementById('st-step-success-card')?.classList.add('d-none');
}

function backToSessionStep() {
  stopLiveCamera();
  updateAttendanceStepper(1);

  const step1 = document.getElementById('st-wiz-step-1');
  const step2 = document.getElementById('st-wiz-step-2');
  if (step1) { step1.classList.add('active'); step1.classList.remove('completed'); }
  if (step2) { step2.classList.remove('active', 'completed'); }

  document.getElementById('st-step-session-card')?.classList.remove('d-none');
  document.getElementById('st-step-camera-card')?.classList.add('d-none');
}

async function startLiveCamera() {
  const alertEl = document.getElementById('st-camera-alert');
  if (alertEl) alertEl.classList.add('d-none');

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    if (alertEl) {
      alertEl.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-1"></i> Browser camera API is not supported in this environment. Please use the file upload option below.';
      alertEl.classList.remove('d-none');
    }
    showToast('error', 'Camera Unsupported', 'Browser camera API is not available. Please upload a classroom photo.');
    return;
  }

  try {
    stopLiveCamera();

    const constraints = {
      video: {
        facingMode: { ideal: subjectTeacherState.currentFacingMode },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    };

    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    subjectTeacherState.cameraStream = stream;

    const videoEl = document.getElementById('st-camera-video');
    if (videoEl) {
      videoEl.srcObject = stream;
      await videoEl.play();
    }

    document.getElementById('st-camera-trigger-box')?.classList.add('d-none');
    document.getElementById('st-live-camera-container')?.classList.remove('d-none');
    showToast('info', 'Camera Active', 'Live camera stream started. Tap shutter to capture.');
  } catch (err) {
    console.error('Camera access failed:', err);
    if (alertEl) {
      alertEl.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> Camera access error: ${err.message || 'Permission denied'}. Please use the file upload option.`;
      alertEl.classList.remove('d-none');
    }
    showToast('warning', 'Camera Access Failed', 'Permission denied or device in use. Please select photo from storage.');
    stopLiveCamera();
  }
}

function stopLiveCamera() {
  if (subjectTeacherState.cameraStream) {
    subjectTeacherState.cameraStream.getTracks().forEach(track => track.stop());
    subjectTeacherState.cameraStream = null;
  }
  const videoEl = document.getElementById('st-camera-video');
  if (videoEl) {
    videoEl.srcObject = null;
  }
  document.getElementById('st-live-camera-container')?.classList.add('d-none');
  document.getElementById('st-camera-trigger-box')?.classList.remove('d-none');
}

async function flipCamera() {
  subjectTeacherState.currentFacingMode = (subjectTeacherState.currentFacingMode === 'environment')
    ? 'user'
    : 'environment';
  await startLiveCamera();
  showToast('info', 'Camera Flipped', `Switched to ${subjectTeacherState.currentFacingMode === 'user' ? 'front' : 'rear'} camera.`);
}

function captureCameraFrame() {
  const videoEl = document.getElementById('st-camera-video');
  const canvasEl = document.getElementById('st-camera-canvas');
  if (!videoEl || !canvasEl) return;

  const w = videoEl.videoWidth || 640;
  const h = videoEl.videoHeight || 480;
  canvasEl.width = w;
  canvasEl.height = h;

  const ctx = canvasEl.getContext('2d');
  ctx.drawImage(videoEl, 0, 0, w, h);

  canvasEl.toBlob((blob) => {
    if (!blob) return;
    subjectTeacherState.capturedImageBlob = blob;
    if (subjectTeacherState.capturedImageUrl) {
      URL.revokeObjectURL(subjectTeacherState.capturedImageUrl);
    }
    subjectTeacherState.capturedImageUrl = URL.createObjectURL(blob);

    const imgPreview = document.getElementById('st-captured-photo');
    if (imgPreview) {
      imgPreview.src = subjectTeacherState.capturedImageUrl;
    }

    stopLiveCamera();
    document.getElementById('st-captured-preview-container')?.classList.remove('d-none');
    showToast('success', 'Photo Captured', 'Classroom photo ready. Tap Analyze to detect faces.');
  }, 'image/jpeg', 0.92);
}

function handleFileInputPhoto(file) {
  if (!file) return;
  subjectTeacherState.capturedImageBlob = file;
  if (subjectTeacherState.capturedImageUrl) {
    URL.revokeObjectURL(subjectTeacherState.capturedImageUrl);
  }
  subjectTeacherState.capturedImageUrl = URL.createObjectURL(file);

  const imgPreview = document.getElementById('st-captured-photo');
  if (imgPreview) {
    imgPreview.src = subjectTeacherState.capturedImageUrl;
  }
  document.getElementById('st-captured-preview-container')?.classList.remove('d-none');
  showToast('info', 'Photo Selected', `${file.name} ready for computer vision analysis.`);
}

function retakePhoto() {
  subjectTeacherState.capturedImageBlob = null;
  if (subjectTeacherState.capturedImageUrl) {
    URL.revokeObjectURL(subjectTeacherState.capturedImageUrl);
    subjectTeacherState.capturedImageUrl = null;
  }
  const fileInput = document.getElementById('st-file-photo');
  if (fileInput) fileInput.value = '';

  document.getElementById('st-captured-preview-container')?.classList.add('d-none');
  showToast('info', 'Photo Cleared', 'You can take a new photo or choose a different file.');
}

async function analyzeClassroomPhotoAction() {
  if (!subjectTeacherState.capturedImageBlob) {
    showToast('warning', 'Photo Required', 'Please capture or choose a classroom photo first.');
    return;
  }

  // Show CV Scanner radar modal overlay
  const cvModal = document.getElementById('cv-scanner-modal');
  if (cvModal) cvModal.classList.remove('d-none');

  // Advance to Step 3 Preview Card
  document.getElementById('st-step-camera-card')?.classList.add('d-none');
  const previewCard = document.getElementById('st-step-preview-card');
  if (previewCard) previewCard.classList.remove('d-none');

  updateAttendanceStepper(5);

  const step2 = document.getElementById('st-wiz-step-2');
  const step3 = document.getElementById('st-wiz-step-3');
  if (step2) { step2.classList.remove('active'); step2.classList.add('completed'); }
  if (step3) { step3.classList.add('active'); step3.classList.remove('completed'); }

  const spinner = document.getElementById('st-analyzing-spinner');
  const details = document.getElementById('st-preview-details-container');
  if (spinner) spinner.classList.remove('d-none');
  if (details) details.classList.add('d-none');

  const formData = new FormData();
  formData.append('class_id', subjectTeacherState.selectedClassId);
  formData.append('subject_id', subjectTeacherState.selectedSubjectId);
  formData.append('period', subjectTeacherState.selectedPeriod);
  formData.append('date_str', subjectTeacherState.selectedDate);
  formData.append('photo', subjectTeacherState.capturedImageBlob, 'classroom_photo.jpg');

  try {
    const res = await Api.analyzeClassroomPhoto(formData);
    subjectTeacherState.previewData = res;

    // Build editable confirmedRecords array for human review
    subjectTeacherState.confirmedRecords = res.preview_records.map(p => ({
      student_id: p.student_id,
      class_id: res.class_id,
      subject_id: res.subject_id,
      date: res.date,
      period: res.period,
      status: p.status, // "PRESENT" or "ABSENT"
      confidence: p.similarity,
      attendance_image_id: res.attendance_image_id,
      bounding_box: p.bounding_box,
      is_manual: false,
      roll_number: p.roll_number,
      full_name: p.full_name,
      face_enrolled: p.face_enrolled,
      is_detected: p.is_detected,
    }));

    if (spinner) spinner.classList.add('d-none');
    if (details) details.classList.remove('d-none');
    if (cvModal) cvModal.classList.add('d-none');

    updateAttendanceStepper(6);

    // Update Header labels
    document.getElementById('st-preview-header-title').textContent = `${res.class_name} • ${res.subject_name}`;
    document.getElementById('st-preview-header-meta').textContent = `Period ${res.period} • Date: ${res.date} • Analyzed ${res.total_faces_detected} face(s)`;
    document.getElementById('st-confirm-period-text').textContent = res.period;

    // Unknown detections alert
    const unknownAlert = document.getElementById('st-preview-unknown-alert');
    const unknownText = document.getElementById('st-preview-unknown-text');
    if (unknownAlert && unknownText) {
      if (res.unknown_count > 0) {
        unknownText.textContent = `Notice: ${res.unknown_count} face(s) in the classroom photo could not be confidently identified. Please review the roster below and adjust manual toggles if needed.`;
        unknownAlert.classList.remove('d-none');
      } else {
        unknownAlert.classList.add('d-none');
      }
    }

    // Populate Annotated AI Detection Result Image
    const resultImg = document.getElementById('st-result-annotated-photo');
    if (resultImg) {
      resultImg.src = res.annotated_image_url || res.image_url;
    }
    const btnAnn = document.getElementById('btn-show-annotated-img');
    const btnOrig = document.getElementById('btn-show-original-img');
    btnAnn?.classList.add('active', 'btn-primary');
    btnAnn?.classList.remove('btn-outline-secondary');
    btnOrig?.classList.remove('active', 'btn-primary');
    btnOrig?.classList.add('btn-outline-secondary');

    updatePreviewKPIs();
    renderStudentPreviewRoster();

    showToast('success', 'Analysis Completed', `Found ${res.total_faces_detected} face(s) • ${res.recognized_count} recognized students.`);
  } catch (err) {
    if (cvModal) cvModal.classList.add('d-none');
    if (spinner) spinner.classList.add('d-none');
    showToast('error', 'Analysis Failed', err.message || 'Computer Vision analysis failed.');
    // Return to camera step
    document.getElementById('st-step-camera-card')?.classList.remove('d-none');
    if (previewCard) previewCard.classList.add('d-none');
    if (step2) { step2.classList.add('active'); step2.classList.remove('completed'); }
    if (step3) { step3.classList.remove('active'); }
    updateAttendanceStepper(4);
  }
}

function updatePreviewKPIs() {
  const records = subjectTeacherState.confirmedRecords;
  const presentCount = records.filter(r => r.status === 'PRESENT').length;
  const absentCount = records.length - presentCount;
  const totalStudents = records.length;
  const preview = subjectTeacherState.previewData;

  const totalEl = document.getElementById('st-preview-total-count');
  const facesEl = document.getElementById('st-preview-faces-count');
  const recognizedEl = document.getElementById('st-preview-recognized-count');
  const unknownEl = document.getElementById('st-preview-unknown-count');
  const presentEl = document.getElementById('st-preview-present-count');
  const absentEl = document.getElementById('st-preview-absent-count');
  const rateEl = document.getElementById('st-preview-rate');

  if (totalEl) totalEl.textContent = preview ? (preview.total_students_in_class ?? totalStudents) : totalStudents;
  if (facesEl) facesEl.textContent = preview ? preview.total_faces_detected : 0;
  if (recognizedEl) recognizedEl.textContent = preview ? preview.recognized_count : presentCount;
  if (unknownEl) unknownEl.textContent = preview ? preview.unknown_count : 0;
  if (presentEl) presentEl.textContent = presentCount;
  if (absentEl) absentEl.textContent = absentCount;
  if (rateEl) {
    const rate = totalStudents > 0 ? Math.round((presentCount / totalStudents) * 100) : 0;
    rateEl.textContent = `${rate}%`;
  }
}

function renderStudentPreviewRoster() {
  const tbody = document.getElementById('st-preview-table-body');
  const cardGrid = document.getElementById('st-preview-cards-container');

  const searchVal = (document.getElementById('st-preview-search')?.value || '').toLowerCase().trim();
  const records = subjectTeacherState.confirmedRecords.filter(r => {
    if (!searchVal) return true;
    return r.full_name.toLowerCase().includes(searchVal) || r.roll_number.toLowerCase().includes(searchVal);
  });

  // Empty State Rendering
  if (records.length === 0) {
    const emptyMarkup = `
      <div class="empty-state-box my-3 py-4">
        <div class="empty-state-icon-circle"><i class="bi bi-people"></i></div>
        <h6 class="fw-bold text-dark">No Students Found</h6>
        <p class="text-secondary small mb-0">No enrolled students matched your search "${escapeHtml(searchVal)}".</p>
      </div>
    `;
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center p-0 border-0">${emptyMarkup}</td></tr>`;
    }
    if (cardGrid) {
      cardGrid.innerHTML = emptyMarkup;
    }
    return;
  }

  // Desktop Table Rendering
  if (tbody) {
    tbody.innerHTML = records.map((r, idx) => {
      const isPresent = r.status === 'PRESENT';
      const statusBadge = isPresent
        ? `<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1"><i class="bi bi-check-circle-fill me-1"></i>PRESENT</span>`
        : `<span class="badge bg-danger-subtle text-danger border border-danger-subtle px-2 py-1"><i class="bi bi-x-circle-fill me-1"></i>ABSENT</span>`;

      let confidenceBadge = '-';
      if (r.is_manual) {
        confidenceBadge = `<span class="badge bg-warning-subtle text-dark border"><i class="bi bi-pencil-fill me-1"></i>Manual Override</span>`;
      } else if (isPresent && r.confidence > 0) {
        const pctVal = r.confidence <= 1.0 ? (r.confidence * 100) : r.confidence;
        const pct = pctVal.toFixed(1);
        confidenceBadge = `<span class="badge bg-primary-subtle text-primary border"><i class="bi bi-shield-check me-1"></i>${pct}% Match</span>`;
      }

      const faceBadge = r.face_enrolled
        ? `<span class="text-success small fw-medium"><i class="bi bi-check-circle me-1"></i>Enrolled</span>`
        : `<span class="text-secondary small"><i class="bi bi-dash-circle me-1"></i>Pending</span>`;

      const toggleBtnClass = isPresent ? 'btn-outline-danger' : 'btn-outline-success';
      const toggleBtnText = isPresent ? '<i class="bi bi-person-x me-1"></i>Mark Absent' : '<i class="bi bi-person-check me-1"></i>Mark Present';

      return `
        <tr class="${isPresent ? 'table-light' : ''}">
          <td class="text-muted small">${idx + 1}</td>
          <td class="fw-semibold text-dark">${escapeHtml(r.roll_number)}</td>
          <td>
            <div class="fw-bold">${escapeHtml(r.full_name)}</div>
          </td>
          <td>${faceBadge}</td>
          <td>${confidenceBadge}</td>
          <td>${statusBadge}</td>
          <td class="text-end">
            <button type="button" class="btn btn-sm ${toggleBtnClass} shadow-sm" onclick="toggleStudentAttendanceStatus(${r.student_id})">
              ${toggleBtnText}
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  // Mobile Touch Card Grid Rendering
  if (cardGrid) {
    cardGrid.innerHTML = records.map((r, idx) => {
      const isPresent = r.status === 'PRESENT';
      let confPill = '';
      if (r.is_manual) {
        confPill = `<span class="confidence-badge med"><i class="bi bi-pencil-fill"></i> Manual</span>`;
      } else if (isPresent && r.confidence > 0) {
        const pct = ((r.confidence <= 1 ? r.confidence * 100 : r.confidence)).toFixed(1);
        confPill = `<span class="confidence-badge high"><i class="bi bi-shield-check"></i> ${pct}%</span>`;
      } else {
        confPill = `<span class="confidence-badge low">No Match</span>`;
      }

      const initials = r.roll_number ? r.roll_number.slice(-3) : (r.full_name ? r.full_name.slice(0, 2).toUpperCase() : 'ST');

      return `
        <div class="student-roster-card ${isPresent ? 'status-present' : 'status-absent'}">
          <div class="d-flex justify-content-between align-items-start mb-2">
            <div class="d-flex align-items-center gap-2">
              <div class="p-2 rounded-circle fw-bold text-center small ${isPresent ? 'bg-success text-white' : 'bg-light text-secondary border'}" style="width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; font-size: 0.75rem;">
                ${escapeHtml(initials)}
              </div>
              <div>
                <div class="fw-bold text-dark lh-sm">${escapeHtml(r.full_name)}</div>
                <small class="text-muted">${escapeHtml(r.roll_number)}</small>
              </div>
            </div>
            ${confPill}
          </div>
          <div class="attendance-toggle-pill mt-2">
            <button type="button" class="toggle-opt-btn ${isPresent ? 'active-present' : ''}" onclick="setStudentAttendanceStatus(${r.student_id}, 'PRESENT')">
              <i class="bi bi-check-circle-fill"></i> Present
            </button>
            <button type="button" class="toggle-opt-btn ${!isPresent ? 'active-absent' : ''}" onclick="setStudentAttendanceStatus(${r.student_id}, 'ABSENT')">
              <i class="bi bi-x-circle-fill"></i> Absent
            </button>
          </div>
        </div>
      `;
    }).join('');
  }
}

function setStudentAttendanceStatus(studentId, newStatus) {
  const rec = subjectTeacherState.confirmedRecords.find(r => r.student_id === studentId);
  if (!rec) return;

  rec.status = newStatus;
  rec.is_manual = true;

  updatePreviewKPIs();
  renderStudentPreviewRoster();
}
window.setStudentAttendanceStatus = setStudentAttendanceStatus;

function toggleStudentAttendanceStatus(studentId) {
  const rec = subjectTeacherState.confirmedRecords.find(r => r.student_id === studentId);
  if (!rec) return;

  rec.status = (rec.status === 'PRESENT') ? 'ABSENT' : 'PRESENT';
  rec.is_manual = true;

  updatePreviewKPIs();
  renderStudentPreviewRoster();
}

function markAllPresent() {
  subjectTeacherState.confirmedRecords.forEach(r => {
    r.status = 'PRESENT';
    r.is_manual = true;
  });
  updatePreviewKPIs();
  renderStudentPreviewRoster();
  showToast('info', 'Batch Update', 'Marked all students as Present.');
}

function markAllAbsent() {
  subjectTeacherState.confirmedRecords.forEach(r => {
    r.status = 'ABSENT';
    r.is_manual = true;
  });
  updatePreviewKPIs();
  renderStudentPreviewRoster();
  showToast('info', 'Batch Update', 'Marked all students as Absent.');
}

function cancelAttendancePreview() {
  document.getElementById('st-step-preview-card')?.classList.add('d-none');
  document.getElementById('st-step-camera-card')?.classList.remove('d-none');

  const step2 = document.getElementById('st-wiz-step-2');
  const step3 = document.getElementById('st-wiz-step-3');
  if (step2) { step2.classList.add('active'); step2.classList.remove('completed'); }
  if (step3) { step3.classList.remove('active', 'completed'); }
  updateAttendanceStepper(4);
  showToast('info', 'Re-Analysis', 'Returned to photo capture step.');
}

async function confirmAttendanceAction() {
  if (!subjectTeacherState.confirmedRecords || subjectTeacherState.confirmedRecords.length === 0) {
    showToast('warning', 'No Records', 'No attendance records available to save.');
    return;
  }

  // Populate Modern Confirmation Dialog Modal before final commit
  const modalEl = document.getElementById('modal-confirm-attendance');
  if (modalEl && window.bootstrap && bootstrap.Modal) {
    const classSelect = document.getElementById('st-select-class');
    const subjectSelect = document.getElementById('st-select-subject');
    const className = classSelect ? (classSelect.options[classSelect.selectedIndex]?.text || 'Selected Class') : 'Class Cohort';
    const subjectName = subjectSelect ? (subjectSelect.options[subjectSelect.selectedIndex]?.text || 'Selected Subject') : 'Subject Course';

    const presentCount = subjectTeacherState.confirmedRecords.filter(r => r.status === 'PRESENT').length;
    const absentCount = subjectTeacherState.confirmedRecords.length - presentCount;
    const totalCount = subjectTeacherState.confirmedRecords.length;
    const presentPct = totalCount > 0 ? Math.round((presentCount / totalCount) * 100) : 0;
    const absentPct = totalCount > 0 ? Math.round((absentCount / totalCount) * 100) : 0;

    const classLabel = document.getElementById('modal-confirm-class');
    const subjLabel = document.getElementById('modal-confirm-subject');
    const periodLabel = document.getElementById('modal-confirm-period');
    const dateLabel = document.getElementById('modal-confirm-date');
    const presentNum = document.getElementById('modal-confirm-present');
    const absentNum = document.getElementById('modal-confirm-absent');
    const presentPctEl = document.getElementById('modal-confirm-present-pct');
    const absentPctEl = document.getElementById('modal-confirm-absent-pct');
    const timeLabel = document.getElementById('modal-confirm-timestamp');

    if (classLabel) classLabel.textContent = className;
    if (subjLabel) subjLabel.textContent = subjectName;
    if (periodLabel) periodLabel.textContent = `Period ${subjectTeacherState.selectedPeriod}`;
    if (dateLabel) dateLabel.textContent = subjectTeacherState.selectedDate;
    if (presentNum) presentNum.textContent = presentCount;
    if (absentNum) absentNum.textContent = absentCount;
    if (presentPctEl) presentPctEl.textContent = `${presentPct}% of enrolled`;
    if (absentPctEl) absentPctEl.textContent = `${absentPct}% of enrolled`;
    if (timeLabel) timeLabel.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    let modalInstance = bootstrap.Modal.getInstance(modalEl);
    if (!modalInstance) {
      modalInstance = new bootstrap.Modal(modalEl);
    }
    modalInstance.show();

    // Wire Final Confirm button in Modal
    const btnFinalConfirm = document.getElementById('btn-modal-final-confirm');
    if (btnFinalConfirm) {
      btnFinalConfirm.onclick = async () => {
        btnFinalConfirm.disabled = true;
        btnFinalConfirm.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving...';
        try {
          await executeSaveAttendance();
          modalInstance.hide();
        } finally {
          btnFinalConfirm.disabled = false;
          btnFinalConfirm.innerHTML = '<i class="bi bi-cloud-check-fill me-1"></i>Confirm & Save';
        }
      };
    }
  } else {
    // Direct save fallback if modal element not rendered
    await executeSaveAttendance();
  }
}

async function executeSaveAttendance() {
  const btnConfirm = document.getElementById('btn-st-confirm-attendance');
  const btnConfirmTop = document.getElementById('btn-st-confirm-attendance-top');
  const originalText = btnConfirm ? btnConfirm.innerHTML : '';

  if (btnConfirm) {
    btnConfirm.disabled = true;
    btnConfirm.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Saving Attendance...';
  }
  if (btnConfirmTop) btnConfirmTop.disabled = true;

  try {
    const payload = subjectTeacherState.confirmedRecords.map(r => ({
      student_id: r.student_id,
      class_id: r.class_id,
      subject_id: r.subject_id,
      teacher_id: Api.getUser()?.id || null,
      date: r.date,
      period: r.period,
      status: r.status,
      confidence: r.confidence,
      attendance_image_id: r.attendance_image_id,
      bounding_box: r.bounding_box ? JSON.stringify(r.bounding_box) : null,
      is_manual: r.is_manual,
    }));

    const result = await Api.confirmAttendance(payload);

    // Transition to Step 4 Success Card
    document.getElementById('st-step-preview-card')?.classList.add('d-none');
    const successCard = document.getElementById('st-step-success-card');
    if (successCard) successCard.classList.remove('d-none');

    updateAttendanceStepper(7);

    const step3 = document.getElementById('st-wiz-step-3');
    if (step3) { step3.classList.remove('active'); step3.classList.add('completed'); }

    const summaryText = document.getElementById('st-success-summary-text');
    const presentCount = subjectTeacherState.confirmedRecords.filter(r => r.status === 'PRESENT').length;
    if (summaryText) {
      summaryText.textContent = `Successfully verified and recorded attendance for ${result.length || payload.length} students (${presentCount} present) in Period ${subjectTeacherState.selectedPeriod} on ${subjectTeacherState.selectedDate}.`;
    }

    showToast('success', 'Attendance Recorded', `Verified records stored for Period ${subjectTeacherState.selectedPeriod}.`);
  } catch (err) {
    showToast('error', 'Save Failed', err.message || 'Failed to save attendance records.');
  } finally {
    if (btnConfirm) {
      btnConfirm.disabled = false;
      btnConfirm.innerHTML = originalText;
    }
    if (btnConfirmTop) btnConfirmTop.disabled = false;
  }
}

function resetAttendanceFlow() {
  subjectTeacherState.capturedImageBlob = null;
  if (subjectTeacherState.capturedImageUrl) {
    URL.revokeObjectURL(subjectTeacherState.capturedImageUrl);
    subjectTeacherState.capturedImageUrl = null;
  }
  subjectTeacherState.previewData = null;
  subjectTeacherState.confirmedRecords = [];

  const fileInput = document.getElementById('st-file-photo');
  if (fileInput) fileInput.value = '';

  document.getElementById('st-captured-preview-container')?.classList.add('d-none');
  document.getElementById('st-step-success-card')?.classList.add('d-none');
  document.getElementById('st-step-preview-card')?.classList.add('d-none');
  document.getElementById('st-step-camera-card')?.classList.add('d-none');
  document.getElementById('st-step-session-card')?.classList.remove('d-none');

  updateAttendanceStepper(1);

  const step1 = document.getElementById('st-wiz-step-1');
  const step2 = document.getElementById('st-wiz-step-2');
  const step3 = document.getElementById('st-wiz-step-3');
  if (step1) { step1.classList.add('active'); step1.classList.remove('completed'); }
  if (step2) { step2.classList.remove('active', 'completed'); }
  if (step3) { step3.classList.remove('active', 'completed'); }
}

function initSubjectTeacherPortal() {
  // Refresh button
  document.getElementById('btn-st-refresh')?.addEventListener('click', loadSubjectTeacherData);

  // Class dropdown change listener
  document.getElementById('st-select-class')?.addEventListener('change', (e) => {
    subjectTeacherState.selectedClassId = parseInt(e.target.value);
    populateSubjectDropdown();
  });

  // Subject dropdown change listener
  document.getElementById('st-select-subject')?.addEventListener('change', (e) => {
    subjectTeacherState.selectedSubjectId = parseInt(e.target.value);
  });

  // Date input change listener
  document.getElementById('st-session-date')?.addEventListener('change', (e) => {
    subjectTeacherState.selectedDate = e.target.value;
  });

  // Period chip selection
  document.querySelectorAll('.period-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.period-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      const p = parseInt(chip.getAttribute('data-period'));
      subjectTeacherState.selectedPeriod = p;

      const badge = document.getElementById('st-period-badge');
      if (badge) badge.textContent = `Period ${p}`;
      const hiddenInput = document.getElementById('st-selected-period');
      if (hiddenInput) hiddenInput.value = p;
    });
  });

  // Step 1 -> Step 2
  document.getElementById('btn-st-goto-camera')?.addEventListener('click', goToCameraStep);

  // Step 2 -> Step 1
  document.getElementById('btn-st-back-to-session')?.addEventListener('click', backToSessionStep);

  // Camera buttons
  document.getElementById('btn-st-start-camera')?.addEventListener('click', startLiveCamera);
  document.getElementById('btn-st-stop-camera')?.addEventListener('click', stopLiveCamera);
  document.getElementById('btn-st-flip-camera')?.addEventListener('click', flipCamera);
  document.getElementById('btn-st-shutter')?.addEventListener('click', captureCameraFrame);

  // File upload input
  document.getElementById('st-file-photo')?.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileInputPhoto(e.target.files[0]);
    }
  });

  // Retake photo
  document.getElementById('btn-st-retake-photo')?.addEventListener('click', retakePhoto);

  // Analyze photo
  document.getElementById('btn-st-analyze-photo')?.addEventListener('click', analyzeClassroomPhotoAction);

  // Search input in preview
  document.getElementById('st-preview-search')?.addEventListener('input', renderStudentPreviewRoster);

  // Batch buttons
  document.getElementById('btn-st-mark-all-present')?.addEventListener('click', markAllPresent);
  document.getElementById('btn-st-mark-all-absent')?.addEventListener('click', markAllAbsent);

  // Result Image Overlay Toggle (Annotated vs Original)
  document.getElementById('btn-show-annotated-img')?.addEventListener('click', () => {
    const btnAnn = document.getElementById('btn-show-annotated-img');
    const btnOrig = document.getElementById('btn-show-original-img');
    btnAnn?.classList.add('active', 'btn-primary');
    btnAnn?.classList.remove('btn-outline-secondary');
    btnOrig?.classList.remove('active', 'btn-primary');
    btnOrig?.classList.add('btn-outline-secondary');
    const resultImg = document.getElementById('st-result-annotated-photo');
    if (resultImg && subjectTeacherState.previewData?.annotated_image_url) {
      resultImg.src = subjectTeacherState.previewData.annotated_image_url;
    }
  });

  document.getElementById('btn-show-original-img')?.addEventListener('click', () => {
    const btnAnn = document.getElementById('btn-show-annotated-img');
    const btnOrig = document.getElementById('btn-show-original-img');
    btnOrig?.classList.add('active', 'btn-primary');
    btnOrig?.classList.remove('btn-outline-secondary');
    btnAnn?.classList.remove('active', 'btn-primary');
    btnAnn?.classList.add('btn-outline-secondary');
    const resultImg = document.getElementById('st-result-annotated-photo');
    if (resultImg && subjectTeacherState.previewData?.image_url) {
      resultImg.src = subjectTeacherState.previewData.image_url;
    }
  });

  // Cancel preview
  document.getElementById('btn-st-cancel-preview')?.addEventListener('click', cancelAttendancePreview);

  // Confirm attendance
  document.getElementById('btn-st-confirm-attendance')?.addEventListener('click', confirmAttendanceAction);
  document.getElementById('btn-st-confirm-attendance-top')?.addEventListener('click', confirmAttendanceAction);

  // Success actions
  document.getElementById('btn-st-take-another')?.addEventListener('click', resetAttendanceFlow);
  document.getElementById('btn-st-goto-reports')?.addEventListener('click', () => {
    resetAttendanceFlow();
    document.querySelector('.sidebar-nav .nav-link[data-target="reports-section"]')?.click();
  });
}

window.quickStartSubjectAttendance = quickStartSubjectAttendance;
window.toggleStudentAttendanceStatus = toggleStudentAttendanceStatus;
window.loadSubjectTeacherData = loadSubjectTeacherData;


/* ========================================================
   ATTENDANCE DASHBOARDS & CHARTS ENGINE
   (Class Teacher, Subject Teacher, Admin)
   ======================================================== */

window.activeDashboardCharts = window.activeDashboardCharts || {};

/**
 * Robust Chart.js instance manager that destroys previous charts
 * on the target canvas before creating a new one.
 */
function createOrUpdateChart(canvasId, config) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;

  if (window.activeDashboardCharts[canvasId]) {
    try {
      window.activeDashboardCharts[canvasId].destroy();
    } catch (e) {
      console.warn('Chart destroy error on', canvasId, e);
    }
    delete window.activeDashboardCharts[canvasId];
  }

  if (typeof Chart === 'undefined') {
    console.warn('Chart.js library not loaded yet for canvas:', canvasId);
    return null;
  }

  try {
    const ctx = canvas.getContext('2d');
    const chartInstance = new Chart(ctx, config);
    window.activeDashboardCharts[canvasId] = chartInstance;
    return chartInstance;
  } catch (err) {
    console.error('Failed to instantiate Chart.js on', canvasId, err);
    return null;
  }
}

// --------------------------------------------------------
// 1. CLASS TEACHER ATTENDANCE DASHBOARD
// --------------------------------------------------------

let ctDashboardCachedData = null;

async function loadClassTeacherDashboard(classId, customFilters = {}) {
  const selectedClassInput = document.getElementById('ct-dash-filter-class')?.value;
  const targetClassId = customFilters.class_id || (selectedClassInput ? parseInt(selectedClassInput, 10) : (classId || currentClassTeacherClass?.id));
  if (!targetClassId) return;

  const params = { class_id: targetClassId, ...customFilters };

  // Pull filter values from UI if not explicitly passed
  if (!customFilters.subject_id) {
    const subVal = document.getElementById('ct-dash-filter-subject')?.value;
    if (subVal) params.subject_id = parseInt(subVal, 10);
  }
  if (!customFilters.teacher_id) {
    const teacherVal = document.getElementById('ct-dash-filter-teacher')?.value;
    if (teacherVal) params.teacher_id = parseInt(teacherVal, 10);
  }
  if (!customFilters.student_id && !customFilters.student) {
    const stVal = document.getElementById('ct-dash-filter-student')?.value;
    if (stVal) {
      if (stVal.trim().match(/^\d+$/)) {
        params.student_id = parseInt(stVal.trim(), 10);
      } else {
        params.student = stVal.trim();
      }
    }
  }
  if (!customFilters.start_date) {
    const startVal = document.getElementById('ct-dash-filter-start')?.value;
    if (startVal) params.start_date = startVal;
  }
  if (!customFilters.end_date) {
    const endVal = document.getElementById('ct-dash-filter-end')?.value;
    if (endVal) params.end_date = endVal;
  }

  try {
    const data = await Api.getClassTeacherAttendanceDashboard(params);
    ctDashboardCachedData = data;

    // Populate filter dropdowns if options are empty
    populateClassTeacherDashboardFilters(data);

    // 1. Today's Attendance
    renderClassTeacherTodayCard(data.today);

    // 2. Class Attendance Percentage (Overall)
    renderClassTeacherOverallCard(data.overall);

    // 3. Student-wise Attendance Table
    renderClassTeacherStudentTable(data.student_wise || []);

    // 4. Subject-wise Attendance (Chart + Table)
    renderClassTeacherSubjectWise(data.subject_wise || []);

    // 5. Date-wise Attendance (Chart + Table)
    renderClassTeacherDateWise(data.date_wise || []);

  } catch (err) {
    console.error('Failed to load class teacher attendance dashboard:', err);
  }
}

function populateClassTeacherDashboardFilters(data) {
  // Class dropdown
  const classSelect = document.getElementById('ct-dash-filter-class');
  if (classSelect && data.available_filters?.classes) {
    const currentVal = classSelect.value;
    if (classSelect.options.length <= 1) {
      classSelect.innerHTML = '<option value="">Current Assigned Class</option>';
      data.available_filters.classes.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.id;
        opt.textContent = c.name;
        classSelect.appendChild(opt);
      });
      if (currentVal) classSelect.value = currentVal;
      else if (data.class_info?.id) classSelect.value = data.class_info.id;
    }
  }

  // Subject dropdown
  const subSelect = document.getElementById('ct-dash-filter-subject');
  if (subSelect && subSelect.options.length <= 1) {
    const currentVal = subSelect.value;
    subSelect.innerHTML = '<option value="">All Subjects</option>';
    const subs = data.available_filters?.subjects || data.subject_wise || [];
    subs.forEach(sub => {
      const opt = document.createElement('option');
      opt.value = sub.id || sub.subject_id;
      const code = sub.code || sub.subject_code || '';
      const name = sub.name || sub.subject_name || '';
      opt.textContent = code ? `${code} - ${name}` : name;
      subSelect.appendChild(opt);
    });
    if (currentVal) subSelect.value = currentVal;
  }

  // Teacher dropdown
  const teacherSelect = document.getElementById('ct-dash-filter-teacher');
  if (teacherSelect && teacherSelect.options.length <= 1 && data.available_filters?.teachers) {
    const currentVal = teacherSelect.value;
    teacherSelect.innerHTML = '<option value="">All Faculty</option>';
    data.available_filters.teachers.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id;
      opt.textContent = t.name;
      teacherSelect.appendChild(opt);
    });
    if (currentVal) teacherSelect.value = currentVal;
  }

  // Student dropdown
  const stSelect = document.getElementById('ct-dash-filter-student');
  if (stSelect && stSelect.options.length <= 1) {
    const currentVal = stSelect.value;
    stSelect.innerHTML = '<option value="">All Students in Class</option>';
    const studentsList = data.available_filters?.students || data.student_wise || [];
    studentsList.forEach(st => {
      const opt = document.createElement('option');
      opt.value = st.id || st.student_id;
      opt.textContent = `${st.roll_number} - ${st.full_name}`;
      stSelect.appendChild(opt);
    });
    if (currentVal) stSelect.value = currentVal;
  }
}

function renderClassTeacherTodayCard(today) {
  if (!today) return;

  const rateBadge = document.getElementById('ct-dash-today-rate-badge');
  const dateEl = document.getElementById('ct-dash-today-date');
  const presentEl = document.getElementById('ct-dash-today-present');
  const absentEl = document.getElementById('ct-dash-today-absent');
  const sessionsEl = document.getElementById('ct-dash-today-sessions');

  const present = today.present !== undefined ? today.present : (today.present_count || 0);
  const absent = today.absent !== undefined ? today.absent : (today.absent_count || 0);
  const sessions = today.sessions_count !== undefined ? today.sessions_count : (today.total_sessions || 0);
  const rate = today.attendance_rate !== null && today.attendance_rate !== undefined ? today.attendance_rate : 0;

  if (rateBadge) {
    rateBadge.textContent = `${rate.toFixed(1)}%`;
    rateBadge.className = `badge px-3 py-2 fs-6 ${rate >= 75 ? 'bg-success' : rate > 0 ? 'bg-warning text-dark' : 'bg-secondary'}`;
  }
  if (dateEl) dateEl.textContent = today.date || 'Today';
  if (presentEl) presentEl.textContent = present;
  if (absentEl) absentEl.textContent = absent;
  if (sessionsEl) sessionsEl.textContent = sessions;

  // Donut Chart: Today's Present vs Absent
  const hasData = (present + absent) > 0;
  createOrUpdateChart('ct-chart-today', {
    type: 'doughnut',
    data: {
      labels: hasData ? ['Present', 'Absent'] : ['No Sessions Today'],
      datasets: [{
        data: hasData ? [present, absent] : [0, 1],
        backgroundColor: hasData ? ['#10b981', '#ef4444'] : ['#e2e8f0', '#cbd5e1'],
        borderWidth: 2,
        borderColor: '#ffffff',
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { boxWidth: 12, padding: 8, font: { family: 'Inter', size: 11 } }
        },
        tooltip: {
          enabled: hasData
        }
      }
    }
  });

  // Periods Breakdown Chips
  const periodsContainer = document.getElementById('ct-dash-today-periods');
  if (periodsContainer) {
    if (!today.periods || today.periods.length === 0) {
      periodsContainer.innerHTML = '<span class="text-muted small">No periods conducted yet today.</span>';
    } else {
      periodsContainer.innerHTML = today.periods.map(p => {
        const pPres = p.present !== undefined ? p.present : (p.present_count || 0);
        const pAbs = p.absent !== undefined ? p.absent : (p.absent_count || 0);
        const pTotal = pPres + pAbs;
        return `
          <span class="badge ${p.rate >= 75 ? 'bg-success-subtle text-success border border-success-subtle' : 'bg-warning-subtle text-warning border border-warning-subtle'} py-2 px-3 small">
            <strong>Period ${p.period}</strong>: ${pPres} Present / ${pTotal} (${p.rate.toFixed(1)}%) - <span class="fw-normal">${escapeHtml(p.subject_name || '')}</span>
          </span>
        `;
      }).join('');
    }
  }
}

function renderClassTeacherOverallCard(overall) {
  if (!overall) return;

  const rate = overall.attendance_rate !== undefined ? overall.attendance_rate : (overall.class_attendance_percentage || 0);
  const totalStudents = overall.total_students || 0;
  const totalSessions = overall.total_sessions || 0;
  const totalRecords = overall.total_records || (overall.records_marked || 0);

  const rateEl = document.getElementById('ct-dash-overall-rate');
  const studentsEl = document.getElementById('ct-dash-overall-students');
  const sessionsEl = document.getElementById('ct-dash-overall-sessions');
  const recordsEl = document.getElementById('ct-dash-overall-records');
  const statusBadge = document.getElementById('ct-dash-overall-status-badge');
  const thresholdInd = document.getElementById('ct-dash-threshold-indicator');

  if (rateEl) rateEl.textContent = `${rate.toFixed(1)}%`;
  if (studentsEl) studentsEl.textContent = totalStudents;
  if (sessionsEl) sessionsEl.textContent = totalSessions;
  if (recordsEl) recordsEl.textContent = totalRecords;

  if (statusBadge) {
    if (rate >= 85) {
      statusBadge.textContent = 'Excellent';
      statusBadge.className = 'badge bg-success px-3 py-2 fs-6';
    } else if (rate >= 75) {
      statusBadge.textContent = 'Good';
      statusBadge.className = 'badge bg-primary px-3 py-2 fs-6';
    } else if (totalSessions > 0) {
      statusBadge.textContent = 'Attention';
      statusBadge.className = 'badge bg-danger px-3 py-2 fs-6';
    } else {
      statusBadge.textContent = 'New Cohort';
      statusBadge.className = 'badge bg-secondary px-3 py-2 fs-6';
    }
  }

  if (thresholdInd) {
    if (rate >= 75) {
      thresholdInd.className = 'badge bg-success-subtle text-success border border-success-subtle';
      thresholdInd.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i>Target Met (&ge; 75%)';
    } else {
      thresholdInd.className = 'badge bg-danger-subtle text-danger border border-danger-subtle';
      thresholdInd.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-1"></i>Below Target (&lt; 75%)';
    }
  }

  // Donut Gauge: Overall Attendance Rate
  const remaining = Math.max(0, 100 - rate);
  createOrUpdateChart('ct-chart-overall', {
    type: 'doughnut',
    data: {
      labels: ['Attended', 'Missed'],
      datasets: [{
        data: totalSessions > 0 ? [rate, remaining] : [0, 100],
        backgroundColor: totalSessions > 0 ? ['#10b981', '#e2e8f0'] : ['#e2e8f0', '#cbd5e1'],
        borderWidth: 0,
        hoverOffset: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '76%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { boxWidth: 12, padding: 8, font: { family: 'Inter', size: 11 } }
        }
      }
    }
  });
}

function renderClassTeacherStudentTable(students, filterText = '', filterStatus = 'all') {
  const tbody = document.getElementById('ct-dash-student-table-body');
  if (!tbody) return;

  let filtered = students;
  if (filterText && filterText.trim()) {
    const q = filterText.trim().toLowerCase();
    filtered = filtered.filter(s =>
      (s.full_name && s.full_name.toLowerCase().includes(q)) ||
      (s.roll_number && s.roll_number.toLowerCase().includes(q)) ||
      (s.register_number && s.register_number.toLowerCase().includes(q))
    );
  }

  if (filterStatus === 'low') {
    filtered = filtered.filter(s => s.is_low_attendance || (s.total_sessions > 0 && s.attendance_rate < 75));
  } else if (filterStatus === 'good') {
    filtered = filtered.filter(s => !s.is_low_attendance && (s.total_sessions === 0 || s.attendance_rate >= 75));
  }

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-muted">No students match the selected filter.</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(st => {
    const rate = st.attendance_rate || 0;
    const isLow = st.is_low_attendance || (st.total_sessions > 0 && rate < 75);
    return `
      <tr class="${isLow ? 'table-danger-subtle' : ''}">
        <td><span class="badge bg-light text-dark border fw-bold">${escapeHtml(st.roll_number || '')}</span></td>
        <td>
          <div class="fw-semibold text-dark">${escapeHtml(st.full_name || '')}</div>
          <small class="text-muted">${escapeHtml(st.register_number || '')}</small>
        </td>
        <td>
          ${st.face_enrolled 
            ? '<span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-camera-fill me-1"></i>Enrolled</span>' 
            : '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">Pending</span>'}
        </td>
        <td>${st.total_sessions || 0}</td>
        <td><strong class="text-success">${st.attended_sessions || 0}</strong></td>
        <td><strong class="${(st.absent_sessions || 0) > 0 ? 'text-danger' : 'text-muted'}">${st.absent_sessions || 0}</strong></td>
        <td>
          <div class="d-flex align-items-center gap-2">
            <div class="progress flex-grow-1" style="height: 6px; background-color: #e2e8f0;">
              <div class="progress-bar ${isLow ? 'bg-danger' : 'bg-success'}" style="width: ${rate}%;"></div>
            </div>
            <span class="small fw-bold ${isLow ? 'text-danger' : 'text-success'}" style="min-width: 44px;">
              ${st.total_sessions > 0 ? rate.toFixed(1) + '%' : 'N/A'}
            </span>
          </div>
        </td>
        <td>
          ${isLow
            ? '<span class="badge badge-low-att"><i class="bi bi-exclamation-triangle-fill me-1"></i>Shortage</span>'
            : '<span class="badge badge-good-att"><i class="bi bi-check-circle-fill me-1"></i>Eligible</span>'}
        </td>
      </tr>
    `;
  }).join('');
}

function renderClassTeacherSubjectWise(subjectWise) {
  const tbody = document.getElementById('ct-dash-subject-table-body');
  if (tbody) {
    if (subjectWise.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">No subject assignments recorded.</td></tr>';
    } else {
      tbody.innerHTML = subjectWise.map(sub => {
        const rate = sub.attendance_rate !== null && sub.attendance_rate !== undefined ? sub.attendance_rate : 0;
        const sessions = sub.total_sessions !== undefined ? sub.total_sessions : (sub.sessions_count || 0);
        return `
          <tr>
            <td>
              <div class="fw-semibold text-dark">${escapeHtml(sub.subject_name || '')}</div>
              <small class="text-muted">${escapeHtml(sub.subject_code || '')}</small>
            </td>
            <td><small class="text-secondary">${escapeHtml(sub.teacher_name || 'Faculty')}</small></td>
            <td>${sessions} sessions</td>
            <td>
              <span class="badge ${rate >= 75 ? 'bg-success' : rate > 0 ? 'bg-warning text-dark' : 'bg-secondary'}">
                ${sub.attendance_rate !== null ? rate.toFixed(1) + '%' : 'No Data'}
              </span>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  // Subject Bar Chart
  const labels = subjectWise.map(s => s.subject_code || s.subject_name);
  const data = subjectWise.map(s => s.attendance_rate !== null && s.attendance_rate !== undefined ? s.attendance_rate : 0);
  const bgColors = subjectWise.map(s => (s.attendance_rate >= 75 ? '#3b82f6' : '#ef4444'));

  createOrUpdateChart('ct-chart-subjects', {
    type: 'bar',
    data: {
      labels: labels.length > 0 ? labels : ['No Subjects'],
      datasets: [{
        label: 'Attendance Rate (%)',
        data: data.length > 0 ? data : [0],
        backgroundColor: bgColors.length > 0 ? bgColors : ['#cbd5e1'],
        borderRadius: 4,
        maxBarThickness: 36
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          max: 100,
          ticks: { callback: v => v + '%' }
        },
        x: { grid: { display: false } }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `Attendance Rate: ${ctx.parsed.y.toFixed(1)}%`
          }
        }
      }
    }
  });
}

function renderClassTeacherDateWise(dateWise) {
  const tbody = document.getElementById('ct-dash-date-table-body');
  if (tbody) {
    if (dateWise.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center py-3 text-muted">No attendance sessions recorded yet.</td></tr>';
    } else {
      tbody.innerHTML = dateWise.map(d => {
        const rate = d.attendance_rate !== null && d.attendance_rate !== undefined ? d.attendance_rate : 0;
        const present = d.present !== undefined ? d.present : (d.present_count || 0);
        const absent = d.absent !== undefined ? d.absent : (d.absent_count || 0);
        return `
          <tr>
            <td><strong>${escapeHtml(d.date || '')}</strong></td>
            <td>${d.sessions_count || 0}</td>
            <td><span class="text-success fw-semibold">${present}</span></td>
            <td><span class="text-danger fw-semibold">${absent}</span></td>
            <td>
              <span class="badge ${rate >= 75 ? 'bg-success' : 'bg-warning text-dark'}">
                ${rate.toFixed(1)}%
              </span>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  // Date Line Chart
  const labels = dateWise.map(d => d.date);
  const data = dateWise.map(d => d.attendance_rate || 0);

  createOrUpdateChart('ct-chart-dates', {
    type: 'line',
    data: {
      labels: labels.length > 0 ? labels : ['No Timeline Data'],
      datasets: [{
        label: 'Daily Attendance (%)',
        data: data.length > 0 ? data : [0],
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.12)',
        borderWidth: 2.5,
        tension: 0.35,
        fill: true,
        pointRadius: 4,
        pointBackgroundColor: '#10b981'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          max: 100,
          ticks: { callback: v => v + '%' }
        },
        x: { grid: { display: false } }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `Daily Rate: ${ctx.parsed.y.toFixed(1)}%`
          }
        }
      }
    }
  });
}

// --------------------------------------------------------
// 2. SUBJECT TEACHER ATTENDANCE DASHBOARD
// --------------------------------------------------------

let stDashboardCachedData = null;

async function loadSubjectTeacherDashboard(customFilters = {}) {
  const params = { ...customFilters };

  if (!customFilters.class_id) {
    const classVal = document.getElementById('st-dash-filter-class')?.value;
    if (classVal) params.class_id = parseInt(classVal, 10);
  }
  if (!customFilters.subject_id) {
    const subVal = document.getElementById('st-dash-filter-subject')?.value;
    if (subVal) params.subject_id = parseInt(subVal, 10);
  }
  if (!customFilters.student && !customFilters.student_id) {
    const stVal = document.getElementById('st-dash-filter-student')?.value;
    if (stVal && stVal.trim()) {
      if (stVal.trim().match(/^\d+$/)) {
        params.student_id = parseInt(stVal.trim(), 10);
      } else {
        params.student = stVal.trim();
      }
    }
  }
  if (!customFilters.teacher_id) {
    const teacherVal = document.getElementById('st-dash-filter-teacher')?.value;
    if (teacherVal) params.teacher_id = parseInt(teacherVal, 10);
  }
  if (!customFilters.start_date) {
    const startVal = document.getElementById('st-dash-filter-start')?.value;
    if (startVal) params.start_date = startVal;
  }
  if (!customFilters.end_date) {
    const endVal = document.getElementById('st-dash-filter-end')?.value;
    if (endVal) params.end_date = endVal;
  }

  try {
    const data = await Api.getSubjectTeacherAttendanceDashboard(params);
    stDashboardCachedData = data;

    // Populate dropdowns from classes/subjects if available
    populateSubjectTeacherDashboardFilters(data);

    // Summary KPIs & Donut
    renderSubjectTeacherSummary(data.summary);

    // Class-wise records (Chart + Table)
    renderSubjectTeacherClassWise(data.class_wise || []);

    // Subject-wise records (Chart + Table)
    renderSubjectTeacherSubjectWise(data.subject_wise || []);

    // Date-wise timeline (Chart) & Recent Sessions ledger (Table)
    renderSubjectTeacherDateWise(data.date_wise || [], data.recent_sessions || []);

  } catch (err) {
    console.error('Failed to load subject teacher attendance dashboard:', err);
  }
}

function populateSubjectTeacherDashboardFilters(data) {
  const classSelect = document.getElementById('st-dash-filter-class');
  if (classSelect && classSelect.options.length <= 1) {
    const currentVal = classSelect.value;
    classSelect.innerHTML = '<option value="">All Taught Classes</option>';
    const classes = data.available_filters?.classes || (subjectTeacherState.assignedClasses.length > 0 ? subjectTeacherState.assignedClasses : (data.class_wise || []));
    classes.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.id || c.class_id;
      opt.textContent = c.name || c.class_name;
      classSelect.appendChild(opt);
    });
    if (currentVal) classSelect.value = currentVal;
  }

  const subSelect = document.getElementById('st-dash-filter-subject');
  if (subSelect && subSelect.options.length <= 1) {
    const currentVal = subSelect.value;
    subSelect.innerHTML = '<option value="">All Taught Subjects</option>';
    const subjects = data.available_filters?.subjects || (subjectTeacherState.assignedSubjects.length > 0 ? subjectTeacherState.assignedSubjects : (data.subject_wise || []));
    subjects.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id || s.subject_id;
      const code = s.code || s.subject_code || '';
      const name = s.name || s.subject_name || '';
      opt.textContent = code ? `${code} - ${name}` : name;
      subSelect.appendChild(opt);
    });
    if (currentVal) subSelect.value = currentVal;
  }
}

function renderSubjectTeacherSummary(summary) {
  if (!summary) return;

  const rate = summary.attendance_rate !== null && summary.attendance_rate !== undefined ? summary.attendance_rate : 0;
  const sessions = summary.total_sessions_taken !== undefined ? summary.total_sessions_taken : (summary.sessions_count || 0);
  const records = summary.total_records_marked !== undefined ? summary.total_records_marked : (summary.total_records || 0);
  const present = summary.present !== undefined ? summary.present : (summary.present_count || 0);
  const absent = summary.absent !== undefined ? summary.absent : (summary.absent_count || 0);

  const rateBadge = document.getElementById('st-dash-rate-badge');
  const sessionsEl = document.getElementById('st-dash-total-sessions');
  const recordsEl = document.getElementById('st-dash-total-records');
  const presentEl = document.getElementById('st-dash-present-count');

  if (rateBadge) {
    rateBadge.textContent = `${rate.toFixed(1)}%`;
    rateBadge.className = `badge px-3 py-2 fs-6 ${rate >= 75 ? 'bg-success' : rate > 0 ? 'bg-warning text-dark' : 'bg-secondary'}`;
  }
  if (sessionsEl) sessionsEl.textContent = sessions;
  if (recordsEl) recordsEl.textContent = records;
  if (presentEl) presentEl.textContent = present;

  // Donut: Attendance Taken by Them
  const hasData = (present + absent) > 0;
  createOrUpdateChart('st-chart-status-summary', {
    type: 'doughnut',
    data: {
      labels: hasData ? ['Present', 'Absent'] : ['No Records'],
      datasets: [{
        data: hasData ? [present, absent] : [0, 1],
        backgroundColor: hasData ? ['#10b981', '#ef4444'] : ['#e2e8f0', '#cbd5e1'],
        borderWidth: 2,
        borderColor: '#ffffff',
        hoverOffset: 3
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '70%',
      plugins: {
        legend: { display: false }
      }
    }
  });
}

function renderSubjectTeacherClassWise(classWise) {
  const tbody = document.getElementById('st-dash-class-table-body');
  if (tbody) {
    if (classWise.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">No class attendance recorded.</td></tr>';
    } else {
      tbody.innerHTML = classWise.map(c => {
        const rate = c.attendance_rate !== null && c.attendance_rate !== undefined ? c.attendance_rate : 0;
        const present = c.present !== undefined ? c.present : (c.present_count || 0);
        const sessions = c.sessions_taken !== undefined ? c.sessions_taken : (c.sessions_count || 0);
        return `
          <tr>
            <td>
              <strong>${escapeHtml(c.class_name || '')}</strong><br>
              <small class="text-muted">${escapeHtml(c.department || '')} - Yr ${c.year || ''} Sec ${escapeHtml(c.section || '')}</small>
            </td>
            <td>${sessions}</td>
            <td><strong class="text-success">${present}</strong></td>
            <td>
              <span class="badge ${rate >= 75 ? 'bg-success' : rate > 0 ? 'bg-warning text-dark' : 'bg-secondary'}">
                ${rate.toFixed(1)}%
              </span>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  // Class Bar Chart
  const labels = classWise.map(c => c.class_name);
  const data = classWise.map(c => c.attendance_rate !== null && c.attendance_rate !== undefined ? c.attendance_rate : 0);

  createOrUpdateChart('st-chart-class-wise', {
    type: 'bar',
    data: {
      labels: labels.length > 0 ? labels : ['No Classes'],
      datasets: [{
        label: 'Attendance Rate (%)',
        data: data.length > 0 ? data : [0],
        backgroundColor: '#3b82f6',
        borderRadius: 4,
        maxBarThickness: 32
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } },
        x: { grid: { display: false } }
      },
      plugins: { legend: { display: false } }
    }
  });
}

function renderSubjectTeacherSubjectWise(subjectWise) {
  const tbody = document.getElementById('st-dash-subject-table-body');
  if (tbody) {
    if (subjectWise.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">No subject records available.</td></tr>';
    } else {
      tbody.innerHTML = subjectWise.map(s => {
        const rate = s.attendance_rate !== null && s.attendance_rate !== undefined ? s.attendance_rate : 0;
        const sessions = s.sessions_taken !== undefined ? s.sessions_taken : (s.sessions_count || 0);
        return `
          <tr>
            <td><strong>${escapeHtml(s.subject_name || '')}</strong></td>
            <td><span class="badge bg-light text-dark border">${escapeHtml(s.subject_code || '')}</span></td>
            <td>${sessions} sessions</td>
            <td>
              <span class="badge ${rate >= 75 ? 'bg-success' : rate > 0 ? 'bg-warning text-dark' : 'bg-secondary'}">
                ${rate.toFixed(1)}%
              </span>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  // Subject Bar Chart
  const labels = subjectWise.map(s => s.subject_code || s.subject_name);
  const data = subjectWise.map(s => s.attendance_rate !== null && s.attendance_rate !== undefined ? s.attendance_rate : 0);

  createOrUpdateChart('st-chart-subject-wise', {
    type: 'bar',
    data: {
      labels: labels.length > 0 ? labels : ['No Subjects'],
      datasets: [{
        label: 'Attendance Rate (%)',
        data: data.length > 0 ? data : [0],
        backgroundColor: '#06b6d4',
        borderRadius: 4,
        maxBarThickness: 32
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } },
        x: { grid: { display: false } }
      },
      plugins: { legend: { display: false } }
    }
  });
}

function renderSubjectTeacherDateWise(dateWise, recentSessions) {
  // Line chart: Date-wise timeline
  const labels = dateWise.map(d => d.date);
  const data = dateWise.map(d => d.attendance_rate || 0);

  createOrUpdateChart('st-chart-date-wise', {
    type: 'line',
    data: {
      labels: labels.length > 0 ? labels : ['No Timeline Data'],
      datasets: [{
        label: 'Daily Attendance (%)',
        data: data.length > 0 ? data : [0],
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245, 158, 11, 0.12)',
        borderWidth: 2.5,
        tension: 0.35,
        fill: true,
        pointRadius: 4,
        pointBackgroundColor: '#f59e0b'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } },
        x: { grid: { display: false } }
      },
      plugins: { legend: { display: false } }
    }
  });

  // Recent Sessions Ledger Table (support both container IDs)
  const tbody = document.getElementById('st-dash-recent-sessions-body') || document.getElementById('st-dash-recent-table-body');
  if (tbody) {
    if (recentSessions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center py-3 text-muted">No attendance sessions recorded yet.</td></tr>';
    } else {
      tbody.innerHTML = recentSessions.map(sess => {
        const rate = sess.attendance_rate !== null && sess.attendance_rate !== undefined ? sess.attendance_rate : 0;
        const present = sess.present !== undefined ? sess.present : (sess.present_count || 0);
        const total = sess.total_marked !== undefined ? sess.total_marked : (sess.total_students || 0);
        const subDisplay = sess.subject_code ? `${sess.subject_code} - ${sess.subject_name}` : (sess.subject_name || 'Subject');
        return `
          <tr>
            <td><strong>${escapeHtml(sess.date || '')}</strong></td>
            <td><span class="badge bg-light text-dark border">P${sess.period}</span></td>
            <td>${escapeHtml(sess.class_name || '')}</td>
            <td>${escapeHtml(subDisplay)}</td>
            <td>${total}</td>
            <td><span class="text-success fw-bold">${present}</span></td>
            <td><span class="text-danger fw-bold">${sess.absent !== undefined ? sess.absent : (sess.absent_count || 0)}</span></td>
            <td>
              <span class="badge ${rate >= 75 ? 'bg-success' : 'bg-warning text-dark'}">
                ${rate.toFixed(1)}%
              </span>
            </td>
          </tr>
        `;
      }).join('');
    }
  }
}

// --------------------------------------------------------
// 3. ADMIN ATTENDANCE DASHBOARD
// --------------------------------------------------------

let adminDashboardCachedData = null;

async function loadAdminAttendanceDashboard(customFilters = {}) {
  const params = { ...customFilters };

  if (!customFilters.class_id) {
    const classVal = document.getElementById('admin-dash-filter-class')?.value;
    if (classVal) params.class_id = parseInt(classVal, 10);
  }
  if (!customFilters.subject_id) {
    const subVal = document.getElementById('admin-dash-filter-subject')?.value;
    if (subVal) params.subject_id = parseInt(subVal, 10);
  }
  if (!customFilters.teacher_id) {
    const teacherVal = document.getElementById('admin-dash-filter-teacher')?.value;
    if (teacherVal) params.teacher_id = parseInt(teacherVal, 10);
  }
  if (!customFilters.student_id && !customFilters.student) {
    const studentVal = document.getElementById('admin-dash-filter-student')?.value;
    if (studentVal && studentVal.trim()) {
      if (studentVal.trim().match(/^\d+$/)) {
        params.student_id = parseInt(studentVal.trim(), 10);
      } else {
        params.student = studentVal.trim();
      }
    }
  }
  if (!customFilters.start_date) {
    const startVal = document.getElementById('admin-dash-filter-start-date')?.value;
    if (startVal) params.start_date = startVal;
  }
  if (!customFilters.end_date) {
    const endVal = document.getElementById('admin-dash-filter-end-date')?.value;
    if (endVal) params.end_date = endVal;
  }

  try {
    const data = await Api.getAdminAttendanceDashboard(params);
    adminDashboardCachedData = data;

    // Populate filter dropdowns from all_classes, all_subjects, teacher_activity if needed
    populateAdminDashboardFilters(data);

    // 1. Statistics KPIs & Donut / Timeline Charts
    renderAdminStatistics(data.statistics, data.date_wise || []);

    // 2. All Classes (Chart + Table)
    renderAdminClasses(data.all_classes || []);

    // 3. All Subjects (Chart + Table)
    renderAdminSubjects(data.all_subjects || []);

    // 4. Teacher Attendance Activity (Chart + Table)
    renderAdminTeacherActivity(data.teacher_activity || []);

  } catch (err) {
    console.error('Failed to load admin attendance dashboard:', err);
  }
}

function populateAdminDashboardFilters(data) {
  const classSelect = document.getElementById('admin-dash-filter-class');
  if (classSelect && classSelect.options.length <= 1) {
    const currentVal = classSelect.value;
    classSelect.innerHTML = '<option value="">All Classes</option>';
    const classes = data.available_filters?.classes || data.all_classes || [];
    classes.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.id || c.class_id;
      opt.textContent = c.name || c.class_name;
      classSelect.appendChild(opt);
    });
    if (currentVal) classSelect.value = currentVal;
  }

  const subSelect = document.getElementById('admin-dash-filter-subject');
  if (subSelect && subSelect.options.length <= 1) {
    const currentVal = subSelect.value;
    subSelect.innerHTML = '<option value="">All Subjects</option>';
    const subs = data.available_filters?.subjects || data.all_subjects || [];
    subs.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id || s.subject_id;
      const code = s.code || s.subject_code || '';
      const name = s.name || s.subject_name || '';
      opt.textContent = code ? `${code} - ${name}` : name;
      subSelect.appendChild(opt);
    });
    if (currentVal) subSelect.value = currentVal;
  }

  const teacherSelect = document.getElementById('admin-dash-filter-teacher');
  if (teacherSelect && teacherSelect.options.length <= 1) {
    const currentVal = teacherSelect.value;
    teacherSelect.innerHTML = '<option value="">All Teachers</option>';
    const teachers = data.available_filters?.teachers || data.teacher_activity || [];
    teachers.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id || t.teacher_id;
      opt.textContent = t.name || t.teacher_name;
      teacherSelect.appendChild(opt);
    });
    if (currentVal) teacherSelect.value = currentVal;
  }
}

function renderAdminStatistics(stats, dateWise) {
  if (!stats) return;

  const totalSessions = stats.total_sessions || 0;
  const totalRecords = stats.total_records !== undefined ? stats.total_records : (stats.total_attendance_records || 0);
  const present = stats.present !== undefined ? stats.present : (stats.present_count !== undefined ? stats.present_count : (stats.total_present || 0));
  const absent = stats.absent !== undefined ? stats.absent : (stats.absent_count !== undefined ? stats.absent_count : (stats.total_absent || 0));
  const overallRate = stats.overall_attendance_rate !== undefined ? stats.overall_attendance_rate : 0;
  const todayRate = stats.today_attendance_rate !== null && stats.today_attendance_rate !== undefined ? stats.today_attendance_rate : 0;
  const todaySessions = stats.today_sessions !== undefined ? stats.today_sessions : (stats.today_sessions_count || 0);

  const sessionsEl = document.getElementById('admin-dash-stat-sessions');
  const recordsEl = document.getElementById('admin-dash-stat-records');
  const rateEl = document.getElementById('admin-dash-stat-rate');
  const presentEl = document.getElementById('admin-dash-stat-present');
  const presentRateEl = document.getElementById('admin-dash-stat-present-rate');
  const absentEl = document.getElementById('admin-dash-stat-absent');
  const absentRateEl = document.getElementById('admin-dash-stat-absent-rate');
  const todayRateEl = document.getElementById('admin-dash-stat-today-rate');
  const todaySessionsEl = document.getElementById('admin-dash-stat-today-sessions');
  const activeFacultyEl = document.getElementById('admin-dash-stat-active-teachers');

  if (sessionsEl) sessionsEl.textContent = totalSessions;
  if (recordsEl) recordsEl.textContent = `${totalRecords} records marked`;
  if (rateEl) rateEl.textContent = `${overallRate.toFixed(1)}%`;
  if (presentEl) presentEl.textContent = present;
  if (presentRateEl) presentRateEl.textContent = `${overallRate.toFixed(1)}% of total`;
  if (absentEl) absentEl.textContent = absent;
  if (absentRateEl) absentRateEl.textContent = `${(100 - overallRate).toFixed(1)}% of total`;

  if (todayRateEl) todayRateEl.textContent = `${todayRate.toFixed(1)}%`;
  if (todaySessionsEl) todaySessionsEl.textContent = `${todaySessions} sessions today`;

  if (activeFacultyEl && adminDashboardCachedData?.teacher_activity) {
    const activeCount = adminDashboardCachedData.teacher_activity.filter(t => (t.sessions_taken || t.sessions_count || 0) > 0).length;
    activeFacultyEl.textContent = `${activeCount} / ${adminDashboardCachedData.teacher_activity.length}`;
  }

  // Chart 1: Institutional Status Breakdown (Donut)
  const hasData = (present + absent) > 0;
  createOrUpdateChart('admin-chart-status', {
    type: 'doughnut',
    data: {
      labels: hasData ? ['Present', 'Absent'] : ['No Data'],
      datasets: [{
        data: hasData ? [present, absent] : [0, 1],
        backgroundColor: hasData ? ['#10b981', '#ef4444'] : ['#e2e8f0', '#cbd5e1'],
        borderWidth: 2,
        borderColor: '#ffffff',
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '70%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { boxWidth: 12, padding: 8, font: { family: 'Inter', size: 11 } }
        }
      }
    }
  });

  // Chart 2: Institutional Daily Trend (%)
  const labels = dateWise.map(d => d.date);
  const data = dateWise.map(d => d.attendance_rate || 0);

  createOrUpdateChart('admin-chart-timeline', {
    type: 'line',
    data: {
      labels: labels.length > 0 ? labels : ['No Timeline Data'],
      datasets: [{
        label: 'Institutional Attendance Rate (%)',
        data: data.length > 0 ? data : [0],
        borderColor: '#2563eb',
        backgroundColor: 'rgba(37, 99, 235, 0.12)',
        borderWidth: 2.5,
        tension: 0.35,
        fill: true,
        pointRadius: 4,
        pointBackgroundColor: '#2563eb'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } },
        x: { grid: { display: false } }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => `Attendance Rate: ${ctx.parsed.y.toFixed(1)}%`
          }
        }
      }
    }
  });
}

function renderAdminClasses(classes) {
  const badge = document.getElementById('admin-dash-classes-badge');
  if (badge) badge.textContent = `${classes.length} Classes`;

  const tbody = document.getElementById('admin-dash-classes-table-body');
  if (tbody) {
    if (classes.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center py-3 text-muted">No classes found.</td></tr>';
    } else {
      tbody.innerHTML = classes.map(c => {
        const rate = c.attendance_rate !== null && c.attendance_rate !== undefined ? c.attendance_rate : 0;
        const isHealthy = rate >= 75;
        const sessions = c.sessions_taken !== undefined ? c.sessions_taken : (c.sessions_count || 0);
        const records = c.records_marked !== undefined ? c.records_marked : (c.records_count || 0);
        return `
          <tr>
            <td><strong>${escapeHtml(c.class_name || c.name || '')}</strong></td>
            <td>${escapeHtml(c.department || '')}</td>
            <td>Year ${c.year || ''} - Sec ${escapeHtml(c.section || '')}</td>
            <td>${escapeHtml(c.class_teacher_name || 'Unassigned')}</td>
            <td>${sessions}</td>
            <td>${records}</td>
            <td>
              <div class="d-flex align-items-center gap-2">
                <div class="progress flex-grow-1" style="height: 6px; width: 60px;">
                  <div class="progress-bar ${isHealthy ? 'bg-success' : 'bg-danger'}" style="width: ${rate}%;"></div>
                </div>
                <span class="fw-bold small ${isHealthy ? 'text-success' : 'text-danger'}">
                  ${rate.toFixed(1)}%
                </span>
              </div>
            </td>
            <td>
              <span class="badge ${isHealthy ? 'bg-success-subtle text-success border border-success-subtle' : 'bg-danger-subtle text-danger border border-danger-subtle'}">
                ${isHealthy ? 'Good Standing' : 'Attention Needed'}
              </span>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  // Bar Chart: All Classes
  const labels = classes.map(c => c.class_name || c.name);
  const data = classes.map(c => c.attendance_rate !== null && c.attendance_rate !== undefined ? c.attendance_rate : 0);
  const bgColors = classes.map(c => (c.attendance_rate >= 75 ? '#3b82f6' : '#ef4444'));

  createOrUpdateChart('admin-chart-classes', {
    type: 'bar',
    data: {
      labels: labels.length > 0 ? labels : ['No Classes'],
      datasets: [{
        label: 'Attendance Rate (%)',
        data: data.length > 0 ? data : [0],
        backgroundColor: bgColors.length > 0 ? bgColors : ['#cbd5e1'],
        borderRadius: 4,
        maxBarThickness: 32
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } },
        x: { grid: { display: false } }
      },
      plugins: { legend: { display: false } }
    }
  });
}

function renderAdminSubjects(subjects) {
  const badge = document.getElementById('admin-dash-subjects-badge');
  if (badge) badge.textContent = `${subjects.length} Subjects`;

  const tbody = document.getElementById('admin-dash-subjects-table-body');
  if (tbody) {
    if (subjects.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center py-3 text-muted">No subjects found.</td></tr>';
    } else {
      tbody.innerHTML = subjects.map(s => {
        const rate = s.attendance_rate !== null && s.attendance_rate !== undefined ? s.attendance_rate : 0;
        const facultyStr = s.assigned_teachers && s.assigned_teachers.length > 0 
          ? s.assigned_teachers.join(', ') 
          : 'None Assigned';
        const classesCount = s.classes_count !== undefined ? s.classes_count : 0;
        const sessions = s.sessions_taken !== undefined ? s.sessions_taken : (s.sessions_count || 0);
        const records = s.records_marked !== undefined ? s.records_marked : (s.records_count || 0);
        return `
          <tr>
            <td><span class="badge bg-light text-dark border">${escapeHtml(s.subject_code || s.code || '')}</span></td>
            <td><strong>${escapeHtml(s.subject_name || s.name || '')}</strong></td>
            <td><small class="text-secondary">${escapeHtml(facultyStr)}</small></td>
            <td>${classesCount} classes</td>
            <td>${sessions}</td>
            <td>${records}</td>
            <td>
              <span class="badge ${rate >= 75 ? 'bg-success' : rate > 0 ? 'bg-warning text-dark' : 'bg-secondary'}">
                ${rate.toFixed(1)}%
              </span>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  // Bar Chart: All Subjects
  const labels = subjects.map(s => s.subject_code || s.code || s.subject_name);
  const data = subjects.map(s => s.attendance_rate !== null && s.attendance_rate !== undefined ? s.attendance_rate : 0);
  const bgColors = subjects.map(s => (s.attendance_rate >= 75 ? '#06b6d4' : '#f59e0b'));

  createOrUpdateChart('admin-chart-subjects', {
    type: 'bar',
    data: {
      labels: labels.length > 0 ? labels : ['No Subjects'],
      datasets: [{
        label: 'Attendance Rate (%)',
        data: data.length > 0 ? data : [0],
        backgroundColor: bgColors.length > 0 ? bgColors : ['#cbd5e1'],
        borderRadius: 4,
        maxBarThickness: 32
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } },
        x: { grid: { display: false } }
      },
      plugins: { legend: { display: false } }
    }
  });
}

function renderAdminTeacherActivity(teachers) {
  const badge = document.getElementById('admin-dash-teachers-badge');
  if (badge) badge.textContent = `${teachers.length} Faculty Members`;

  const tbody = document.getElementById('admin-dash-teachers-table-body');
  if (tbody) {
    if (teachers.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="text-center py-3 text-muted">No teacher activity recorded.</td></tr>';
    } else {
      tbody.innerHTML = teachers.map(t => {
        const subs = t.assigned_subjects && t.assigned_subjects.length > 0 
          ? t.assigned_subjects.join(', ') 
          : 'None';
        const sessions = t.sessions_taken !== undefined ? t.sessions_taken : (t.sessions_count || 0);
        const records = t.records_marked !== undefined ? t.records_marked : (t.records_count || 0);
        const isActive = sessions > 0;
        return `
          <tr>
            <td><strong>${escapeHtml(t.teacher_name || '')}</strong></td>
            <td>${escapeHtml(t.department || 'General')}</td>
            <td><span class="badge bg-secondary-subtle text-secondary">${escapeHtml(t.role || '')}</span></td>
            <td><small class="text-muted">${escapeHtml(subs)}</small></td>
            <td><strong class="text-primary">${sessions}</strong> sessions</td>
            <td>${records}</td>
            <td>${t.last_active_date && t.last_active_date !== 'No Activity' ? t.last_active_date : '<span class="text-muted">No activity</span>'}</td>
            <td>
              <span class="badge ${isActive ? 'bg-success-subtle text-success border border-success-subtle' : 'bg-secondary-subtle text-muted'}">
                ${isActive ? '<i class="bi bi-circle-fill text-success me-1"></i>Active' : 'Idle'}
              </span>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  // Bar Chart: Teacher Activity (Sessions Conducted)
  const labels = teachers.map(t => t.teacher_name);
  const data = teachers.map(t => t.sessions_taken !== undefined ? t.sessions_taken : (t.sessions_count || 0));

  createOrUpdateChart('admin-chart-teachers', {
    type: 'bar',
    data: {
      labels: labels.length > 0 ? labels : ['No Teachers'],
      datasets: [{
        label: 'Sessions Taken',
        data: data.length > 0 ? data : [0],
        backgroundColor: '#f59e0b',
        borderRadius: 4,
        maxBarThickness: 32
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } },
        x: { grid: { display: false } }
      },
      plugins: { legend: { display: false } }
    }
  });
}

// --------------------------------------------------------
// 4. INITIALIZE ATTENDANCE DASHBOARDS & EVENT LISTENERS
// --------------------------------------------------------

function initAttendanceDashboards() {
  // Class Teacher Dashboard Filters
  const btnCtApply = document.getElementById('btn-ct-dash-apply-filters');
  if (btnCtApply) {
    btnCtApply.addEventListener('click', () => {
      loadClassTeacherDashboard();
    });
  }

  const ctClassSelect = document.getElementById('ct-dash-filter-class');
  if (ctClassSelect) {
    ctClassSelect.addEventListener('change', () => {
      loadClassTeacherDashboard();
    });
  }

  const btnCtReset = document.getElementById('btn-ct-dash-reset-filters');
  if (btnCtReset) {
    btnCtReset.addEventListener('click', () => {
      const cls = document.getElementById('ct-dash-filter-class');
      const sub = document.getElementById('ct-dash-filter-subject');
      const teacher = document.getElementById('ct-dash-filter-teacher');
      const st = document.getElementById('ct-dash-filter-student');
      const start = document.getElementById('ct-dash-filter-start');
      const end = document.getElementById('ct-dash-filter-end');
      if (cls) cls.value = '';
      if (sub) sub.value = '';
      if (teacher) teacher.value = '';
      if (st) st.value = '';
      if (start) start.value = '';
      if (end) end.value = '';
      loadClassTeacherDashboard();
    });
  }

  // Class Teacher Student-wise Table Live Filter
  const ctStudentSearch = document.getElementById('ct-dash-student-search-input');
  const ctStudentStatusFilter = document.getElementById('ct-dash-student-status-filter');
  if (ctStudentSearch) {
    ctStudentSearch.addEventListener('input', () => {
      if (ctDashboardCachedData?.student_wise) {
        renderClassTeacherStudentTable(
          ctDashboardCachedData.student_wise,
          ctStudentSearch.value,
          ctStudentStatusFilter?.value || 'all'
        );
      }
    });
  }
  if (ctStudentStatusFilter) {
    ctStudentStatusFilter.addEventListener('change', () => {
      if (ctDashboardCachedData?.student_wise) {
        renderClassTeacherStudentTable(
          ctDashboardCachedData.student_wise,
          ctStudentSearch?.value || '',
          ctStudentStatusFilter.value
        );
      }
    });
  }

  // Subject Teacher Dashboard Filters
  const btnStApply = document.getElementById('btn-st-dash-apply-filters');
  if (btnStApply) {
    btnStApply.addEventListener('click', () => {
      loadSubjectTeacherDashboard();
    });
  }

  const btnStReset = document.getElementById('btn-st-dash-reset-filters');
  if (btnStReset) {
    btnStReset.addEventListener('click', () => {
      const cls = document.getElementById('st-dash-filter-class');
      const sub = document.getElementById('st-dash-filter-subject');
      const st = document.getElementById('st-dash-filter-student');
      const teacher = document.getElementById('st-dash-filter-teacher');
      const start = document.getElementById('st-dash-filter-start');
      const end = document.getElementById('st-dash-filter-end');
      if (cls) cls.value = '';
      if (sub) sub.value = '';
      if (st) st.value = '';
      if (teacher) teacher.value = '';
      if (start) start.value = '';
      if (end) end.value = '';
      loadSubjectTeacherDashboard();
    });
  }

  // Admin Attendance Dashboard Filters
  const btnAdminApply = document.getElementById('btn-admin-dash-apply-filters');
  if (btnAdminApply) {
    btnAdminApply.addEventListener('click', () => {
      loadAdminAttendanceDashboard();
    });
  }

  const btnAdminReset = document.getElementById('btn-admin-dash-reset-filters');
  if (btnAdminReset) {
    btnAdminReset.addEventListener('click', () => {
      const cls = document.getElementById('admin-dash-filter-class');
      const sub = document.getElementById('admin-dash-filter-subject');
      const teacher = document.getElementById('admin-dash-filter-teacher');
      const student = document.getElementById('admin-dash-filter-student');
      const start = document.getElementById('admin-dash-filter-start-date');
      const end = document.getElementById('admin-dash-filter-end-date');
      if (cls) cls.value = '';
      if (sub) sub.value = '';
      if (teacher) teacher.value = '';
      if (student) student.value = '';
      if (start) start.value = '';
      if (end) end.value = '';
      loadAdminAttendanceDashboard();
    });
  }

  const btnAdminRefresh = document.getElementById('btn-admin-dash-refresh');
  if (btnAdminRefresh) {
    btnAdminRefresh.addEventListener('click', () => {
      loadAdminAttendanceDashboard();
    });
  }

  // Bootstrap Sub-Tab Shown Event Listeners
  const tabBtnCtAttendance = document.getElementById('tab-btn-attendance');
  if (tabBtnCtAttendance) {
    tabBtnCtAttendance.addEventListener('shown.bs.tab', () => {
      loadClassTeacherDashboard();
    });
  }

  const tabBtnCtSubjects = document.getElementById('tab-btn-subjects');
  if (tabBtnCtSubjects) {
    tabBtnCtSubjects.addEventListener('shown.bs.tab', () => {
      loadClassTeacherSubjectTeachers();
    });
  }

  const tabBtnStDashboard = document.getElementById('st-tab-btn-dashboard');
  if (tabBtnStDashboard) {
    tabBtnStDashboard.addEventListener('shown.bs.tab', () => {
      loadSubjectTeacherDashboard();
    });
  }
}

function navigateToDashboard(roleType) {
  if (roleType === 'class-teacher') {
    const link = document.querySelector('.sidebar-nav .nav-link[data-target="class-teacher-section"]');
    if (link) link.click();
    const tabBtn = document.getElementById('tab-btn-attendance');
    if (tabBtn && typeof bootstrap !== 'undefined') {
      bootstrap.Tab.getOrCreateInstance(tabBtn).show();
    }
  } else if (roleType === 'subject-teacher') {
    const link = document.querySelector('.sidebar-nav .nav-link[data-target="subject-teacher-section"]');
    if (link) link.click();
    const tabBtn = document.getElementById('st-tab-btn-dashboard');
    if (tabBtn && typeof bootstrap !== 'undefined') {
      bootstrap.Tab.getOrCreateInstance(tabBtn).show();
    }
  } else if (roleType === 'admin') {
    const link = document.querySelector('.sidebar-nav .nav-link[data-target="admin-section"]');
    if (link) link.click();
    const tabBtn = document.getElementById('admin-tab-btn-analytics');
    if (tabBtn) tabBtn.click();
  }
}

function exportAttendanceCSV() {
  let rows = [];
  const nowStr = new Date().toISOString().split('T')[0];

  if (adminDashboardCachedData && adminDashboardCachedData.all_classes) {
    rows.push(['Class Name', 'Department', 'Year', 'Section', 'Class Teacher', 'Sessions Conducted', 'Records Marked', 'Attendance Rate %', 'Status']);
    adminDashboardCachedData.all_classes.forEach(c => {
      rows.push([
        `"${c.class_name || c.name || ''}"`,
        `"${c.department || ''}"`,
        `"${c.year || ''}"`,
        `"${c.section || ''}"`,
        `"${c.class_teacher_name || 'Unassigned'}"`,
        c.sessions_taken || c.sessions_count || 0,
        c.records_marked || c.records_count || 0,
        (c.attendance_rate || 0).toFixed(1),
        `"${c.status_label || ''}"`
      ]);
    });
  } else if (ctDashboardCachedData && ctDashboardCachedData.student_wise) {
    rows.push(['Roll Number', 'Full Name', 'Register Number', 'Face Enrolled', 'Total Sessions', 'Attended', 'Absent', 'Attendance Rate %', 'Status']);
    ctDashboardCachedData.student_wise.forEach(st => {
      rows.push([
        `"${st.roll_number || ''}"`,
        `"${st.full_name || ''}"`,
        `"${st.register_number || ''}"`,
        st.face_enrolled ? 'Yes' : 'No',
        st.total_sessions || 0,
        st.attended_sessions || 0,
        st.absent_sessions || 0,
        (st.attendance_rate || 0).toFixed(1),
        `"${st.status_label || ''}"`
      ]);
    });
  } else if (stDashboardCachedData && stDashboardCachedData.recent_sessions) {
    rows.push(['Date', 'Period', 'Class', 'Subject', 'Total Students', 'Present', 'Absent', 'Attendance Rate %']);
    stDashboardCachedData.recent_sessions.forEach(s => {
      rows.push([
        `"${s.date || ''}"`,
        `P${s.period}`,
        `"${s.class_name || ''}"`,
        `"${s.subject_name || ''}"`,
        s.total_students || s.total_marked || 0,
        s.present || 0,
        s.absent || 0,
        (s.attendance_rate || 0).toFixed(1)
      ]);
    });
  } else {
    rows.push(['Export Date', 'Status', 'Message']);
    rows.push([nowStr, 'Notice', 'Please open a dashboard first to generate and export data.']);
  }

  const csvContent = 'data:text/csv;charset=utf-8,' + rows.map(e => e.join(',')).join('\n');
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `attendance_report_${nowStr}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

window.loadClassTeacherDashboard = loadClassTeacherDashboard;
window.loadSubjectTeacherDashboard = loadSubjectTeacherDashboard;
window.loadAdminAttendanceDashboard = loadAdminAttendanceDashboard;
window.initAttendanceDashboards = initAttendanceDashboards;
window.navigateToDashboard = navigateToDashboard;
window.exportAttendanceCSV = exportAttendanceCSV;

// ==========================================================
// COMPREHENSIVE ATTENDANCE REPORTS MODULE
// ==========================================================
let currentReportType = 'daily';
let reportCachedData = null;
let reportFilters = {
  start_date: '',
  end_date: '',
  class_id: '',
  subject_id: '',
  teacher_id: '',
  student: '',
  year: '',
  month: '',
};
let reportDropdownsLoaded = false;

async function initAttendanceReportsModule() {
  if (reportDropdownsLoaded) return;
  try {
    // Populate classes
    const classesRes = await Api.listClasses().catch(() => []);
    const classSelect = document.getElementById('report-filter-class');
    if (classSelect && Array.isArray(classesRes)) {
      classSelect.innerHTML = '<option value="">All Classes</option>';
      classesRes.forEach(c => {
        classSelect.innerHTML += `<option value="${c.id}">${c.name || `${c.department} - Year ${c.year} - Sec ${c.section}`}</option>`;
      });
    }

    // Populate subjects
    const subjectsRes = await Api.listSubjects().catch(() => []);
    const subjectSelect = document.getElementById('report-filter-subject');
    if (subjectSelect && Array.isArray(subjectsRes)) {
      subjectSelect.innerHTML = '<option value="">All Subjects</option>';
      subjectsRes.forEach(s => {
        subjectSelect.innerHTML += `<option value="${s.id}">${s.code} - ${s.name}</option>`;
      });
    }

    // Populate teachers
    const teachersRes = await Api.listTeachers().catch(() => []);
    const teacherSelect = document.getElementById('report-filter-teacher');
    if (teacherSelect && Array.isArray(teachersRes)) {
      teacherSelect.innerHTML = '<option value="">All Teachers</option>';
      teachersRes.forEach(t => {
        teacherSelect.innerHTML += `<option value="${t.id}">${t.full_name || t.username}</option>`;
      });
    }

    reportDropdownsLoaded = true;
  } catch (err) {
    console.warn('Could not populate report filter dropdowns:', err);
  }
}

function switchReportType(type) {
  currentReportType = type || 'daily';

  // Update tabs active state
  document.querySelectorAll('#report-type-nav .nav-link').forEach(btn => {
    btn.classList.remove('active');
  });
  const activeTab = document.getElementById(`btn-report-tab-${currentReportType}`);
  if (activeTab) activeTab.classList.add('active');

  // Toggle filter visibility
  const monthGroup = document.getElementById('filter-group-month');
  const yearGroup = document.getElementById('filter-group-year');
  const studentGroup = document.getElementById('filter-group-student');

  if (monthGroup) monthGroup.classList.toggle('d-none', currentReportType !== 'monthly');
  if (yearGroup) yearGroup.classList.toggle('d-none', currentReportType !== 'monthly');
  if (studentGroup) studentGroup.classList.toggle('d-none', currentReportType !== 'student');

  // Switch active data view
  document.querySelectorAll('.report-data-view').forEach(view => {
    view.classList.add('d-none');
  });
  const targetView = document.getElementById(`report-view-${currentReportType}`);
  if (targetView) targetView.classList.remove('d-none');

  // Set Banner Title
  const titles = {
    daily: 'DAILY ATTENDANCE REPORT',
    student: 'STUDENT ATTENDANCE REPORT',
    subject: 'SUBJECT ATTENDANCE REPORT',
    class: 'CLASS ATTENDANCE REPORT',
    monthly: 'MONTHLY ATTENDANCE REPORT',
  };
  const titleElem = document.getElementById('report-banner-title');
  if (titleElem) titleElem.textContent = titles[currentReportType] || 'ATTENDANCE REPORT';

  // Load report data
  loadAttendanceReport();
}

function setReportDatePreset(preset) {
  // Update button active states
  document.querySelectorAll('.report-date-presets button').forEach(b => b.classList.remove('active'));
  if (window.event && window.event.target) {
    window.event.target.classList.add('active');
  }

  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];
  const startInput = document.getElementById('report-filter-start');
  const endInput = document.getElementById('report-filter-end');

  if (preset === 'today') {
    if (startInput) startInput.value = todayStr;
    if (endInput) endInput.value = todayStr;
  } else if (preset === '7days') {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    if (startInput) startInput.value = d.toISOString().split('T')[0];
    if (endInput) endInput.value = todayStr;
  } else if (preset === 'this_month') {
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
    if (startInput) startInput.value = firstDay;
    if (endInput) endInput.value = todayStr;
  } else if (preset === '30days') {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    if (startInput) startInput.value = d.toISOString().split('T')[0];
    if (endInput) endInput.value = todayStr;
  } else if (preset === 'all') {
    if (startInput) startInput.value = '';
    if (endInput) endInput.value = '';
  }

  applyReportFilters();
}

function applyReportFilters() {
  reportFilters.start_date = document.getElementById('report-filter-start')?.value || '';
  reportFilters.end_date = document.getElementById('report-filter-end')?.value || '';
  reportFilters.class_id = document.getElementById('report-filter-class')?.value || '';
  reportFilters.subject_id = document.getElementById('report-filter-subject')?.value || '';
  reportFilters.teacher_id = document.getElementById('report-filter-teacher')?.value || '';
  reportFilters.student = document.getElementById('report-filter-student')?.value || '';
  reportFilters.year = document.getElementById('report-filter-year')?.value || '';
  reportFilters.month = document.getElementById('report-filter-month')?.value || '';

  loadAttendanceReport();
}

function resetReportFilters() {
  if (document.getElementById('report-filter-start')) document.getElementById('report-filter-start').value = '';
  if (document.getElementById('report-filter-end')) document.getElementById('report-filter-end').value = '';
  if (document.getElementById('report-filter-class')) document.getElementById('report-filter-class').value = '';
  if (document.getElementById('report-filter-subject')) document.getElementById('report-filter-subject').value = '';
  if (document.getElementById('report-filter-teacher')) document.getElementById('report-filter-teacher').value = '';
  if (document.getElementById('report-filter-student')) document.getElementById('report-filter-student').value = '';
  if (document.getElementById('report-filter-month')) document.getElementById('report-filter-month').value = '';

  document.querySelectorAll('.report-date-presets button').forEach(b => b.classList.remove('active'));

  reportFilters = {
    start_date: '',
    end_date: '',
    class_id: '',
    subject_id: '',
    teacher_id: '',
    student: '',
    year: '',
    month: '',
  };

  loadAttendanceReport();
}

function refreshCurrentReport() {
  loadAttendanceReport();
}

async function loadAttendanceReport() {
  const spinner = document.getElementById('report-loading-spinner');
  const emptyState = document.getElementById('report-empty-state');
  const views = document.querySelectorAll('.report-data-view');

  if (spinner) spinner.classList.remove('d-none');
  if (emptyState) emptyState.classList.add('d-none');
  views.forEach(v => v.classList.add('d-none'));

  try {
    initAttendanceReportsModule();
    const data = await Api.getAttendanceReport(currentReportType, reportFilters);
    reportCachedData = data;

    // Update KPI Cards
    const summary = data.summary || {};
    const totalClasses = summary.total_classes || 0;
    const presentCount = summary.present_count || 0;
    const absentCount = summary.absent_count || 0;
    const rawRate = (summary.attendance_percentage !== undefined ? summary.attendance_percentage : (summary.overall_attendance_percentage || 0));
    const rate = Number(rawRate).toFixed(1);

    const kpiTotal = document.getElementById('report-kpi-total-classes');
    const kpiPres = document.getElementById('report-kpi-present');
    const kpiAbs = document.getElementById('report-kpi-absent');
    const kpiRate = document.getElementById('report-kpi-rate');
    const kpiRateStatus = document.getElementById('report-kpi-rate-status');

    if (kpiTotal) kpiTotal.textContent = totalClasses;
    if (kpiPres) kpiPres.textContent = presentCount;
    if (kpiAbs) kpiAbs.textContent = absentCount;
    if (kpiRate) kpiRate.textContent = `${rate}%`;
    if (kpiRateStatus) {
      kpiRateStatus.textContent = Number(rate) >= 75 ? 'Good Standing (≥75%)' : 'Attention Needed (<75%)';
      kpiRateStatus.className = Number(rate) >= 75 ? 'text-success fw-semibold' : 'text-danger fw-semibold';
    }

    // Update banner metadata
    const generatedDateElem = document.getElementById('report-meta-generated-date');
    if (generatedDateElem) generatedDateElem.textContent = new Date().toLocaleString();

    const subtitleElem = document.getElementById('report-banner-subtitle');
    if (subtitleElem) {
      const dRange = (reportFilters.start_date || reportFilters.end_date)
        ? `From ${reportFilters.start_date || 'Earliest'} to ${reportFilters.end_date || 'Latest'}`
        : 'All-Time Records';
      subtitleElem.textContent = `${dRange} • Calculated from stored attendance database`;
    }

    const filterStatusElem = document.getElementById('report-filter-status-text');
    if (filterStatusElem) {
      filterStatusElem.textContent = `Showing ${data.rows?.length || 0} ${currentReportType} ledger row(s) • Total student records: ${summary.total_records || 0}`;
    }

    // Hide spinner
    if (spinner) spinner.classList.add('d-none');

    const rows = data.rows || [];
    if (rows.length === 0) {
      if (emptyState) emptyState.classList.remove('d-none');
      return;
    }

    const activeView = document.getElementById(`report-view-${currentReportType}`);
    if (activeView) activeView.classList.remove('d-none');

    if (currentReportType === 'daily') {
      renderDailyReport(data);
    } else if (currentReportType === 'student') {
      renderStudentReport(data);
    } else if (currentReportType === 'subject') {
      renderSubjectReport(data);
    } else if (currentReportType === 'class') {
      renderClassReport(data);
    } else if (currentReportType === 'monthly') {
      renderMonthlyReport(data);
    }
  } catch (err) {
    if (spinner) spinner.classList.add('d-none');
    console.error('Error loading attendance report:', err);
    if (typeof showAlert === 'function') {
      showAlert('danger', `Failed to load ${currentReportType} report: ${err.message}`);
    }
  }
}

// Render 1. Daily Report
function renderDailyReport(data) {
  const tbody = document.getElementById('report-daily-tbody');
  const countBadge = document.getElementById('report-daily-dates-count');
  if (countBadge) countBadge.textContent = `${data.rows?.length || 0} Days`;
  if (!tbody) return;

  tbody.innerHTML = '';
  data.rows.forEach((r, idx) => {
    const rateVal = Number(r.attendance_percentage || 0);
    const isGood = rateVal >= 75;
    const badgeClass = isGood ? 'bg-success-subtle text-success border border-success' : 'bg-danger-subtle text-danger border border-danger';
    const rowId = `daily-row-${idx}`;
    const collapseId = `daily-sess-collapse-${idx}`;
    const hasSessions = r.sessions && r.sessions.length > 0;

    let sessionsHtml = '';
    if (hasSessions) {
      sessionsHtml = `
        <tr class="collapse-row print-show" id="${collapseId}" style="display: none;">
          <td colspan="8" class="p-3 bg-light border-bottom">
            <div class="p-3 bg-white border rounded-3 shadow-sm">
              <h6 class="fw-bold text-dark small mb-2"><i class="bi bi-clock-history me-1 text-primary"></i>Period Sessions Conducted on ${r.date}:</h6>
              <div class="table-responsive">
                <table class="table table-sm table-bordered align-middle mb-0 extra-small">
                  <thead class="table-light">
                    <tr>
                      <th>Period</th>
                      <th>Class</th>
                      <th>Subject Code</th>
                      <th>Subject Name</th>
                      <th>Teacher</th>
                      <th>Enrolled Students</th>
                      <th>Present</th>
                      <th>Absent</th>
                      <th>Attendance %</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${r.sessions.map(s => `
                      <tr>
                        <td><strong>Period ${s.period}</strong></td>
                        <td>${escapeHtml(s.class_name)}</td>
                        <td><code>${escapeHtml(s.subject_code)}</code></td>
                        <td>${escapeHtml(s.subject_name)}</td>
                        <td>${escapeHtml(s.teacher_name)}</td>
                        <td>${s.total_students}</td>
                        <td class="text-success fw-bold">${s.present_count}</td>
                        <td class="text-danger fw-bold">${s.absent_count}</td>
                        <td><span class="badge ${Number(s.attendance_percentage || 0) >= 75 ? 'bg-success' : 'bg-danger'}">${Number(s.attendance_percentage || 0).toFixed(1)}%</span></td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            </div>
          </td>
        </tr>
      `;
    }

    tbody.innerHTML += `
      <tr id="${rowId}">
        <td class="text-muted small print-hide">${idx + 1}</td>
        <td><strong>${escapeHtml(r.date)}</strong></td>
        <td><span class="badge bg-primary-subtle text-primary border border-primary">${r.total_classes} Classes</span></td>
        <td class="text-success fw-bold">${r.present_count}</td>
        <td class="text-danger fw-bold">${r.absent_count}</td>
        <td>${r.total_records}</td>
        <td><span class="badge ${badgeClass}">${rateVal.toFixed(1)}%</span></td>
        <td class="text-end print-hide">
          ${hasSessions ? `
            <button type="button" class="btn btn-outline-secondary btn-sm py-0" onclick="toggleDailySessionsCollapse('${collapseId}')">
              <i class="bi bi-chevron-down me-1"></i>Sessions (${r.sessions.length})
            </button>
          ` : '<span class="text-muted small">-</span>'}
        </td>
      </tr>
      ${sessionsHtml}
    `;
  });
}

function toggleDailySessionsCollapse(collapseId) {
  const el = document.getElementById(collapseId);
  if (!el) return;
  el.style.display = (el.style.display === 'none' || el.style.display === '') ? 'table-row' : 'none';
}

// Render 2. Student Report
function renderStudentReport(data) {
  const tbody = document.getElementById('report-student-tbody');
  const eligibleBadge = document.getElementById('report-student-eligible-badge');
  const shortageBadge = document.getElementById('report-student-shortage-badge');

  if (eligibleBadge) eligibleBadge.textContent = `${data.summary?.eligible_count || 0} Eligible (≥75%)`;
  if (shortageBadge) shortageBadge.textContent = `${data.summary?.shortage_count || 0} Shortage (<75%)`;
  if (!tbody) return;

  tbody.innerHTML = '';
  data.rows.forEach((s, idx) => {
    const rateVal = Number(s.attendance_percentage || 0);
    const isEligible = rateVal >= 75;
    const statusBadge = isEligible
      ? '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Eligible</span>'
      : '<span class="badge bg-danger"><i class="bi bi-exclamation-octagon me-1"></i>Shortage</span>';

    tbody.innerHTML += `
      <tr>
        <td class="text-muted small">${idx + 1}</td>
        <td><strong>${escapeHtml(s.roll_number)}</strong></td>
        <td>
          <div class="fw-semibold text-dark">${escapeHtml(s.full_name)}</div>
          <small class="text-muted">${escapeHtml(s.department || '')}</small>
        </td>
        <td><code>${escapeHtml(s.register_number || '-')}</code></td>
        <td>${escapeHtml(s.class_name || 'Unassigned')}</td>
        <td><span class="badge bg-light text-dark border">${s.total_classes}</span></td>
        <td class="text-success fw-bold">${s.present_count}</td>
        <td class="text-danger fw-bold">${s.absent_count}</td>
        <td>
          <div class="d-flex align-items-center gap-2">
            <span class="fw-bold ${isEligible ? 'text-success' : 'text-danger'}">${rateVal.toFixed(1)}%</span>
            <div class="progress flex-grow-1 print-hide" style="height: 6px; width: 60px;">
              <div class="progress-bar ${isEligible ? 'bg-success' : 'bg-danger'}" style="width: ${Math.min(100, rateVal)}%"></div>
            </div>
          </div>
        </td>
        <td>${statusBadge}</td>
        <td class="text-end print-hide">
          <button type="button" class="btn btn-outline-primary btn-sm py-0" onclick="openStudentSessionModal(${s.student_id})">
            <i class="bi bi-clock-history me-1"></i>Log
          </button>
        </td>
      </tr>
    `;
  });
}

// Render 3. Subject Report
function renderSubjectReport(data) {
  const tbody = document.getElementById('report-subject-tbody');
  const countBadge = document.getElementById('report-subject-count-badge');
  if (countBadge) countBadge.textContent = `${data.rows?.length || 0} Subjects`;
  if (!tbody) return;

  tbody.innerHTML = '';
  data.rows.forEach((sub, idx) => {
    const rateVal = Number(sub.attendance_percentage || 0);
    const isGood = rateVal >= 75;
    const teachers = (sub.assigned_teachers && sub.assigned_teachers.length) ? sub.assigned_teachers.join(', ') : 'Unassigned';
    const classes = (sub.classes_covered && sub.classes_covered.length) ? sub.classes_covered.join(', ') : 'None';

    tbody.innerHTML += `
      <tr>
        <td class="text-muted small">${idx + 1}</td>
        <td><code>${escapeHtml(sub.subject_code)}</code></td>
        <td><strong>${escapeHtml(sub.subject_name)}</strong></td>
        <td><small class="text-secondary">${escapeHtml(sub.department || '')}</small></td>
        <td><small class="text-dark">${escapeHtml(teachers)}</small></td>
        <td><small class="text-muted">${escapeHtml(classes)}</small></td>
        <td><span class="badge bg-primary-subtle text-primary border border-primary">${sub.total_classes} Classes</span></td>
        <td class="text-success fw-bold">${sub.present_count}</td>
        <td class="text-danger fw-bold">${sub.absent_count}</td>
        <td>
          <span class="badge ${isGood ? 'bg-success' : 'bg-danger'}">${rateVal.toFixed(1)}%</span>
        </td>
      </tr>
    `;
  });
}

// Render 4. Class Report
function renderClassReport(data) {
  const tbody = document.getElementById('report-class-tbody');
  const countBadge = document.getElementById('report-class-count-badge');
  if (countBadge) countBadge.textContent = `${data.rows?.length || 0} Classes`;
  if (!tbody) return;

  tbody.innerHTML = '';
  data.rows.forEach((c, idx) => {
    const rateVal = Number(c.attendance_percentage || 0);
    const isGood = rateVal >= 75;
    const statusBadge = isGood
      ? '<span class="badge bg-success-subtle text-success border border-success">Good Standing</span>'
      : '<span class="badge bg-danger-subtle text-danger border border-danger">Attention Needed</span>';

    tbody.innerHTML += `
      <tr>
        <td class="text-muted small">${idx + 1}</td>
        <td><strong>${escapeHtml(c.class_name)}</strong></td>
        <td><small class="text-secondary">${escapeHtml(c.department || '')}</small></td>
        <td>Year ${c.year} - Sec ${escapeHtml(c.section)}</td>
        <td>${escapeHtml(c.class_teacher_name || 'Unassigned')}</td>
        <td><span class="badge bg-light text-dark border">${c.enrolled_students} Students</span></td>
        <td><span class="badge bg-primary-subtle text-primary border border-primary">${c.total_classes} Classes</span></td>
        <td class="text-success fw-bold">${c.present_count}</td>
        <td class="text-danger fw-bold">${c.absent_count}</td>
        <td>
          <span class="badge ${isGood ? 'bg-success' : 'bg-danger'}">${rateVal.toFixed(1)}%</span>
        </td>
        <td>${statusBadge}</td>
      </tr>
    `;
  });
}

// Render 5. Monthly Report
function renderMonthlyReport(data) {
  const tbody = document.getElementById('report-monthly-tbody');
  const countBadge = document.getElementById('report-monthly-count-badge');
  if (countBadge) countBadge.textContent = `${data.rows?.length || 0} Months`;
  if (!tbody) return;

  tbody.innerHTML = '';
  data.rows.forEach((m, idx) => {
    const rateVal = Number(m.attendance_percentage || 0);
    const isGood = rateVal >= 75;
    const statusBadge = isGood
      ? '<span class="badge bg-success">Normal Activity</span>'
      : '<span class="badge bg-warning text-dark">Below Target</span>';

    tbody.innerHTML += `
      <tr>
        <td class="text-muted small">${idx + 1}</td>
        <td><strong>${escapeHtml(m.month_name)}</strong></td>
        <td><span class="badge bg-light text-dark border">${m.working_days_count} Working Days</span></td>
        <td><span class="badge bg-primary-subtle text-primary border border-primary">${m.total_classes} Classes</span></td>
        <td class="text-success fw-bold">${m.present_count}</td>
        <td class="text-danger fw-bold">${m.absent_count}</td>
        <td>${m.total_records}</td>
        <td>
          <span class="badge ${isGood ? 'bg-success' : 'bg-danger'}">${rateVal.toFixed(1)}%</span>
        </td>
        <td>${statusBadge}</td>
      </tr>
    `;
  });
}

// Student session log modal
async function openStudentSessionModal(studentId) {
  if (!reportCachedData || !reportCachedData.rows) return;
  const s = reportCachedData.rows.find(item => item.student_id === studentId);
  if (!s) return;

  document.getElementById('modal-student-name').textContent = s.full_name;
  document.getElementById('modal-student-roll').textContent = s.roll_number;
  document.getElementById('modal-student-reg').textContent = s.register_number || '-';
  document.getElementById('modal-student-class').textContent = s.class_name || 'Class Batch';
  document.getElementById('modal-student-total-classes').textContent = s.total_classes;
  document.getElementById('modal-student-present-count').textContent = s.present_count;
  document.getElementById('modal-student-absent-count').textContent = s.absent_count;

  const rateVal = Number(s.attendance_percentage || 0);
  const isEligible = rateVal >= 75;
  const rateBadge = document.getElementById('modal-student-rate-badge');
  const statusText = document.getElementById('modal-student-status-text');

  if (rateBadge) {
    rateBadge.textContent = `${rateVal.toFixed(1)}%`;
    rateBadge.className = `badge fs-6 px-3 py-2 ${isEligible ? 'bg-success' : 'bg-danger'}`;
  }
  if (statusText) {
    statusText.textContent = isEligible ? 'Eligible for Examination' : 'Attendance Shortage Warning';
    statusText.className = `small mt-1 ${isEligible ? 'text-success' : 'text-danger'} fw-semibold`;
  }

  // Load detailed sessions if present or fetch individual student report
  const tbody = document.getElementById('modal-student-sessions-tbody');
  if (tbody) {
    if (s.detailed_sessions && s.detailed_sessions.length > 0) {
      tbody.innerHTML = s.detailed_sessions.map(sess => `
        <tr>
          <td><strong>${escapeHtml(sess.date)}</strong></td>
          <td>Period ${sess.period}</td>
          <td><code>${escapeHtml(sess.subject_code)}</code></td>
          <td>${escapeHtml(sess.subject_name)}</td>
          <td>${escapeHtml(sess.teacher_name)}</td>
          <td class="text-end">
            <span class="badge ${sess.status === 'PRESENT' ? 'bg-success' : 'bg-danger'}">${escapeHtml(sess.status)}</span>
          </td>
        </tr>
      `).join('');
    } else {
      tbody.innerHTML = '<tr><td colspan="5" class="text-center py-3 text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Fetching session log...</td></tr>';
      try {
        const studentDetail = await Api.getStudentReport({ student_id: s.student_id });
        const fetched = studentDetail.rows && studentDetail.rows[0];
        if (fetched && fetched.detailed_sessions && fetched.detailed_sessions.length > 0) {
          tbody.innerHTML = fetched.detailed_sessions.map(sess => `
            <tr>
              <td><strong>${escapeHtml(sess.date)}</strong></td>
              <td>Period ${sess.period}</td>
              <td><code>${escapeHtml(sess.subject_code)}</code></td>
              <td>${escapeHtml(sess.subject_name)}</td>
              <td>${escapeHtml(sess.teacher_name)}</td>
              <td class="text-end">
                <span class="badge ${sess.status === 'PRESENT' ? 'bg-success' : 'bg-danger'}">${escapeHtml(sess.status)}</span>
              </td>
            </tr>
          `).join('');
        } else {
          tbody.innerHTML = '<tr><td colspan="5" class="text-center py-3 text-muted">No individual session records found for this student.</td></tr>';
        }
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-danger">Error: ${escapeHtml(e.message)}</td></tr>`;
      }
    }
  }

  const modalEl = document.getElementById('modal-student-report-sessions');
  if (modalEl && typeof bootstrap !== 'undefined') {
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  }
}

// Export to CSV
async function exportAttendanceReportCSV() {
  try {
    await Api.downloadReportCsv(currentReportType, reportFilters);
  } catch (err) {
    console.warn('API CSV download failed, generating client-side fallback:', err);
    if (!reportCachedData || !reportCachedData.rows || reportCachedData.rows.length === 0) {
      alert('Please generate a report with records before exporting.');
      return;
    }
    const nowStr = new Date().toISOString().split('T')[0];
    let csvRows = [];
    csvRows.push([`# ONE-CLICK ATTENDANCE SYSTEM - ${currentReportType.toUpperCase()} ATTENDANCE REPORT`]);
    csvRows.push([`# Exported Date: ${nowStr}`]);
    const summary = reportCachedData.summary || {};
    csvRows.push([`# Total Classes: ${summary.total_classes || 0}, Present: ${summary.present_count || 0}, Absent: ${summary.absent_count || 0}, Rate: ${Number(summary.attendance_percentage || 0).toFixed(2)}%`]);
    csvRows.push([]);

    if (currentReportType === 'daily') {
      csvRows.push(['Date', 'Total Classes', 'Present Count', 'Absent Count', 'Total Records', 'Attendance Percentage']);
      reportCachedData.rows.forEach(r => {
        csvRows.push([r.date, r.total_classes, r.present_count, r.absent_count, r.total_records, `${Number(r.attendance_percentage || 0).toFixed(2)}%`]);
      });
    } else if (currentReportType === 'student') {
      csvRows.push(['Roll Number', 'Student Name', 'Register No', 'Class', 'Total Classes', 'Present', 'Absent', 'Attendance %', 'Status']);
      reportCachedData.rows.forEach(r => {
        csvRows.push([r.roll_number, `"${r.full_name}"`, r.register_number, `"${r.class_name}"`, r.total_classes, r.present_count, r.absent_count, `${Number(r.attendance_percentage || 0).toFixed(2)}%`, r.status_label]);
      });
    } else if (currentReportType === 'subject') {
      csvRows.push(['Subject Code', 'Subject Name', 'Department', 'Faculty', 'Classes Covered', 'Total Classes', 'Present', 'Absent', 'Attendance %']);
      reportCachedData.rows.forEach(r => {
        csvRows.push([r.subject_code, `"${r.subject_name}"`, r.department, `"${(r.assigned_teachers || []).join(', ')}"`, `"${(r.classes_covered || []).join(', ')}"`, r.total_classes, r.present_count, r.absent_count, `${Number(r.attendance_percentage || 0).toFixed(2)}%`]);
      });
    } else if (currentReportType === 'class') {
      csvRows.push(['Class Name', 'Department', 'Year', 'Section', 'Class Teacher', 'Enrolled Students', 'Total Classes', 'Present', 'Absent', 'Attendance %', 'Standing']);
      reportCachedData.rows.forEach(r => {
        csvRows.push([`"${r.class_name}"`, r.department, r.year, r.section, `"${r.class_teacher_name}"`, r.enrolled_students, r.total_classes, r.present_count, r.absent_count, `${Number(r.attendance_percentage || 0).toFixed(2)}%`, r.status_label]);
      });
    } else if (currentReportType === 'monthly') {
      csvRows.push(['Month', 'Working Days', 'Total Classes', 'Present Count', 'Absent Count', 'Total Records', 'Attendance %']);
      reportCachedData.rows.forEach(r => {
        csvRows.push([`"${r.month_name}"`, r.working_days_count, r.total_classes, r.present_count, r.absent_count, r.total_records, `${Number(r.attendance_percentage || 0).toFixed(2)}%`]);
      });
    }

    const csvContent = 'data:text/csv;charset=utf-8,' + csvRows.map(e => e.join(',')).join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `attendance_${currentReportType}_report_${nowStr}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
}

// Print Report
function printAttendanceReport() {
  const generatedDateElem = document.getElementById('report-meta-generated-date');
  if (generatedDateElem) generatedDateElem.textContent = new Date().toLocaleString();
  window.print();
}

window.initAttendanceReportsModule = initAttendanceReportsModule;
window.switchReportType = switchReportType;
window.setReportDatePreset = setReportDatePreset;
window.applyReportFilters = applyReportFilters;
window.resetReportFilters = resetReportFilters;
window.refreshCurrentReport = refreshCurrentReport;
window.loadAttendanceReport = loadAttendanceReport;
window.exportAttendanceReportCSV = exportAttendanceReportCSV;
window.printAttendanceReport = printAttendanceReport;
window.openStudentSessionModal = openStudentSessionModal;
window.toggleDailySessionsCollapse = toggleDailySessionsCollapse;

