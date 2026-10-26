/**
 * Student Portal Module — All 9 portal sections
 * Namespace: window.SP
 * Hooks into existing app.js navigation + Api client
 */

const SP = (() => {
  // ─────────────────────────────────────────────────────────────────
  // STATE
  // ─────────────────────────────────────────────────────────────────
  let _profile = null;
  let _activeTab = 'sp-overview';

  // ─────────────────────────────────────────────────────────────────
  // HELPERS
  // ─────────────────────────────────────────────────────────────────
  function el(id) { return document.getElementById(id); }

  function setHtml(id, html) {
    const e = el(id);
    if (e) e.innerHTML = html;
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  function fmtDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  function showToast(msg, type = 'success') {
    const container = document.getElementById('app-toast-container');
    if (!container) { console.log('[SP Toast]', type, msg); return; }
    const id = 'sp-toast-' + Date.now();
    const bgMap = { success: 'bg-success', danger: 'bg-danger', warning: 'bg-warning text-dark', info: 'bg-info text-dark' };
    const bg = bgMap[type] || 'bg-secondary';
    const html = `
      <div id="${id}" class="toast align-items-center text-white ${bg} border-0 mb-2" role="alert" data-bs-autohide="true" data-bs-delay="4000">
        <div class="d-flex">
          <div class="toast-body fw-medium small">${msg}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
      </div>`;
    container.insertAdjacentHTML('beforeend', html);
    const toastEl = document.getElementById(id);
    if (toastEl && window.bootstrap) {
      new bootstrap.Toast(toastEl).show();
      toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
    }
  }

  function statusBadge(status) {
    const map = {
      PRESENT: 'bg-success',
      ABSENT: 'bg-danger',
      LATE: 'bg-warning text-dark',
      EXCUSED: 'bg-info text-dark',
      NOT_SUBMITTED: 'bg-danger',
      SUBMITTED: 'bg-primary',
      GRADED: 'bg-success',
      RESUBMITTED: 'bg-warning text-dark',
      NORMAL: 'bg-secondary',
      HIGH: 'bg-warning text-dark',
      URGENT: 'bg-danger',
    };
    const css = map[status] || 'bg-secondary';
    return `<span class="badge ${css} rounded-pill">${status.replace(/_/g, ' ')}</span>`;
  }

  function progressBar(pct, danger = false) {
    const color = pct < 75 ? 'bg-danger' : pct < 85 ? 'bg-warning' : 'bg-success';
    return `
      <div class="progress sp-progress-bar" style="height:8px;">
        <div class="progress-bar ${color}" style="width:${Math.min(pct, 100)}%"></div>
      </div>
      <small class="text-muted">${pct}%</small>`;
  }

  // ─────────────────────────────────────────────────────────────────
  // TAB NAVIGATION
  // ─────────────────────────────────────────────────────────────────
  function switchTab(tabId) {
    _activeTab = tabId;
    document.querySelectorAll('#student-portal-section .sp-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    document.querySelectorAll('#student-portal-section .sp-tab-pane').forEach(pane => {
      pane.classList.toggle('d-none', pane.id !== tabId);
    });

    // Lazy-load each tab
    if (tabId === 'sp-overview') loadOverview();
    else if (tabId === 'sp-attendance') loadAttendance();
    else if (tabId === 'sp-timetable') loadTimetable();
    else if (tabId === 'sp-assignments') loadAssignments();
    else if (tabId === 'sp-grades') loadGrades();
    else if (tabId === 'sp-announcements') loadAnnouncements();
    else if (tabId === 'sp-materials') loadMaterials();
    else if (tabId === 'sp-events') loadEvents();
  }

  // ─────────────────────────────────────────────────────────────────
  // 1. OVERVIEW / DASHBOARD
  // ─────────────────────────────────────────────────────────────────
  async function loadOverview() {
    setHtml('sp-overview-content', `
      <div class="text-center py-4"><div class="spinner-border text-primary"></div><div class="mt-2 text-muted small">Loading profile...</div></div>`);
    try {
      const data = await Api.studentPortal.getProfile();
      _profile = data;
      const s = data.student;
      const qs = data.quick_stats;
      const ci = data.class_info;

      const warningBanner = qs.low_attendance_warning ? `
        <div class="alert alert-danger d-flex align-items-center gap-2 mb-3 py-2">
          <i class="bi bi-exclamation-triangle-fill fs-5"></i>
          <div class="small"><strong>Low Attendance Warning!</strong> Your attendance is ${qs.attendance_percentage}% — below the required 75%. Please attend more classes.</div>
        </div>` : '';

      setHtml('sp-overview-content', `
        ${warningBanner}
        <div class="row g-3 mb-4">
          <div class="col-6 col-md-3">
            <div class="sp-metric-card sp-card-attendance">
              <div class="sp-metric-icon"><i class="bi bi-calendar-check-fill"></i></div>
              <div class="sp-metric-value">${qs.attendance_percentage}%</div>
              <div class="sp-metric-label">Attendance</div>
              ${progressBar(qs.attendance_percentage)}
            </div>
          </div>
          <div class="col-6 col-md-3">
            <div class="sp-metric-card sp-card-assignment">
              <div class="sp-metric-icon"><i class="bi bi-file-earmark-text-fill"></i></div>
              <div class="sp-metric-value">${qs.pending_assignments}</div>
              <div class="sp-metric-label">Pending Tasks</div>
              <small class="text-muted">Assignments due</small>
            </div>
          </div>
          <div class="col-6 col-md-3">
            <div class="sp-metric-card sp-card-sessions">
              <div class="sp-metric-icon"><i class="bi bi-camera-video-fill"></i></div>
              <div class="sp-metric-value">${qs.present_sessions}</div>
              <div class="sp-metric-label">Present</div>
              <small class="text-muted">of ${qs.total_sessions} sessions</small>
            </div>
          </div>
          <div class="col-6 col-md-3">
            <div class="sp-metric-card sp-card-notif">
              <div class="sp-metric-icon"><i class="bi bi-bell-fill"></i></div>
              <div class="sp-metric-value">${qs.unread_notifications}</div>
              <div class="sp-metric-label">Notifications</div>
              <small class="text-muted">Unread</small>
            </div>
          </div>
        </div>

        <div class="row g-3">
          <div class="col-md-5">
            <div class="card border-0 shadow-sm h-100">
              <div class="card-body">
                <h6 class="fw-bold mb-3"><i class="bi bi-person-circle me-2 text-primary"></i>Student Profile</h6>
                <table class="table table-sm table-borderless mb-0">
                  <tr><td class="text-muted small">Name</td><td class="fw-semibold">${s.full_name}</td></tr>
                  <tr><td class="text-muted small">Roll No.</td><td>${s.roll_number}</td></tr>
                  <tr><td class="text-muted small">Register No.</td><td>${s.register_number}</td></tr>
                  <tr><td class="text-muted small">Department</td><td>${s.department}</td></tr>
                  <tr><td class="text-muted small">Year / Section</td><td>Year ${s.year} — Section ${s.section}</td></tr>
                  <tr><td class="text-muted small">Email</td><td>${s.email || '—'}</td></tr>
                  <tr><td class="text-muted small">Phone</td><td>${s.phone || '—'}</td></tr>
                  <tr><td class="text-muted small">Face Enrolled</td><td>${s.face_enrolled ? '<span class="badge bg-success">Yes</span>' : '<span class="badge bg-warning text-dark">No</span>'}</td></tr>
                </table>
              </div>
            </div>
          </div>
          <div class="col-md-7">
            <div class="card border-0 shadow-sm h-100">
              <div class="card-body">
                <h6 class="fw-bold mb-3"><i class="bi bi-building me-2 text-primary"></i>Class Information</h6>
                ${ci ? `
                  <div class="row g-2 text-center mb-3">
                    <div class="col-4">
                      <div class="bg-primary-subtle rounded-2 p-2">
                        <div class="fw-bold text-primary">${ci.department || s.department}</div>
                        <div class="small text-muted">Department</div>
                      </div>
                    </div>
                    <div class="col-4">
                      <div class="bg-success-subtle rounded-2 p-2">
                        <div class="fw-bold text-success">Year ${ci.year}</div>
                        <div class="small text-muted">Academic Year</div>
                      </div>
                    </div>
                    <div class="col-4">
                      <div class="bg-info-subtle rounded-2 p-2">
                        <div class="fw-bold text-info">Section ${ci.section}</div>
                        <div class="small text-muted">Section</div>
                      </div>
                    </div>
                  </div>
                  <div class="text-muted small"><i class="bi bi-hash me-1"></i>${ci.name || 'N/A'}</div>
                ` : '<p class="text-muted small">No class assigned yet. Contact administrator.</p>'}

                <hr class="my-3">
                <h6 class="fw-semibold small text-muted mb-2">QUICK ACTIONS</h6>
                <div class="d-flex flex-wrap gap-2">
                  <button class="btn btn-sm btn-outline-primary" onclick="SP.switchTab('sp-attendance')"><i class="bi bi-calendar-check me-1"></i>View Attendance</button>
                  <button class="btn btn-sm btn-outline-success" onclick="SP.switchTab('sp-timetable')"><i class="bi bi-table me-1"></i>Timetable</button>
                  <button class="btn btn-sm btn-outline-warning" onclick="SP.switchTab('sp-assignments')"><i class="bi bi-file-earmark me-1"></i>Assignments</button>
                  <button class="btn btn-sm btn-outline-info" onclick="SP.switchTab('sp-announcements')"><i class="bi bi-megaphone me-1"></i>Notices</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      `);
    } catch (err) {
      setHtml('sp-overview-content', `<div class="alert alert-danger"><i class="bi bi-exclamation-circle me-2"></i>${err.message}</div>`);
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 2. ATTENDANCE
  // ─────────────────────────────────────────────────────────────────
  async function loadAttendance() {
    setHtml('sp-attendance-content', `<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>`);
    try {
      const data = await Api.studentPortal.getAttendance();
      const ov = data.overall;

      const warningBanner = ov.low_attendance_warning ? `
        <div class="alert alert-danger d-flex gap-2 py-2 mb-3">
          <i class="bi bi-exclamation-triangle-fill"></i>
          <div class="small"><strong>Low Attendance Alert!</strong> ${ov.percentage}% — You need to attend ${ov.sessions_to_75_pct} more sessions to reach 75%.</div>
        </div>` : '';

      // Subject-wise table
      const subjectRows = data.subject_breakdown.map(s => `
        <tr class="${s.low_attendance ? 'table-danger' : ''}">
          <td class="fw-semibold">${s.subject_name} <small class="text-muted">(${s.subject_code})</small></td>
          <td class="text-center">${s.total}</td>
          <td class="text-center text-success">${s.present}</td>
          <td class="text-center text-danger">${s.absent}</td>
          <td>
            ${progressBar(s.percentage)}
            ${s.low_attendance ? '<span class="badge bg-danger rounded-pill ms-1 small">Low</span>' : ''}
          </td>
        </tr>`).join('');

      // Monthly trend
      const monthlyBars = data.monthly_trend.map(m => {
        const h = Math.max(8, m.percentage * 0.8);
        const color = m.percentage < 75 ? '#dc3545' : m.percentage < 85 ? '#fd7e14' : '#198754';
        const [yr, mo] = m.month.split('-');
        const label = new Date(+yr, +mo - 1).toLocaleString('en', { month: 'short' });
        return `
          <div class="sp-bar-col text-center">
            <div class="sp-bar-wrap"><div class="sp-bar" style="height:${h}px;background:${color};" title="${m.percentage}% — ${m.present}/${m.total}"></div></div>
            <div class="small text-muted mt-1">${label}</div>
            <div class="fw-semibold small" style="color:${color}">${m.percentage}%</div>
          </div>`;
      }).join('');

      // Recent records
      const recentRows = data.recent_records.map(r => `
        <tr>
          <td>${fmtDate(r.date)}</td>
          <td>${r.subject} <small class="text-muted">(${r.subject_code})</small></td>
          <td class="text-center">P${r.period}</td>
          <td>${statusBadge(r.status)}</td>
          <td>${r.is_manual ? '<span class="badge bg-secondary rounded-pill">Manual</span>' : ''}</td>
        </tr>`).join('');

      setHtml('sp-attendance-content', `
        ${warningBanner}
        <div class="row g-3 mb-4">
          <div class="col-6 col-lg-3">
            <div class="sp-stat-box text-center">
              <div class="sp-stat-val text-${ov.percentage < 75 ? 'danger' : 'success'}">${ov.percentage}%</div>
              <div class="sp-stat-label">Overall</div>
              ${progressBar(ov.percentage)}
            </div>
          </div>
          <div class="col-6 col-lg-3">
            <div class="sp-stat-box text-center">
              <div class="sp-stat-val text-success">${ov.present}</div>
              <div class="sp-stat-label">Present</div>
            </div>
          </div>
          <div class="col-6 col-lg-3">
            <div class="sp-stat-box text-center">
              <div class="sp-stat-val text-danger">${ov.absent}</div>
              <div class="sp-stat-label">Absent</div>
            </div>
          </div>
          <div class="col-6 col-lg-3">
            <div class="sp-stat-box text-center">
              <div class="sp-stat-val text-warning">${ov.late + ov.excused}</div>
              <div class="sp-stat-label">Late / Excused</div>
            </div>
          </div>
        </div>

        <div class="row g-3 mb-4">
          <div class="col-md-7">
            <div class="card border-0 shadow-sm">
              <div class="card-body">
                <h6 class="fw-bold mb-3"><i class="bi bi-book me-2 text-primary"></i>Subject-Wise Attendance</h6>
                ${subjectRows ? `<div class="table-responsive"><table class="table table-sm align-middle">
                  <thead class="table-light"><tr>
                    <th>Subject</th><th class="text-center">Total</th><th class="text-center">Present</th><th class="text-center">Absent</th><th>Progress</th>
                  </tr></thead>
                  <tbody>${subjectRows}</tbody>
                </table></div>` : '<p class="text-muted">No attendance records.</p>'}
              </div>
            </div>
          </div>
          <div class="col-md-5">
            <div class="card border-0 shadow-sm h-100">
              <div class="card-body">
                <h6 class="fw-bold mb-3"><i class="bi bi-bar-chart me-2 text-primary"></i>Monthly Trend</h6>
                <div class="sp-bar-chart d-flex align-items-end gap-2 justify-content-center" style="height:80px;">
                  ${monthlyBars || '<p class="text-muted small">No data</p>'}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="card border-0 shadow-sm">
          <div class="card-body">
            <h6 class="fw-bold mb-3"><i class="bi bi-clock-history me-2 text-primary"></i>Recent Records (Last 20)</h6>
            ${recentRows ? `<div class="table-responsive"><table class="table table-sm table-hover align-middle">
              <thead class="table-light"><tr><th>Date</th><th>Subject</th><th>Period</th><th>Status</th><th>Note</th></tr></thead>
              <tbody>${recentRows}</tbody>
            </table></div>` : '<p class="text-muted small">No records found.</p>'}
          </div>
        </div>
      `);
    } catch (err) {
      setHtml('sp-attendance-content', `<div class="alert alert-danger">${err.message}</div>`);
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 3. TIMETABLE
  // ─────────────────────────────────────────────────────────────────
  async function loadTimetable() {
    setHtml('sp-timetable-content', `<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>`);
    try {
      const data = await Api.studentPortal.getTimetable();
      const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

      const today = new Date().toLocaleDateString('en-US', { weekday: 'long' });

      const cols = DAYS.map(day => {
        const slots = data.timetable[day] || [];
        const isToday = day === today;
        const header = `<th class="text-center ${isToday ? 'bg-primary text-white' : 'bg-light'}" style="min-width:130px;">${day}${isToday ? ' <span class="badge bg-warning text-dark">Today</span>' : ''}</th>`;
        const cells = slots.length > 0
          ? slots.map(s => `
              <td class="align-top p-2">
                <div class="sp-timetable-cell${isToday ? ' sp-tt-today' : ''}">
                  <div class="fw-semibold small">${s.subject}</div>
                  <div class="text-muted" style="font-size:0.7rem;">${s.subject_code}</div>
                  <div class="text-muted" style="font-size:0.7rem;"><i class="bi bi-clock me-1"></i>${s.start_time}–${s.end_time}</div>
                  <div class="text-muted" style="font-size:0.7rem;"><i class="bi bi-person me-1"></i>${s.teacher}</div>
                  <div class="text-muted" style="font-size:0.7rem;"><i class="bi bi-door-open me-1"></i>${s.classroom}</div>
                  <span class="badge bg-primary-subtle text-primary mt-1" style="font-size:0.65rem;">P${s.period}</span>
                </div>
              </td>`)
            .join('')
          : `<td class="text-center text-muted small py-3" style="background:#f8f9fa;">No classes</td>`;
        return { header, cells, slots };
      });

      const maxPeriods = Math.max(...DAYS.map(d => (data.timetable[d] || []).length), 1);

      let tableHtml = `
        <div class="table-responsive">
          <table class="table table-bordered align-middle small" style="min-width:700px;">
            <thead>
              <tr>
                ${cols.map(c => c.header).join('')}
              </tr>
            </thead>
            <tbody>
              <tr>
                ${cols.map(c => c.cells).join('')}
              </tr>
            </tbody>
          </table>
        </div>`;

      // Exam timetable
      const examRows = data.exam_timetable.map(e => `
        <tr>
          <td class="fw-semibold">${e.exam_name}</td>
          <td>${e.subject} <small class="text-muted">(${e.subject_code})</small></td>
          <td>${fmtDate(e.date)}</td>
          <td>${e.start_time} – ${e.end_time}</td>
          <td>${e.venue}</td>
        </tr>`).join('');

      setHtml('sp-timetable-content', `
        <div class="card border-0 shadow-sm mb-4">
          <div class="card-body">
            <h6 class="fw-bold mb-3"><i class="bi bi-table me-2 text-primary"></i>Weekly Timetable</h6>
            ${Object.values(data.timetable).some(d => d.length > 0) ? tableHtml : '<p class="text-muted">No timetable configured for your class.</p>'}
          </div>
        </div>
        <div class="card border-0 shadow-sm">
          <div class="card-body">
            <h6 class="fw-bold mb-3"><i class="bi bi-clipboard2-check me-2 text-danger"></i>Upcoming Examinations</h6>
            ${examRows ? `<div class="table-responsive"><table class="table table-sm table-hover align-middle">
              <thead class="table-light"><tr><th>Exam</th><th>Subject</th><th>Date</th><th>Time</th><th>Venue</th></tr></thead>
              <tbody>${examRows}</tbody>
            </table></div>` : '<p class="text-muted small">No upcoming exams scheduled.</p>'}
          </div>
        </div>
      `);
    } catch (err) {
      setHtml('sp-timetable-content', `<div class="alert alert-danger">${err.message}</div>`);
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 4. ASSIGNMENTS
  // ─────────────────────────────────────────────────────────────────
  async function loadAssignments() {
    setHtml('sp-assignments-content', `<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>`);
    try {
      const data = await Api.studentPortal.getAssignments();

      function assignmentCard(a, showSubmitBtn = false) {
        const deadlineStr = a.deadline ? `<span class="${a.is_overdue ? 'text-danger fw-semibold' : 'text-muted'}">${fmtDateTime(a.deadline)}${a.is_overdue ? ' (Overdue)' : ''}</span>` : '—';
        const submitBtn = showSubmitBtn
          ? `<button class="btn btn-sm btn-primary mt-2" onclick="SP.openSubmitModal(${a.id}, '${a.title.replace(/'/g, "\\'")}', ${a.maximum_marks})">
              <i class="bi bi-upload me-1"></i>Submit
             </button>`
          : '';
        const marksDisplay = a.marks !== null && a.marks !== undefined
          ? `<span class="badge bg-success ms-1">${a.marks}/${a.maximum_marks}</span>` : '';
        return `
          <div class="sp-assignment-card mb-3 p-3 rounded-3 border">
            <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
              <div>
                <div class="fw-semibold">${a.title} ${marksDisplay}</div>
                <div class="text-muted small">${a.subject} (${a.subject_code}) • ${a.teacher}</div>
                ${a.description ? `<div class="text-muted small mt-1">${a.description}</div>` : ''}
              </div>
              <div class="text-end">
                ${statusBadge(a.status || 'NOT_SUBMITTED')}
                ${a.status === 'GRADED' && a.feedback ? `<div class="text-muted small mt-1"><i class="bi bi-chat-quote me-1"></i>${a.feedback}</div>` : ''}
              </div>
            </div>
            <div class="mt-2 d-flex flex-wrap gap-3 small">
              <span><i class="bi bi-alarm me-1 text-warning"></i>${deadlineStr}</span>
              <span><i class="bi bi-star me-1 text-primary"></i>${a.maximum_marks} marks</span>
              ${a.submitted_date ? `<span><i class="bi bi-check2-circle me-1 text-success"></i>Submitted ${fmtDateTime(a.submitted_date)}</span>` : ''}
            </div>
            ${submitBtn}
          </div>`;
      }

      const pendingHtml = data.pending.length
        ? data.pending.map(a => assignmentCard(a, true)).join('')
        : '<p class="text-muted small">No pending assignments.</p>';
      const submittedHtml = data.submitted.length
        ? data.submitted.map(a => assignmentCard(a, false)).join('')
        : '<p class="text-muted small">No submissions yet.</p>';
      const gradedHtml = data.graded.length
        ? data.graded.map(a => assignmentCard(a, false)).join('')
        : '<p class="text-muted small">No graded assignments.</p>';

      setHtml('sp-assignments-content', `
        <div class="row g-2 mb-3">
          <div class="col-4">
            <div class="sp-stat-box text-center border-danger">
              <div class="sp-stat-val text-danger">${data.pending_count}</div>
              <div class="sp-stat-label">Pending</div>
            </div>
          </div>
          <div class="col-4">
            <div class="sp-stat-box text-center border-primary">
              <div class="sp-stat-val text-primary">${data.submitted.length}</div>
              <div class="sp-stat-label">Submitted</div>
            </div>
          </div>
          <div class="col-4">
            <div class="sp-stat-box text-center border-success">
              <div class="sp-stat-val text-success">${data.graded.length}</div>
              <div class="sp-stat-label">Graded</div>
            </div>
          </div>
        </div>

        <!-- Tabs -->
        <ul class="nav nav-pills mb-3 gap-1" id="sp-assign-tabs">
          <li class="nav-item"><button class="nav-link active" onclick="SP._assignTab(0, this)">
            <i class="bi bi-clock me-1"></i>Pending (${data.pending_count})
          </button></li>
          <li class="nav-item"><button class="nav-link" onclick="SP._assignTab(1, this)">
            <i class="bi bi-check-circle me-1"></i>Submitted
          </button></li>
          <li class="nav-item"><button class="nav-link" onclick="SP._assignTab(2, this)">
            <i class="bi bi-star me-1"></i>Graded
          </button></li>
        </ul>
        <div id="sp-assign-pane-0">${pendingHtml}</div>
        <div id="sp-assign-pane-1" class="d-none">${submittedHtml}</div>
        <div id="sp-assign-pane-2" class="d-none">${gradedHtml}</div>

        <!-- Submit Modal -->
        <div class="modal fade" id="sp-submit-modal" tabindex="-1">
          <div class="modal-dialog">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title"><i class="bi bi-upload me-2"></i>Submit Assignment</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body">
                <p id="sp-submit-modal-title" class="fw-semibold text-muted small mb-3"></p>
                <div class="mb-3">
                  <label class="form-label small fw-semibold">Answer / Notes</label>
                  <textarea id="sp-submit-text" class="form-control" rows="5" placeholder="Type your submission here..."></textarea>
                </div>
                <div class="mb-3">
                  <label class="form-label small fw-semibold">File URL or Path (optional)</label>
                  <input type="text" id="sp-submit-file" class="form-control" placeholder="https://drive.google.com/... or /path/to/file.pdf">
                </div>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" id="sp-submit-confirm-btn" onclick="SP._doSubmit()">
                  <i class="bi bi-send me-1"></i>Submit
                </button>
              </div>
            </div>
          </div>
        </div>
      `);
    } catch (err) {
      setHtml('sp-assignments-content', `<div class="alert alert-danger">${err.message}</div>`);
    }
  }

  let _currentSubmitAssignmentId = null;

  function openSubmitModal(assignmentId, title, maxMarks) {
    _currentSubmitAssignmentId = assignmentId;
    const titleEl = el('sp-submit-modal-title');
    if (titleEl) titleEl.textContent = `${title} — Max: ${maxMarks} marks`;
    const textEl = el('sp-submit-text');
    if (textEl) textEl.value = '';
    const fileEl = el('sp-submit-file');
    if (fileEl) fileEl.value = '';
    const modal = document.getElementById('sp-submit-modal');
    if (modal && window.bootstrap) new bootstrap.Modal(modal).show();
  }

  function _assignTab(idx, btn) {
    [0, 1, 2].forEach(i => {
      const pane = el(`sp-assign-pane-${i}`);
      if (pane) pane.classList.toggle('d-none', i !== idx);
    });
    document.querySelectorAll('#sp-assign-tabs .nav-link').forEach((b, i) => {
      b.classList.toggle('active', i === idx);
    });
  }

  async function _doSubmit() {
    const text = el('sp-submit-text') ? el('sp-submit-text').value.trim() : '';
    const file = el('sp-submit-file') ? el('sp-submit-file').value.trim() : '';
    if (!text && !file) { showToast('Please provide a submission text or file URL.', 'warning'); return; }

    const btn = el('sp-submit-confirm-btn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Submitting...'; }

    try {
      const result = await Api.studentPortal.submitAssignment(_currentSubmitAssignmentId, text || null, file || null);
      const modalEl = document.getElementById('sp-submit-modal');
      if (modalEl && window.bootstrap) bootstrap.Modal.getInstance(modalEl)?.hide();
      showToast(result.is_late ? 'Assignment submitted (marked as late).' : 'Assignment submitted!', result.is_late ? 'warning' : 'success');
      loadAssignments();
    } catch (err) {
      showToast(err.message, 'danger');
    } finally {
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-send me-1"></i>Submit'; }
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 5. GRADES
  // ─────────────────────────────────────────────────────────────────
  async function loadGrades() {
    setHtml('sp-grades-content', `<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>`);
    try {
      const data = await Api.studentPortal.getGrades();
      const op = data.overall_performance;

      const gradeColor = (pct) => pct >= 80 ? 'text-success' : pct >= 60 ? 'text-primary' : pct >= 40 ? 'text-warning' : 'text-danger';

      const semesterSections = data.semesters.map(sem => {
        const rows = sem.records.map(r => `
          <tr>
            <td class="fw-semibold">${r.subject} <small class="text-muted">(${r.subject_code})</small></td>
            <td class="text-muted small">${r.assessment_type}</td>
            <td class="text-center fw-semibold">${r.marks} / ${r.max_marks}</td>
            <td class="text-center">
              <span class="fw-bold ${gradeColor(r.percentage)}">${r.percentage}%</span>
            </td>
            <td><span class="badge bg-primary-subtle text-primary rounded-pill">${r.grade}</span></td>
            <td class="text-muted small">${r.remarks || '—'}</td>
          </tr>`).join('');
        return `
          <div class="card border-0 shadow-sm mb-3">
            <div class="card-header bg-primary-subtle text-primary fw-bold">${sem.label}</div>
            <div class="card-body p-0">
              <div class="table-responsive">
                <table class="table table-sm align-middle mb-0">
                  <thead class="table-light"><tr>
                    <th>Subject</th><th>Assessment</th><th class="text-center">Marks</th><th class="text-center">%</th><th>Grade</th><th>Remarks</th>
                  </tr></thead>
                  <tbody>${rows}</tbody>
                </table>
              </div>
            </div>
          </div>`;
      }).join('');

      setHtml('sp-grades-content', `
        <div class="row g-3 mb-4">
          <div class="col-md-4">
            <div class="sp-metric-card text-center">
              <div class="sp-metric-icon"><i class="bi bi-award-fill"></i></div>
              <div class="sp-metric-value ${gradeColor(op.percentage)}">${op.percentage}%</div>
              <div class="sp-metric-label">Overall Score</div>
              <div class="small fw-semibold text-primary mt-1">${op.grade}</div>
            </div>
          </div>
          <div class="col-md-4">
            <div class="sp-metric-card text-center">
              <div class="sp-metric-icon"><i class="bi bi-clipboard-check-fill"></i></div>
              <div class="sp-metric-value text-info">${op.total_assessments}</div>
              <div class="sp-metric-label">Total Assessments</div>
            </div>
          </div>
          <div class="col-md-4">
            <div class="sp-metric-card text-center">
              <div class="sp-metric-icon"><i class="bi bi-book-fill"></i></div>
              <div class="sp-metric-value text-primary">${data.semesters.length}</div>
              <div class="sp-metric-label">Semesters</div>
            </div>
          </div>
        </div>
        ${semesterSections || '<div class="alert alert-info"><i class="bi bi-info-circle me-2"></i>No academic records found.</div>'}
      `);
    } catch (err) {
      setHtml('sp-grades-content', `<div class="alert alert-danger">${err.message}</div>`);
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 6. ANNOUNCEMENTS
  // ─────────────────────────────────────────────────────────────────
  async function loadAnnouncements() {
    setHtml('sp-announcements-content', `<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>`);
    try {
      const data = await Api.studentPortal.getAnnouncements();

      const cards = data.announcements.map(a => {
        const priorityBorder = a.priority === 'URGENT' ? 'border-danger' : a.priority === 'HIGH' ? 'border-warning' : 'border-light';
        const priorityHeader = a.priority === 'URGENT' ? 'bg-danger text-white' : a.priority === 'HIGH' ? 'bg-warning text-dark' : 'bg-light text-muted';
        return `
          <div class="card ${priorityBorder} shadow-sm mb-3">
            <div class="card-header ${priorityHeader} py-2 d-flex justify-content-between align-items-center">
              <span class="fw-semibold">${a.title}</span>
              ${statusBadge(a.priority)}
            </div>
            <div class="card-body py-2">
              <p class="mb-1 small">${a.message}</p>
              <div class="d-flex gap-3 text-muted" style="font-size:0.75rem;">
                <span><i class="bi bi-person me-1"></i>${a.author}</span>
                <span><i class="bi bi-calendar me-1"></i>${fmtDate(a.publication_date)}</span>
                ${a.expiry_date ? `<span><i class="bi bi-clock me-1"></i>Expires ${fmtDate(a.expiry_date)}</span>` : ''}
              </div>
            </div>
          </div>`;
      }).join('');

      setHtml('sp-announcements-content', `
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h6 class="fw-bold mb-0"><i class="bi bi-megaphone me-2 text-primary"></i>Announcements & Notices</h6>
          ${data.urgent_count > 0 ? `<span class="badge bg-danger rounded-pill">${data.urgent_count} urgent</span>` : ''}
        </div>
        ${cards || '<div class="alert alert-info"><i class="bi bi-info-circle me-2"></i>No announcements at this time.</div>'}
      `);
    } catch (err) {
      setHtml('sp-announcements-content', `<div class="alert alert-danger">${err.message}</div>`);
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 7. STUDY MATERIALS
  // ─────────────────────────────────────────────────────────────────
  async function loadMaterials() {
    setHtml('sp-materials-content', `<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>`);
    try {
      const data = await Api.studentPortal.getMaterials();

      const cards = data.materials.map(m => `
        <div class="col-md-6 col-lg-4">
          <div class="card border-0 shadow-sm h-100">
            <div class="card-body">
              <div class="d-flex align-items-start gap-2 mb-2">
                <div class="p-2 bg-primary-subtle rounded-2"><i class="bi bi-file-earmark-text-fill text-primary fs-5"></i></div>
                <div>
                  <div class="fw-semibold small">${m.title}</div>
                  <div class="text-muted" style="font-size:0.75rem;">${m.subject} (${m.subject_code})</div>
                </div>
              </div>
              ${m.description ? `<p class="text-muted small mb-2">${m.description}</p>` : ''}
              <div class="d-flex justify-content-between align-items-center">
                <small class="text-muted"><i class="bi bi-person me-1"></i>${m.teacher}</small>
                <small class="text-muted">${fmtDate(m.uploaded_date)}</small>
              </div>
              ${m.file_url ? `<a href="${m.file_url}" target="_blank" class="btn btn-sm btn-outline-primary w-100 mt-2">
                <i class="bi bi-download me-1"></i>Download / View
              </a>` : ''}
            </div>
          </div>
        </div>`).join('');

      setHtml('sp-materials-content', `
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h6 class="fw-bold mb-0"><i class="bi bi-folder2-open me-2 text-primary"></i>Study Materials</h6>
          <span class="badge bg-secondary rounded-pill">${data.total} files</span>
        </div>
        ${cards ? `<div class="row g-3">${cards}</div>` : '<div class="alert alert-info"><i class="bi bi-info-circle me-2"></i>No study materials uploaded yet.</div>'}
      `);
    } catch (err) {
      setHtml('sp-materials-content', `<div class="alert alert-danger">${err.message}</div>`);
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // 8. EVENTS
  // ─────────────────────────────────────────────────────────────────
  async function loadEvents() {
    setHtml('sp-events-content', `<div class="text-center py-4"><div class="spinner-border text-primary"></div></div>`);
    try {
      const data = await Api.studentPortal.getEvents();
      const catColor = { Cultural: 'text-purple', Sports: 'text-success', Technical: 'text-primary', Workshop: 'text-warning', Academic: 'text-info' };

      const cards = data.events.map(e => `
        <div class="col-md-6">
          <div class="card border-0 shadow-sm h-100">
            <div class="card-body">
              <div class="d-flex gap-3 align-items-start">
                <div class="sp-event-date text-center">
                  <div class="sp-event-day">${new Date(e.date).getDate()}</div>
                  <div class="sp-event-month">${new Date(e.date).toLocaleString('en', { month: 'short' })}</div>
                </div>
                <div>
                  <div class="fw-semibold">${e.title}</div>
                  <div class="small text-muted mb-1">${e.category} ${e.venue ? `• ${e.venue}` : ''}</div>
                  ${e.description ? `<p class="text-muted small mb-0">${e.description}</p>` : ''}
                </div>
              </div>
            </div>
          </div>
        </div>`).join('');

      setHtml('sp-events-content', `
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h6 class="fw-bold mb-0"><i class="bi bi-calendar-star me-2 text-primary"></i>College Events</h6>
          <span class="badge bg-secondary rounded-pill">${data.total} upcoming</span>
        </div>
        ${cards ? `<div class="row g-3">${cards}</div>` : '<div class="alert alert-info"><i class="bi bi-info-circle me-2"></i>No upcoming events.</div>'}
      `);
    } catch (err) {
      setHtml('sp-events-content', `<div class="alert alert-danger">${err.message}</div>`);
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // PUBLIC INIT
  // ─────────────────────────────────────────────────────────────────
  function init() {
    // Wire up tab buttons
    document.querySelectorAll('#student-portal-section .sp-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
  }

  return {
    init,
    switchTab,
    openSubmitModal,
    _assignTab,
    _doSubmit,
    loadOverview,
  };
})();

window.SP = SP;
